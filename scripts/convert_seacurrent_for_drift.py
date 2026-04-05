#!/usr/bin/env python3
"""Convert SeaCurrent NetCDF / wind GRIB2 files to OpenDrift-friendly format.

Outputs two compressed files:
  - current_fixed.nc  (x_sea_water_velocity, y_sea_water_velocity)
  - wind_fixed.nc     (x_wind, y_wind, merged from all GRIB2 time steps)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Convert SeaCurrent .nc files for drift forecast use.")
    p.add_argument("--input-dir", default="data/nc_files", help="Directory containing downloaded .nc files")
    p.add_argument("--output-dir", default="data/nc_converted", help="Directory for converted .nc files")
    p.add_argument("--pattern", default="*.nc", help="Glob pattern of source files")
    p.add_argument("--wind-input-dir", default=None, help="Directory containing wind GRIB2 files")
    return p.parse_args()


def convert_current(input_dir: Path, output_dir: Path, pattern: str, xr) -> int:
    """Convert sea current NC files → current_fixed.nc."""
    src_files = sorted(input_dir.glob(pattern))
    if not src_files:
        print(f"⚠️ 找不到要轉換的檔案：{input_dir}/{pattern}")
        return 0

    converted = 0
    for src in src_files:
        print(f"🔄 轉換海流：{src}")
        try:
            ds = xr.open_dataset(src)
        except Exception as exc:  # noqa: BLE001
            print(f"❌ 開啟失敗：{src} ({exc})")
            continue

        if "UC" not in ds.variables or "VC" not in ds.variables:
            print(f"⏭️ 跳過（無 UC/VC 變數）：{src.name}")
            ds.close()
            continue

        # Only keep UC/VC, rename for OpenDrift
        current = ds[["UC", "VC"]].rename({
            "UC": "x_sea_water_velocity",
            "VC": "y_sea_water_velocity",
        })
        ds.close()

        current["x_sea_water_velocity"].attrs.update({
            "standard_name": "eastward_sea_water_velocity",
            "units": "m s-1",
            "coordinates": "longitude latitude",
        })
        current["y_sea_water_velocity"].attrs.update({
            "standard_name": "northward_sea_water_velocity",
            "units": "m s-1",
            "coordinates": "longitude latitude",
        })

        dst = output_dir / "current_fixed.nc"
        encoding = {v: {"zlib": True, "complevel": 4} for v in current.data_vars}
        current.to_netcdf(dst, encoding=encoding)
        current.close()
        converted += 1
        size_mb = dst.stat().st_size / 1024 / 1024
        print(f"✅ current_fixed.nc: {size_mb:.1f} MB")

    return converted


def convert_wind_grib2(grb_files: list, output_dir: Path, xr) -> int:
    """Convert wind GRIB2 files → merged wind_fixed.nc."""
    U_NAMES = ("u10", "u100", "UGRD", "u")
    V_NAMES = ("v10", "v100", "VGRD", "v")

    datasets = []
    for grb in grb_files:
        print(f"🌬️ 讀取風場：{grb.name}")
        try:
            ds = xr.open_dataset(
                grb, engine="cfgrib",
                backend_kwargs={"indexpath": ""},
            )
        except Exception:
            ds = xr.open_dataset(
                grb, engine="cfgrib",
                backend_kwargs={
                    "filter_by_keys": {"typeOfLevel": "heightAboveGround", "level": 10},
                    "indexpath": "",
                },
            )

        available = list(ds.data_vars)
        rename_map = {}
        for name in U_NAMES:
            if name in available:
                rename_map[name] = "x_wind"
                break
        for name in V_NAMES:
            if name in available:
                rename_map[name] = "y_wind"
                break

        if len(rename_map) < 2:
            print(f"⏭️ 跳過（找不到風場變數，可用: {available}）：{grb.name}")
            ds.close()
            continue

        ds2 = ds.rename(rename_map)
        ds.close()

        # Ensure time dimension for concatenation
        if "time" in ds2.coords and "time" not in ds2.dims:
            ds2 = ds2.expand_dims("time")
        datasets.append(ds2)

    if not datasets:
        print("⚠️ 沒有成功讀取任何風場檔案")
        return 0

    # Merge all time steps into one file
    wind = xr.concat(datasets, dim="time")
    wind["x_wind"].attrs.update({"standard_name": "x_wind", "units": "m s-1"})
    wind["y_wind"].attrs.update({"standard_name": "y_wind", "units": "m s-1"})

    dst = output_dir / "wind_fixed.nc"
    encoding = {v: {"zlib": True, "complevel": 4} for v in wind.data_vars}
    wind.to_netcdf(dst, encoding=encoding)

    for ds2 in datasets:
        ds2.close()
    wind.close()

    size_mb = dst.stat().st_size / 1024 / 1024
    print(f"✅ wind_fixed.nc: {size_mb:.1f} MB ({len(datasets)} 個時間步合併)")
    return len(datasets)


def main() -> int:
    args = parse_args()

    try:
        import xarray as xr  # type: ignore
    except Exception as exc:  # noqa: BLE001
        print(f"❌ 需要 xarray 才能做 NetCDF 轉換：{exc}")
        return 2

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Convert sea current
    current_count = convert_current(input_dir, output_dir, args.pattern, xr)
    print(f"✅ 海流轉換完成：{current_count} 個檔案")

    # Convert wind GRIB2
    if args.wind_input_dir:
        wind_dir = Path(args.wind_input_dir)
        grb_files = sorted(wind_dir.glob("*.grb2"))
        if not grb_files:
            print(f"⚠️ 找不到風場 GRIB2 檔案：{wind_dir}/*.grb2")
        else:
            try:
                convert_wind_grib2(grb_files, output_dir, xr)
            except Exception as exc:  # noqa: BLE001
                print(f"❌ 風場轉換失敗：{exc}")
                return 3

    return 0


if __name__ == "__main__":
    sys.exit(main())
