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
    return 0


if __name__ == "__main__":
    sys.exit(main())
