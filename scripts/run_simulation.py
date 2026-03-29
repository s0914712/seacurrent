#!/usr/bin/env python3
"""Run OpenDrift Leeway drift simulation and save results."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run Leeway drift simulation.")
    p.add_argument("--lon", type=float, required=True, help="Longitude of seed point")
    p.add_argument("--lat", type=float, required=True, help="Latitude of seed point")
    p.add_argument("--duration", type=int, default=12, help="Simulation duration in hours")
    p.add_argument("--nc-dir", default="data/nc_converted", help="Directory with converted NC files")
    p.add_argument("--output-dir", default="results", help="Directory for output images/data")
    p.add_argument("--object-type", type=int, default=26, help="Leeway object type (26=life raft, no ballast)")
    p.add_argument("--num-elements", type=int, default=500, help="Number of drift elements to seed")
    p.add_argument("--radius", type=int, default=1000, help="Seed radius in meters")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    import matplotlib
    matplotlib.use("Agg")

    from opendrift.models.leeway import Leeway
    from opendrift.readers import reader_netCDF_CF_generic

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    nc_dir = Path(args.nc_dir)

    # Find all NC files
    nc_files = sorted(nc_dir.glob("*.nc"))
    if not nc_files:
        print(f"No .nc files found in {nc_dir}")
        return 1

    # Initialize Leeway model
    o = Leeway(loglevel=20)

    # Load readers
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

    o.add_reader(readers)

    # Fallback values for missing data
    o.set_config("environment:fallback:x_sea_water_velocity", 0)
    o.set_config("environment:fallback:y_sea_water_velocity", 0)
    o.set_config("environment:fallback:x_wind", 0)
    o.set_config("environment:fallback:y_wind", 0)

    # Seed elements
    o.seed_elements(
        lon=args.lon,
        lat=args.lat,
        number=args.num_elements,
        radius=args.radius,
        time=readers[0].start_time,
        object_type=args.object_type,
    )

    print(f"Seeded {args.num_elements} elements at ({args.lon}, {args.lat})")
    print(f"Simulation start: {readers[0].start_time}, duration: {args.duration}h")

    # Run simulation
    o.run(
        duration=timedelta(hours=args.duration),
        time_step=1800,
        time_step_output=3600,
    )

    # Save trajectory plot
    trajectory_path = str(output_dir / "trajectory.png")
    o.plot(filename=trajectory_path, fast=True)
    print(f"Saved trajectory plot: {trajectory_path}")

    # Save results metadata
    results = {
        "lon": args.lon,
        "lat": args.lat,
        "duration_hours": args.duration,
        "object_type": args.object_type,
        "num_elements": args.num_elements,
        "start_time": str(readers[0].start_time),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "images": ["trajectory.png"],
    }

    results_path = output_dir / "results.json"
    results_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved results metadata: {results_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
