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
    p.add_argument("--gfs-input-dir", default=None,
                   help="Directory containing GFS M-A0060 GRIB2 files (multi-level wind/T/RH)")
    p.add_argument("--gfs-region", default="105,10,140,35",
                   help="lon_min,lat_min,lon_max,lat_max bbox cropped from the global GFS grid "
                        "(default Taiwan/W-Pacific). Use 'global' to keep full grid.")
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


def _open_grib_level(grb, type_of_level: str, level: int, xr):
    """Open a single (typeOfLevel, level) slice of a GRIB2 file via cfgrib.

    cfgrib cannot open a multi-parameter / multi-level GRIB2 in one call, so we
    filter per level using filter_by_keys. Returns an xarray Dataset or None on
    failure.
    """
    try:
        return xr.open_dataset(
            grb, engine="cfgrib",
            backend_kwargs={
                "filter_by_keys": {"typeOfLevel": type_of_level, "level": level},
                "indexpath": "",
            },
        )
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ 無法讀取 {grb.name} ({type_of_level}={level}): {exc}")
        return None


def _pick_var(ds, candidates: tuple[str, ...]) -> str | None:
    for name in candidates:
        if name in ds.data_vars:
            return name
    return None


def _crop_region(ds, region: tuple[float, float, float, float] | None):
    """Crop an xarray Dataset to a (lon_min, lat_min, lon_max, lat_max) bbox.

    GFS uses 0..360 longitude convention, so wrap the requested lon range
    accordingly. Returns the dataset unchanged if region is None.
    """
    if region is None:
        return ds
    lon_min, lat_min, lon_max, lat_max = region
    lon_name = "longitude" if "longitude" in ds.coords else "lon"
    lat_name = "latitude" if "latitude" in ds.coords else "lat"
    # Normalise requested lon to match dataset convention
    ds_lon = ds[lon_name]
    if float(ds_lon.max()) > 180 and lon_min < 0:
        lon_min += 360
    if float(ds_lon.max()) > 180 and lon_max < 0:
        lon_max += 360

    # Build slices respecting the axis direction (GFS lat is N→S, so slice high→low).
    ds_lat = ds[lat_name]
    if float(ds_lat[0]) > float(ds_lat[-1]):
        lat_slice = slice(lat_max, lat_min)
    else:
        lat_slice = slice(lat_min, lat_max)
    lon_slice = slice(lon_min, lon_max)
    return ds.sel({lon_name: lon_slice, lat_name: lat_slice})


def convert_gfs_grib2(grb_files: list, output_dir: Path, xr,
                      region: tuple[float, float, float, float] | None = None) -> int:
    """Convert GFS M-A0060 GRIB2 files into three compressed NC files.

    Writes:
      - wind_gfs_fixed.nc  (x_wind_10m/y_wind_10m + x_wind_pl/y_wind_pl on pressure levels)
      - temp_gfs_fixed.nc  (temp_2m + temp_pl on pressure levels)
      - rh_gfs_fixed.nc    (rh_2m + rh_pl on pressure levels)
    All stacked along a `time` dimension, pressure-level fields stacked along `level`.

    `region` = (lon_min, lat_min, lon_max, lat_max) crops to a bbox so the
    per-variable NetCDF stays well under GitHub's 100 MB file cap. Pass None
    to keep the full 0.25° global grid.
    """
    PRESSURE_LEVELS = [850, 925, 1000]

    wind_hours: list = []
    temp_hours: list = []
    rh_hours: list = []

    for grb in grb_files:
        print(f"🌍 讀取 GFS：{grb.name}")

        ds_h10 = _open_grib_level(grb, "heightAboveGround", 10, xr)
        ds_h2 = _open_grib_level(grb, "heightAboveGround", 2, xr)
        if ds_h10 is not None:
            ds_h10 = _crop_region(ds_h10, region)
        if ds_h2 is not None:
            ds_h2 = _crop_region(ds_h2, region)

        pl_datasets = []
        for lvl in PRESSURE_LEVELS:
            dsp = _open_grib_level(grb, "isobaricInhPa", lvl, xr)
            if dsp is None:
                break
            pl_datasets.append((lvl, _crop_region(dsp, region)))

        if len(pl_datasets) != len(PRESSURE_LEVELS) or ds_h10 is None or ds_h2 is None:
            print(f"⏭️ 跳過（缺少層次）：{grb.name}")
            for _, d in pl_datasets:
                d.close()
            if ds_h10 is not None:
                ds_h10.close()
            if ds_h2 is not None:
                ds_h2.close()
            continue

        # --- Surface wind (10 m) ---
        u10_name = _pick_var(ds_h10, ("u10", "10u", "UGRD"))
        v10_name = _pick_var(ds_h10, ("v10", "10v", "VGRD"))
        if u10_name and v10_name:
            surf_wind = ds_h10[[u10_name, v10_name]].rename({
                u10_name: "x_wind_10m",
                v10_name: "y_wind_10m",
            })
        else:
            print(f"⚠️ 找不到 10m 風場變數 (有: {list(ds_h10.data_vars)})")
            surf_wind = None

        # --- 2 m temperature + humidity ---
        t2_name = _pick_var(ds_h2, ("t2m", "2t"))
        r2_name = _pick_var(ds_h2, ("r2", "2r"))
        surf_temp = ds_h2[[t2_name]].rename({t2_name: "temp_2m"}) if t2_name else None
        surf_rh = ds_h2[[r2_name]].rename({r2_name: "rh_2m"}) if r2_name else None

        # --- Pressure-level u/v/t/r ---
        u_pl, v_pl, t_pl, r_pl = [], [], [], []
        for lvl, dsp in pl_datasets:
            u_n = _pick_var(dsp, ("u", "UGRD"))
            v_n = _pick_var(dsp, ("v", "VGRD"))
            t_n = _pick_var(dsp, ("t", "TMP"))
            r_n = _pick_var(dsp, ("r", "RH"))
            if u_n and v_n:
                w = dsp[[u_n, v_n]].rename({u_n: "x_wind_pl", v_n: "y_wind_pl"})
                u_pl.append(w)
            if t_n:
                t_pl.append(dsp[[t_n]].rename({t_n: "temp_pl"}))
            if r_n:
                r_pl.append(dsp[[r_n]].rename({r_n: "rh_pl"}))

        # Build per-hour merged datasets. Wind: merge surface + pressure levels.
        # Use xr.concat + assign_coords to avoid a pandas dependency.
        def _stack_levels(pieces):
            return xr.concat(pieces, dim="level").assign_coords(level=PRESSURE_LEVELS)

        pieces_wind = []
        if surf_wind is not None:
            pieces_wind.append(surf_wind)
        if len(u_pl) == len(PRESSURE_LEVELS):
            pieces_wind.append(_stack_levels(u_pl))
        if pieces_wind:
            merged_wind = xr.merge(pieces_wind, compat="override")
            if "time" in merged_wind.coords and "time" not in merged_wind.dims:
                merged_wind = merged_wind.expand_dims("time")
            wind_hours.append(merged_wind)

        pieces_temp = []
        if surf_temp is not None:
            pieces_temp.append(surf_temp)
        if len(t_pl) == len(PRESSURE_LEVELS):
            pieces_temp.append(_stack_levels(t_pl))
        if pieces_temp:
            merged_temp = xr.merge(pieces_temp, compat="override")
            if "time" in merged_temp.coords and "time" not in merged_temp.dims:
                merged_temp = merged_temp.expand_dims("time")
            temp_hours.append(merged_temp)

        pieces_rh = []
        if surf_rh is not None:
            pieces_rh.append(surf_rh)
        if len(r_pl) == len(PRESSURE_LEVELS):
            pieces_rh.append(_stack_levels(r_pl))
        if pieces_rh:
            merged_rh = xr.merge(pieces_rh, compat="override")
            if "time" in merged_rh.coords and "time" not in merged_rh.dims:
                merged_rh = merged_rh.expand_dims("time")
            rh_hours.append(merged_rh)

        ds_h10.close()
        ds_h2.close()
        for _, d in pl_datasets:
            d.close()

    written = 0

    def _write(name: str, datasets: list, vars_attrs: dict) -> None:
        nonlocal written
        if not datasets:
            print(f"⚠️ GFS {name}: 無資料可輸出")
            return
        ds_out = xr.concat(datasets, dim="time")
        for var, attrs in vars_attrs.items():
            if var in ds_out.data_vars:
                ds_out[var].attrs.update(attrs)
        dst = output_dir / name
        encoding = {v: {"zlib": True, "complevel": 4} for v in ds_out.data_vars}
        ds_out.to_netcdf(dst, encoding=encoding)
        size_mb = dst.stat().st_size / 1024 / 1024
        print(f"✅ {name}: {size_mb:.1f} MB ({len(datasets)} 個時間步)")
        ds_out.close()
        written += 1

    _write("wind_gfs_fixed.nc", wind_hours, {
        "x_wind_10m": {"standard_name": "eastward_wind", "units": "m s-1"},
        "y_wind_10m": {"standard_name": "northward_wind", "units": "m s-1"},
        "x_wind_pl": {"standard_name": "eastward_wind", "units": "m s-1"},
        "y_wind_pl": {"standard_name": "northward_wind", "units": "m s-1"},
    })
    _write("temp_gfs_fixed.nc", temp_hours, {
        "temp_2m": {"standard_name": "air_temperature", "units": "K"},
        "temp_pl": {"standard_name": "air_temperature", "units": "K"},
    })
    _write("rh_gfs_fixed.nc", rh_hours, {
        "rh_2m": {"standard_name": "relative_humidity", "units": "%"},
        "rh_pl": {"standard_name": "relative_humidity", "units": "%"},
    })

    return written


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

    # Convert GFS M-A0060 GRIB2 (multi-level wind/T/RH)
    if args.gfs_input_dir:
        gfs_dir = Path(args.gfs_input_dir)
        grb_files = sorted(gfs_dir.glob("*.grb2"))
        if not grb_files:
            print(f"⚠️ 找不到 GFS GRIB2 檔案：{gfs_dir}/*.grb2")
        else:
            region: tuple[float, float, float, float] | None = None
            if args.gfs_region and args.gfs_region.lower() != "global":
                try:
                    parts = [float(x) for x in args.gfs_region.split(",")]
                    if len(parts) != 4:
                        raise ValueError("expected 4 comma-separated floats")
                    region = (parts[0], parts[1], parts[2], parts[3])
                except Exception as exc:  # noqa: BLE001
                    print(f"⚠️ 無法解析 --gfs-region '{args.gfs_region}': {exc} — 使用全球範圍")
            try:
                convert_gfs_grib2(grb_files, output_dir, xr, region=region)
            except Exception as exc:  # noqa: BLE001
                import traceback
                print(f"❌ GFS 轉換失敗：{exc}")
                traceback.print_exc()
                return 4

    return 0


if __name__ == "__main__":
    sys.exit(main())
