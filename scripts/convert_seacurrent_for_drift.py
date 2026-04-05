#!/usr/bin/env python3
"""Convert SeaCurrent NetCDF files to OpenDrift-friendly variable names."""

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

    src_files = sorted(input_dir.glob(args.pattern))
    if not src_files:
        print(f"⚠️ 找不到要轉換的檔案：{input_dir}/{args.pattern}")
        return 0

    converted = 0
    skipped = 0

    for src in src_files:
        dst = output_dir / src.name
        print(f"🔄 轉換：{src} -> {dst}")
        try:
            ds = xr.open_dataset(src)
        except Exception as exc:  # noqa: BLE001
            print(f"❌ 開啟失敗：{src} ({exc})")
            continue

        rename_map = {}
        if "UC" in ds.variables:
            rename_map["UC"] = "x_sea_water_velocity"
        if "VC" in ds.variables:
            rename_map["VC"] = "y_sea_water_velocity"

        if not rename_map:
            print(f"⏭️ 跳過（無 UC/VC 變數）：{src.name}")
            skipped += 1
            ds.close()
            continue

        ds2 = ds.rename(rename_map)
        ds.close()

        if "x_sea_water_velocity" in ds2.variables:
            ds2["x_sea_water_velocity"].attrs.update(
                {
                    "standard_name": "eastward_sea_water_velocity",
                    "units": "m s-1",
                    "coordinates": "longitude latitude",
                }
            )
        if "y_sea_water_velocity" in ds2.variables:
            ds2["y_sea_water_velocity"].attrs.update(
                {
                    "standard_name": "northward_sea_water_velocity",
                    "units": "m s-1",
                    "coordinates": "longitude latitude",
                }
            )

        ds2.to_netcdf(dst)
        ds2.close()
        converted += 1

    print(f"✅ 轉換完成：成功 {converted}，跳過 {skipped}")

    # Wind GRIB2 → NetCDF conversion
    if args.wind_input_dir:
        wind_dir = Path(args.wind_input_dir)
        grb_files = sorted(wind_dir.glob("*.grb2"))
        if not grb_files:
            print(f"⚠️ 找不到風場 GRIB2 檔案：{wind_dir}/*.grb2")
        else:
            try:
                wind_converted = convert_wind_grib2(grb_files, output_dir, xr)
                print(f"✅ 風場轉換完成：成功 {wind_converted}")
            except Exception as exc:  # noqa: BLE001
                print(f"❌ 風場轉換失敗：{exc}")
                return 3

    return 0


def convert_wind_grib2(grb_files: list, output_dir: Path, xr) -> int:
    """Convert wind GRIB2 files to OpenDrift-compatible NetCDF."""
    # Possible wind variable names from cfgrib
    U_NAMES = ("u10", "u100", "UGRD", "u")
    V_NAMES = ("v10", "v100", "VGRD", "v")

    converted = 0
    for grb in grb_files:
        dst = output_dir / grb.with_suffix(".nc").name
        print(f"🌬️ 轉換風場：{grb.name} -> {dst.name}")

        try:
            ds = xr.open_dataset(
                grb, engine="cfgrib",
                backend_kwargs={"indexpath": ""},
            )
        except Exception:
            # Try filtering for 10m wind specifically
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
            print(f"⏭️ 跳過（找不到風場變數，可用變數: {available}）：{grb.name}")
            ds.close()
            continue

        ds2 = ds.rename(rename_map)
        ds2["x_wind"].attrs.update({
            "standard_name": "x_wind",
            "units": "m s-1",
        })
        ds2["y_wind"].attrs.update({
            "standard_name": "y_wind",
            "units": "m s-1",
        })
        ds2.to_netcdf(dst)
        ds.close()
        ds2.close()
        converted += 1

    return converted


if __name__ == "__main__":
    sys.exit(main())
