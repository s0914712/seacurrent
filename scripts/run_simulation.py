#!/usr/bin/env python3
"""Run OpenDrift drift simulation (Leeway / OceanDrift / OpenOil) and save results."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

MODEL_LABELS = {
    "leeway": "Person Overboard",
    "oceandrift": "Marine Debris",
    "openoil": "Oil Spill",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run OpenDrift drift simulation.")
    p.add_argument("--lon", type=float, required=True, help="Longitude of seed point")
    p.add_argument("--lat", type=float, required=True, help="Latitude of seed point")
    p.add_argument("--duration", type=int, default=12, help="Simulation duration in hours")
    p.add_argument("--nc-dir", default="data/nc_converted", help="Directory with converted NC files")
    p.add_argument("--output-dir", default="results", help="Directory for output images/data")
    p.add_argument("--num-elements", type=int, default=500, help="Number of drift elements to seed")
    p.add_argument("--radius", type=int, default=1000, help="Seed radius in meters")
    p.add_argument(
        "--model-type",
        choices=["leeway", "oceandrift", "openoil"],
        default="leeway",
        help="OpenDrift model type",
    )
    p.add_argument(
        "--model-params",
        default="{}",
        help="JSON string of model-specific parameters",
    )
    return p.parse_args()


def create_model(model_type: str):
    """Import and instantiate the appropriate OpenDrift model."""
    if model_type == "leeway":
        from opendrift.models.leeway import Leeway
        return Leeway(loglevel=20)
    elif model_type == "oceandrift":
        from opendrift.models.oceandrift import OceanDrift
        o = OceanDrift(loglevel=20)
        o.set_config("drift:horizontal_diffusivity", 10)
        return o
    elif model_type == "openoil":
        from opendrift.models.openoil import OpenOil
        o = OpenOil(loglevel=20)
        o.set_config("environment:fallback:land_binary_mask", 0)
        return o
    else:
        raise ValueError(f"Unknown model type: {model_type}")


def seed_model(o, model_type: str, params: dict, lon: float, lat: float,
               num_elements: int, radius: int, start_time):
    """Seed elements with model-specific parameters."""
    if model_type == "leeway":
        object_type = int(params.get("object_type", 26))
        o.seed_elements(
            lon=lon, lat=lat,
            number=num_elements, radius=radius,
            time=start_time,
            object_type=object_type,
        )
    elif model_type == "oceandrift":
        wind_drift_factor = float(params.get("wind_drift_factor", 0.02))
        o.seed_elements(
            lon=lon, lat=lat,
            number=num_elements, radius=radius,
            time=start_time,
            wind_drift_factor=wind_drift_factor,
        )
    elif model_type == "openoil":
        oil_type = params.get("oil_type", "GENERIC MEDIUM CRUDE")
        amount = float(params.get("amount", 100))
        o.seed_elements(
            lon=lon, lat=lat,
            number=num_elements, radius=radius,
            time=start_time,
            oil_type=oil_type,
            amount=amount,
        )


def main() -> int:
    args = parse_args()
    model_params = json.loads(args.model_params)

    import matplotlib
    matplotlib.use("Agg")

    from opendrift.readers import reader_netCDF_CF_generic

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    nc_dir = Path(args.nc_dir)

    # Find all NC files
    nc_files = sorted(nc_dir.glob("*.nc"))
    if not nc_files:
        print(f"No .nc files found in {nc_dir}")
        return 1

    # Initialize model
    print(f"Model: {MODEL_LABELS.get(args.model_type, args.model_type)}")
    o = create_model(args.model_type)

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
    seed_model(
        o, args.model_type, model_params,
        args.lon, args.lat, args.num_elements, args.radius,
        readers[0].start_time,
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
        "model_type": args.model_type,
        "model_label": MODEL_LABELS.get(args.model_type, args.model_type),
        "model_params": model_params,
        "lon": args.lon,
        "lat": args.lat,
        "duration_hours": args.duration,
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
