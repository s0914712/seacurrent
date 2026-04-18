#!/usr/bin/env python3
"""Run scheduled drift simulations for predefined Taiwan monitoring points."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

from run_simulation import export_trajectory_geojson


# 5 monitoring points around Taiwan
MONITORING_POINTS = [
    {"id": "keelung",    "name": "Keelung",             "name_zh": "基隆外海",   "lon": 121.75, "lat": 25.20},
    {"id": "kaohsiung",  "name": "Kaohsiung",           "name_zh": "高雄外海",   "lon": 120.25, "lat": 22.50},
    {"id": "hualien",    "name": "Hualien",             "name_zh": "花蓮外海",   "lon": 121.70, "lat": 24.00},
    {"id": "penghu",     "name": "Penghu Channel",      "name_zh": "澎湖水道",   "lon": 119.60, "lat": 23.50},
    {"id": "taitung",    "name": "Taitung / Green Isl.", "name_zh": "台東綠島",   "lon": 121.50, "lat": 22.65},
    {"id": "hengchun",   "name": "Hengchun / Bashi",    "name_zh": "恆春巴士海峽", "lon": 120.7723, "lat": 21.6881},
]

DURATION_HOURS = 24
NUM_ELEMENTS = 300


def main() -> int:
    import matplotlib
    matplotlib.use("Agg")

    from opendrift.models.leeway import Leeway
    from opendrift.readers import reader_netCDF_CF_generic

    nc_dir = Path("data/nc_converted")
    output_dir = Path("scheduled_results")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load readers once
    nc_files = sorted(nc_dir.glob("*.nc"))
    if not nc_files:
        print(f"No .nc files found in {nc_dir}")
        return 1

    readers = []
    for nc_file in nc_files:
        try:
            reader = reader_netCDF_CF_generic.Reader(str(nc_file))
            readers.append(reader)
            print(f"Loaded reader: {nc_file.name}")
        except Exception as exc:
            print(f"Warning: could not load {nc_file.name}: {exc}")

    if not readers:
        print("No valid readers loaded.")
        return 1

    start_time = readers[0].start_time
    all_results = []

    for point in MONITORING_POINTS:
        print(f"\n{'='*60}")
        print(f"Running simulation for {point['name']} ({point['name_zh']})")
        print(f"  Location: ({point['lon']}, {point['lat']})")
        print(f"{'='*60}")

        try:
            o = Leeway(loglevel=20)
            o.add_reader(readers)

            o.set_config("environment:fallback:x_sea_water_velocity", 0)
            o.set_config("environment:fallback:y_sea_water_velocity", 0)
            o.set_config("environment:fallback:x_wind", 0)
            o.set_config("environment:fallback:y_wind", 0)

            o.seed_elements(
                lon=point["lon"],
                lat=point["lat"],
                number=NUM_ELEMENTS,
                radius=1000,
                time=start_time,
                object_type=26,
            )

            o.run(
                duration=timedelta(hours=DURATION_HOURS),
                time_step=1800,
                time_step_output=3600,
            )

            # Save trajectory image
            img_name = f"{point['id']}.png"
            img_path = str(output_dir / img_name)
            o.plot(filename=img_path, fast=True)
            print(f"Saved: {img_path}")

            # Save GeoJSON for interactive map
            geojson_name = f"{point['id']}.geojson"
            geojson = export_trajectory_geojson(o, "leeway")
            (output_dir / geojson_name).write_text(
                json.dumps(geojson, ensure_ascii=False), encoding="utf-8",
            )
            print(f"Saved: {geojson_name}")

            all_results.append({
                "id": point["id"],
                "name": point["name"],
                "name_zh": point["name_zh"],
                "lon": point["lon"],
                "lat": point["lat"],
                "image": img_name,
                "geojson": geojson_name,
                "status": "ok",
            })

        except Exception as exc:
            print(f"FAILED for {point['name']}: {exc}")
            all_results.append({
                "id": point["id"],
                "name": point["name"],
                "name_zh": point["name_zh"],
                "lon": point["lon"],
                "lat": point["lat"],
                "image": None,
                "status": f"error: {exc}",
            })

    # Write manifest
    manifest = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "data_start_time": str(start_time),
        "duration_hours": DURATION_HOURS,
        "model": "Leeway (Person Overboard)",
        "points": all_results,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nManifest saved: {manifest_path}")

    ok_count = sum(1 for r in all_results if r["status"] == "ok")
    print(f"\nDone: {ok_count}/{len(MONITORING_POINTS)} simulations succeeded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
