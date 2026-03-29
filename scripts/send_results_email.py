#!/usr/bin/env python3
"""Send drift simulation results via SendGrid email API."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen


SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Email simulation results via SendGrid.")
    p.add_argument("--to", required=True, help="Recipient email address")
    p.add_argument("--results-dir", default="results", help="Directory containing result images and results.json")
    p.add_argument("--request-id", default="unknown", help="Unique request ID for tracking")
    p.add_argument("--from-email", default=None, help="Sender email (overrides SENDGRID_FROM_EMAIL env)")
    return p.parse_args()


def build_email_payload(
    from_email: str,
    to_email: str,
    request_id: str,
    results_dir: Path,
) -> dict:
    # Load results metadata
    results_json = results_dir / "results.json"
    metadata = {}
    if results_json.exists():
        metadata = json.loads(results_json.read_text(encoding="utf-8"))

    lon = metadata.get("lon", "N/A")
    lat = metadata.get("lat", "N/A")
    duration = metadata.get("duration_hours", "N/A")
    start_time = metadata.get("start_time", "N/A")
    timestamp = metadata.get("timestamp", "N/A")

    html_body = f"""\
<h2>Drift Simulation Results</h2>
<table border="1" cellpadding="6" cellspacing="0">
  <tr><td><b>Request ID</b></td><td>{request_id}</td></tr>
  <tr><td><b>Longitude</b></td><td>{lon}</td></tr>
  <tr><td><b>Latitude</b></td><td>{lat}</td></tr>
  <tr><td><b>Duration</b></td><td>{duration} hours</td></tr>
  <tr><td><b>Data Start Time</b></td><td>{start_time}</td></tr>
  <tr><td><b>Computed At</b></td><td>{timestamp}</td></tr>
</table>
<p>Simulation images are attached below.</p>
"""

    # Collect image attachments
    attachments = []
    for img_name in metadata.get("images", []):
        img_path = results_dir / img_name
        if img_path.exists():
            b64_data = base64.b64encode(img_path.read_bytes()).decode("ascii")
            attachments.append({
                "content": b64_data,
                "filename": img_name,
                "type": "image/png",
                "disposition": "attachment",
            })

    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": from_email, "name": "SeaCurrent Drift Simulator"},
        "subject": f"Drift Simulation Results - {request_id}",
        "content": [{"type": "text/html", "value": html_body}],
    }
    if attachments:
        payload["attachments"] = attachments

    return payload


def send_email(api_key: str, payload: dict) -> int:
    data = json.dumps(payload).encode("utf-8")
    req = Request(
        SENDGRID_API_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(req) as resp:
            status = resp.status
            print(f"SendGrid response: {status}")
            return 0 if 200 <= status < 300 else 1
    except Exception as exc:
        print(f"Failed to send email: {exc}")
        return 1


def main() -> int:
    args = parse_args()

    api_key = os.environ.get("SENDGRID_API_KEY", "")
    if not api_key:
        print("SENDGRID_API_KEY environment variable is not set.")
        return 1

    from_email = args.from_email or os.environ.get("SENDGRID_FROM_EMAIL", "noreply@seacurrent.dev")
    results_dir = Path(args.results_dir)

    if not results_dir.exists():
        print(f"Results directory not found: {results_dir}")
        return 1

    payload = build_email_payload(from_email, args.to, args.request_id, results_dir)
    return send_email(api_key, payload)


if __name__ == "__main__":
    sys.exit(main())
