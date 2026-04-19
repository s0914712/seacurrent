#!/usr/bin/env python3
"""Convert NetCDF ocean current / wind data to leaflet-velocity JSON format.

Produces two JSON files that can be loaded by the leaflet-velocity plugin to
render Windy-style animated particle flow on a Leaflet map.

Output files (in --output-dir):
  - current_velocity.json   (sea current u/v)
  - wind_velocity.json      (wind u/v)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np


# ---- GFS M-A0060 multi-level layer specifications --------------------------
# Each entry produces a per-hour JSON frame at
#   scheduled_results/frames/<name>/h{HHH}.json
# Vector layers use the leaflet-velocity u/v pair; scalar layers use a
# single-component header compatible with leaflet.canvaslayer.field.
GFS_LAYER_SPECS: list[dict] = [
    # Winds
    {"name": "wind_10m",     "kind": "vector", "nc": "wind_gfs_fixed.nc",
     "u": "x_wind_10m", "v": "y_wind_10m",
     "u_name": "eastward_wind", "v_name": "northward_wind"},
    {"name": "wind_850hPa",  "kind": "vector", "nc": "wind_gfs_fixed.nc",
     "u": "x_wind_pl", "v": "y_wind_pl", "level": 850,
     "u_name": "eastward_wind", "v_name": "northward_wind"},
    {"name": "wind_925hPa",  "kind": "vector", "nc": "wind_gfs_fixed.nc",
     "u": "x_wind_pl", "v": "y_wind_pl", "level": 925,
     "u_name": "eastward_wind", "v_name": "northward_wind"},
    {"name": "wind_1000hPa", "kind": "vector", "nc": "wind_gfs_fixed.nc",
     "u": "x_wind_pl", "v": "y_wind_pl", "level": 1000,
     "u_name": "eastward_wind", "v_name": "northward_wind"},
    # Temperature (K)
    {"name": "temp_2m",      "kind": "scalar", "nc": "temp_gfs_fixed.nc",
     "var": "temp_2m",  "units": "K", "param_name": "air_temperature"},
    {"name": "temp_850hPa",  "kind": "scalar", "nc": "temp_gfs_fixed.nc",
     "var": "temp_pl",  "level": 850, "units": "K", "param_name": "air_temperature"},
    {"name": "temp_925hPa",  "kind": "scalar", "nc": "temp_gfs_fixed.nc",
     "var": "temp_pl",  "level": 925, "units": "K", "param_name": "air_temperature"},
    {"name": "temp_1000hPa", "kind": "scalar", "nc": "temp_gfs_fixed.nc",
     "var": "temp_pl",  "level": 1000, "units": "K", "param_name": "air_temperature"},
    # Relative humidity (%)
    {"name": "rh_2m",        "kind": "scalar", "nc": "rh_gfs_fixed.nc",
     "var": "rh_2m",   "units": "%", "param_name": "relative_humidity"},
    {"name": "rh_850hPa",    "kind": "scalar", "nc": "rh_gfs_fixed.nc",
     "var": "rh_pl",   "level": 850, "units": "%", "param_name": "relative_humidity"},
    {"name": "rh_925hPa",    "kind": "scalar", "nc": "rh_gfs_fixed.nc",
     "var": "rh_pl",   "level": 925, "units": "%", "param_name": "relative_humidity"},
    {"name": "rh_1000hPa",   "kind": "scalar", "nc": "rh_gfs_fixed.nc",
     "var": "rh_pl",   "level": 1000, "units": "%", "param_name": "relative_humidity"},
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Convert NC data to leaflet-velocity JSON.")
    p.add_argument("--input-dir", default="data/nc_converted",
                   help="Directory containing current_fixed.nc / wind_fixed.nc")
    p.add_argument("--output-dir", default="scheduled_results",
                   help="Output directory for JSON files")
    p.add_argument("--time-index", type=int, default=0,
                   help="Time step index to extract (default: 0 = latest)")
    p.add_argument("--current-step", type=int, default=1,
                   help="Subsampling step for current grid (1=full res)")
    p.add_argument("--wind-step", type=int, default=4,
                   help="Subsampling step for wind grid (reduces file size)")
    p.add_argument("--gfs-step", type=int, default=4,
                   help="Subsampling step for GFS (M-A0060) 0.25° global grid")
    p.add_argument("--precision", type=int, default=3,
                   help="Decimal places for velocity values")
    p.add_argument("--frames", action="store_true",
                   help="Emit one JSON per time step into <output-dir>/frames/{current,wind,...}/h###.json")
    p.add_argument("--max-hours", type=int, default=72,
                   help="When --frames is set, only emit up to this lead-time (hours)")
    return p.parse_args()


def build_velocity_json(
    u: np.ndarray,
    v: np.ndarray,
    lons: np.ndarray,
    lats: np.ndarray,
    u_name: str,
    v_name: str,
    u_param_num: int = 2,
    v_param_num: int = 3,
) -> list[dict]:
    """Build leaflet-velocity compatible JSON from u/v arrays on a regular grid.

    Data must be on a regular grid (1D lon, 1D lat).
    lat[0] should be the northernmost latitude (data scanned N→S).
    """
    ny, nx = u.shape
    lo1, lo2 = float(lons[0]), float(lons[-1])
    la1, la2 = float(lats[0]), float(lats[-1])
    dx = float(lons[1] - lons[0]) if nx > 1 else 1.0
    dy = float(lats[0] - lats[1]) if ny > 1 else 1.0  # positive (N→S step)

    header_common = {
        "parameterUnit": "m/s",
        "parameterCategory": 2,
        "nx": nx,
        "ny": ny,
        "lo1": round(lo1, 4),
        "la1": round(la1, 4),
        "lo2": round(lo2, 4),
        "la2": round(la2, 4),
        "dx": round(abs(dx), 6),
        "dy": round(abs(dy), 6),
    }

    # Replace NaN with null-equivalent (0) for JSON
    u_flat = np.where(np.isnan(u), 0.0, u).flatten().tolist()
    v_flat = np.where(np.isnan(v), 0.0, v).flatten().tolist()

    return [
        {
            "header": {
                **header_common,
                "parameterNumber": u_param_num,
                "parameterNumberName": u_name,
            },
            "data": u_flat,
        },
        {
            "header": {
                **header_common,
                "parameterNumber": v_param_num,
                "parameterNumberName": v_name,
            },
            "data": v_flat,
        },
    ]


def build_scalar_json(
    values: np.ndarray,
    lons: np.ndarray,
    lats: np.ndarray,
    param_name: str,
    units: str,
) -> list[dict]:
    """Build a single-component scalar JSON (leaflet.canvaslayer.field compatible).

    Data must be on a regular grid (1D lon, 1D lat), lat[0] = northernmost.
    """
    ny, nx = values.shape
    lo1, lo2 = float(lons[0]), float(lons[-1])
    la1, la2 = float(lats[0]), float(lats[-1])
    dx = float(lons[1] - lons[0]) if nx > 1 else 1.0
    dy = float(lats[0] - lats[1]) if ny > 1 else 1.0

    data = np.where(np.isnan(values), 0.0, values).flatten().tolist()

    return [{
        "header": {
            "parameterUnit": units,
            "parameterCategory": 0,
            "parameterNumber": 0,
            "parameterNumberName": param_name,
            "nx": nx,
            "ny": ny,
            "lo1": round(lo1, 4),
            "la1": round(la1, 4),
            "lo2": round(lo2, 4),
            "la2": round(la2, 4),
            "dx": round(abs(dx), 6),
            "dy": round(abs(dy), 6),
        },
        "data": data,
    }]


def _extract_gfs_field(
    nc_path: Path, spec: dict, time_idx: int, step: int, precision: int,
) -> list[dict] | None:
    """Read one GFS layer spec at a single time step and return the JSON components."""
    import netCDF4

    if not nc_path.exists():
        print(f"⚠️  GFS file not found: {nc_path}")
        return None

    ds = netCDF4.Dataset(nc_path)
    try:
        lat_name = "latitude" if "latitude" in ds.variables else "lat"
        lon_name = "longitude" if "longitude" in ds.variables else "lon"
        raw_lat = ds[lat_name][:]
        raw_lon = ds[lon_name][:]

        level = spec.get("level")

        def _read(var_name: str) -> np.ndarray:
            var = ds[var_name]
            dims = var.dimensions
            if level is not None and "level" in dims:
                level_var = ds["level"][:]
                level_idx = int(np.argmin(np.abs(np.asarray(level_var) - level)))
                # Build a tuple of slices indexing the correct dims.
                idx: list = []
                for d in dims:
                    if d == "time":
                        idx.append(time_idx)
                    elif d == "level":
                        idx.append(level_idx)
                    else:
                        idx.append(slice(None, None, step))
                return np.asarray(var[tuple(idx)])
            else:
                idx = []
                for d in dims:
                    if d == "time":
                        idx.append(time_idx)
                    else:
                        idx.append(slice(None, None, step))
                return np.asarray(var[tuple(idx)])

        lon = np.asarray(raw_lon)[::step]
        lat = np.asarray(raw_lat)[::step]

        if spec["kind"] == "vector":
            u = _read(spec["u"])
            v = _read(spec["v"])
        else:
            scalar = _read(spec["var"])
    finally:
        ds.close()

    # GFS scans N→S already (la1 > la2) → no flip needed
    if lat[0] < lat[-1]:
        lat = lat[::-1]
        if spec["kind"] == "vector":
            u = np.flipud(u)
            v = np.flipud(v)
        else:
            scalar = np.flipud(scalar)

    if spec["kind"] == "vector":
        u = np.round(u, precision)
        v = np.round(v, precision)
        print(f"✅ GFS {spec['name']}: {len(lon)}x{len(lat)} grid, "
              f"lon=[{lon[0]:.1f},{lon[-1]:.1f}], lat=[{lat[0]:.1f},{lat[-1]:.1f}]")
        return build_velocity_json(
            u, v, lon, lat,
            u_name=spec.get("u_name", "u"),
            v_name=spec.get("v_name", "v"),
        )
    else:
        scalar = np.round(scalar, precision)
        print(f"✅ GFS {spec['name']}: {len(lon)}x{len(lat)} grid (scalar)")
        return build_scalar_json(
            scalar, lon, lat,
            param_name=spec.get("param_name", spec["var"]),
            units=spec["units"],
        )


def convert_current(nc_path: Path, time_idx: int, step: int, precision: int) -> list[dict] | None:
    """Convert current_fixed.nc → leaflet-velocity JSON."""
    import netCDF4

    if not nc_path.exists():
        print(f"⚠️  current file not found: {nc_path}")
        return None

    ds = netCDF4.Dataset(nc_path)
    try:
        lon = ds["lon"][::step]
        lat = ds["lat"][::step]
        u = ds["x_sea_water_velocity"][time_idx, ::step, ::step]
        v = ds["y_sea_water_velocity"][time_idx, ::step, ::step]
    finally:
        ds.close()

    # leaflet-velocity expects la1=north, data scanned N→S
    # Our lat goes 7→36 (S→N), so flip
    u = np.flipud(u)
    v = np.flipud(v)
    lat = lat[::-1]

    # Round for smaller file size
    u = np.round(u, precision)
    v = np.round(v, precision)

    print(f"✅ Current: {len(lon)}x{len(lat)} grid, "
          f"lon=[{lon[0]:.1f},{lon[-1]:.1f}], lat=[{lat[0]:.1f},{lat[-1]:.1f}]")

    return build_velocity_json(
        u, v, lon, lat,
        u_name="eastward_sea_water_velocity",
        v_name="northward_sea_water_velocity",
    )


def convert_wind(nc_path: Path, time_idx: int, step: int, precision: int) -> list[dict] | None:
    """Convert wind_fixed.nc → leaflet-velocity JSON.

    Wind data may be on a 2D (curvilinear) grid, so we regrid to a regular grid.
    """
    import netCDF4

    if not nc_path.exists():
        print(f"⚠️  wind file not found: {nc_path}")
        return None

    ds = netCDF4.Dataset(nc_path)
    try:
        raw_lat = ds["latitude"][:]
        raw_lon = ds["longitude"][:]
        u_raw = ds["x_wind"][time_idx, :, :]
        v_raw = ds["y_wind"][time_idx, :, :]
    finally:
        ds.close()

    # Check if lat/lon are 2D (curvilinear) → need regridding
    if raw_lat.ndim == 2:
        print("🌬️  Wind grid is curvilinear (2D lat/lon), regridding to regular grid...")
        from scipy.interpolate import griddata

        # Target regular grid covering Taiwan region with ~0.1° resolution
        lon_min, lon_max = 115.0, 130.0
        lat_min, lat_max = 18.0, 30.0
        res = 0.1 * step  # resolution scaled by step

        reg_lon = np.arange(lon_min, lon_max + res, res)
        reg_lat = np.arange(lat_max, lat_min - res, -res)  # N→S

        grid_lon, grid_lat = np.meshgrid(reg_lon, reg_lat)

        # Flatten source coordinates (convert masked arrays to plain numpy)
        src_lon = np.asarray(raw_lon).flatten()
        src_lat = np.asarray(raw_lat).flatten()
        src_u = np.asarray(u_raw).flatten()
        src_v = np.asarray(v_raw).flatten()

        # Remove NaN values
        valid = np.isfinite(src_u) & np.isfinite(src_v) & np.isfinite(src_lon) & np.isfinite(src_lat)

        src_points = np.column_stack([src_lon[valid], src_lat[valid]])

        u = griddata(src_points, src_u[valid], (grid_lon, grid_lat), method="linear")
        v = griddata(src_points, src_v[valid], (grid_lon, grid_lat), method="linear")

        # Fill remaining NaN with 0
        u = np.where(np.isnan(u), 0.0, u)
        v = np.where(np.isnan(v), 0.0, v)
        lon = reg_lon
        lat = reg_lat
    else:
        # 1D lat/lon (regular grid) - just subsample
        lon = raw_lon[::step]
        lat = raw_lat[::step]
        u = u_raw[::step, ::step]
        v = v_raw[::step, ::step]
        # Flip if lat is S→N
        if lat[0] < lat[-1]:
            u = np.flipud(u)
            v = np.flipud(v)
            lat = lat[::-1]

    u = np.round(u, precision)
    v = np.round(v, precision)

    print(f"✅ Wind: {len(lon)}x{len(lat)} grid, "
          f"lon=[{lon[0]:.1f},{lon[-1]:.1f}], lat=[{lat[0]:.1f},{lat[-1]:.1f}]")

    return build_velocity_json(
        u, v, lon, lat,
        u_name="eastward_wind",
        v_name="northward_wind",
    )


class CompactEncoder(json.JSONEncoder):
    """Write data arrays on single lines for compact output."""

    def encode(self, o):
        if isinstance(o, list) and len(o) == 2 and isinstance(o[0], dict):
            # Top-level: list of two components
            parts = []
            for component in o:
                header_json = json.dumps(component["header"], separators=(",", ":"))
                data_json = "[" + ",".join(
                    str(int(x)) if x == int(x) else str(x) for x in component["data"]
                ) + "]"
                parts.append('{"header":' + header_json + ',"data":' + data_json + "}")
            return "[" + ",\n" + parts[0] + ",\n" + parts[1] + "]"
        return super().encode(o)


def _read_time_axes(input_dir: Path) -> dict:
    """Inspect both NC files and return {current: {hours: [...]}, wind: {hours: [...]}} (lead times in hours)."""
    import netCDF4
    from datetime import datetime, timedelta, timezone
    info: dict = {}

    cpath = input_dir / "current_fixed.nc"
    if cpath.exists():
        ds = netCDF4.Dataset(cpath)
        try:
            t = ds["time"]
            units = getattr(t, "units", "")
            vals = [float(x) for x in t[:]]
            base = None
            if "since" in units:
                base_str = units.split("since", 1)[1].strip().rstrip("Z")
                base_str = base_str.replace("T", " ").split("+")[0].split(".")[0].strip()
                try:
                    base = datetime.fromisoformat(base_str).replace(tzinfo=timezone.utc)
                except ValueError:
                    base = None
            # convert vals to hours since first
            hours = [int(round(v - vals[0])) for v in vals]
            info["current"] = {
                "hours": hours,
                "base_time": base.isoformat() if base else None,
                "units": units,
            }
        finally:
            ds.close()

    wpath = input_dir / "wind_fixed.nc"
    if wpath.exists():
        ds = netCDF4.Dataset(wpath)
        try:
            base_time = None
            hours: list[int] = []
            if "valid_time" in ds.variables:
                vt = ds["valid_time"][:]
                vt_units = getattr(ds["valid_time"], "units", "seconds since 1970-01-01")
                from datetime import datetime as _dt
                if "seconds since 1970-01-01" in vt_units:
                    base_time = _dt.fromtimestamp(float(vt[0]), tz=timezone.utc).isoformat()
                    hours = [int(round((float(v) - float(vt[0])) / 3600.0)) for v in vt]
            elif "step" in ds.variables:
                st = ds["step"][:]
                hours = [int(round(float(v))) for v in st]
            else:
                t = ds["time"]
                hours = list(range(len(t)))
            info["wind"] = {
                "hours": hours,
                "base_time": base_time,
            }
        finally:
            ds.close()

    # GFS multi-level files — all three share the same time axis, so read once.
    for gfs_name in ("wind_gfs_fixed.nc", "temp_gfs_fixed.nc", "rh_gfs_fixed.nc"):
        gpath = input_dir / gfs_name
        if not gpath.exists():
            continue
        ds = netCDF4.Dataset(gpath)
        try:
            base_time = None
            hours = []
            if "valid_time" in ds.variables:
                vt = ds["valid_time"][:]
                vt_units = getattr(ds["valid_time"], "units", "seconds since 1970-01-01")
                from datetime import datetime as _dt
                if "seconds since 1970-01-01" in vt_units:
                    base_time = _dt.fromtimestamp(float(vt[0]), tz=timezone.utc).isoformat()
                    hours = [int(round((float(v) - float(vt[0])) / 3600.0)) for v in vt]
            elif "step" in ds.variables:
                st = ds["step"][:]
                hours = [int(round(float(v))) for v in st]
            elif "time" in ds.variables:
                hours = list(range(len(ds["time"])))
            info["gfs"] = {"hours": hours, "base_time": base_time}
            break
        finally:
            ds.close()

    return info


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.frames:
        return _emit_frames(args, input_dir, output_dir)

    # Convert current
    current_json = convert_current(
        input_dir / "current_fixed.nc", args.time_index, args.current_step, args.precision,
    )
    if current_json:
        dst = output_dir / "current_velocity.json"
        with open(dst, "w") as f:
            json.dump(current_json, f, separators=(",", ":"))
        size_kb = dst.stat().st_size / 1024
        print(f"📄 {dst}: {size_kb:.0f} KB")

    # Convert wind
    try:
        wind_json = convert_wind(
            input_dir / "wind_fixed.nc", args.time_index, args.wind_step, args.precision,
        )
        if wind_json:
            dst = output_dir / "wind_velocity.json"
            with open(dst, "w") as f:
                json.dump(wind_json, f, separators=(",", ":"))
            size_kb = dst.stat().st_size / 1024
            print(f"📄 {dst}: {size_kb:.0f} KB")
    except Exception as exc:
        print(f"⚠️  Wind conversion failed (non-fatal): {exc}")

    return 0


def _emit_frames(args, input_dir: Path, output_dir: Path) -> int:
    """Emit per-hour JSON frames into output_dir/frames/{current,wind}/h###.json.

    Also writes output_dir/frames/index.json with metadata so the frontend can
    build the timeline and lazy-fetch each hour on demand.
    """
    import json as _json

    frames_dir = output_dir / "frames"
    (frames_dir / "current").mkdir(parents=True, exist_ok=True)
    (frames_dir / "wind").mkdir(parents=True, exist_ok=True)

    axes = _read_time_axes(input_dir)
    max_h = args.max_hours

    index = {
        "max_hours": max_h,
        "current": {"base_time": None, "hours": [], "step": "h{:03d}.json"},
        "wind": {"base_time": None, "hours": [], "step": "h{:03d}.json"},
        "layers": {},
    }

    # ---- Current (typically hourly) ----
    if "current" in axes:
        c_axis = axes["current"]
        index["current"]["base_time"] = c_axis.get("base_time")
        for ti, hour in enumerate(c_axis["hours"]):
            if hour > max_h:
                break
            try:
                j = convert_current(
                    input_dir / "current_fixed.nc", ti, args.current_step, args.precision,
                )
            except Exception as exc:
                print(f"⚠️  current t{ti} failed: {exc}")
                continue
            if not j:
                continue
            dst = frames_dir / "current" / f"h{hour:03d}.json"
            with open(dst, "w") as f:
                _json.dump(j, f, separators=(",", ":"))
            index["current"]["hours"].append(hour)
            print(f"📄 current h{hour:03d}: {dst.stat().st_size/1024:.0f} KB")

    # ---- Wind (typically 6-hourly) ----
    if "wind" in axes:
        w_axis = axes["wind"]
        index["wind"]["base_time"] = w_axis.get("base_time")
        for ti, hour in enumerate(w_axis["hours"]):
            if hour > max_h:
                break
            try:
                j = convert_wind(
                    input_dir / "wind_fixed.nc", ti, args.wind_step, args.precision,
                )
            except Exception as exc:
                print(f"⚠️  wind t{ti} failed: {exc}")
                continue
            if not j:
                continue
            dst = frames_dir / "wind" / f"h{hour:03d}.json"
            with open(dst, "w") as f:
                _json.dump(j, f, separators=(",", ":"))
            index["wind"]["hours"].append(hour)
            print(f"📄 wind h{hour:03d}: {dst.stat().st_size/1024:.0f} KB")

    # ---- GFS multi-level wind / temperature / humidity ----
    if "gfs" in axes:
        gfs_axis = axes["gfs"]
        gfs_hours = gfs_axis["hours"]
        gfs_base = gfs_axis.get("base_time")

        for spec in GFS_LAYER_SPECS:
            nc_path = input_dir / spec["nc"]
            if not nc_path.exists():
                continue
            layer_dir = frames_dir / spec["name"]
            layer_dir.mkdir(parents=True, exist_ok=True)
            layer_hours: list[int] = []
            for ti, hour in enumerate(gfs_hours):
                if hour > max_h:
                    break
                try:
                    j = _extract_gfs_field(nc_path, spec, ti, args.gfs_step, args.precision)
                except Exception as exc:
                    print(f"⚠️  GFS {spec['name']} t{ti} failed: {exc}")
                    continue
                if not j:
                    continue
                dst = layer_dir / f"h{hour:03d}.json"
                with open(dst, "w") as f:
                    _json.dump(j, f, separators=(",", ":"))
                layer_hours.append(hour)
                print(f"📄 {spec['name']} h{hour:03d}: {dst.stat().st_size/1024:.0f} KB")

            index["layers"][spec["name"]] = {
                "type": spec["kind"],
                "base_time": gfs_base,
                "hours": layer_hours,
                "step": "h{:03d}.json",
                "units": spec.get("units", "m/s"),
                "level": spec.get("level"),
            }

    idx_path = frames_dir / "index.json"
    with open(idx_path, "w") as f:
        _json.dump(index, f, indent=2)
    print(f"📄 frames index → {idx_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
