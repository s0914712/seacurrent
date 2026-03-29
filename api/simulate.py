"""Vercel serverless function: trigger drift simulation via GitHub Actions."""

from http.server import BaseHTTPRequestHandler
import json
import os
import uuid
from urllib.request import Request, urlopen


GITHUB_API = "https://api.github.com"
REPO = "s0914712/seacurrent"
WORKFLOW_FILE = "run-simulation.yml"
CLOUD_RUN_URL = "https://opendrift-leeway-1087471739366.europe-west1.run.app"


def trigger_github_actions(lon: float, lat: float, duration: int, email: str, request_id: str) -> dict:
    """Trigger the run-simulation workflow via GitHub API workflow_dispatch."""
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return {"error": "GITHUB_TOKEN not configured", "status_code": 500}

    url = f"{GITHUB_API}/repos/{REPO}/actions/workflows/{WORKFLOW_FILE}/dispatches"
    payload = {
        "ref": "main",
        "inputs": {
            "lon": str(lon),
            "lat": str(lat),
            "duration": str(duration),
            "email": email,
            "request_id": request_id,
        },
    }

    data = json.dumps(payload).encode("utf-8")
    req = Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )

    try:
        with urlopen(req) as resp:
            if 200 <= resp.status < 300:
                return {"ok": True, "status_code": resp.status}
            return {"error": f"GitHub API returned {resp.status}", "status_code": resp.status}
    except Exception as exc:
        return {"error": str(exc), "status_code": 502}


def fallback_cloud_run(lon: float, lat: float, duration: int) -> dict:
    """Fallback: call existing Cloud Run backend for immediate results."""
    payload = json.dumps({"lon": lon, "lat": lat, "duration": duration}).encode("utf-8")
    req = Request(
        CLOUD_RUN_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=300) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return {"error": f"Cloud Run fallback failed: {exc}"}


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._respond(400, {"error": "Invalid JSON"})
            return

        lon = data.get("lon")
        lat = data.get("lat")
        duration = data.get("duration")
        email = data.get("email", "")
        mode = data.get("mode", "email")  # "email" or "instant"

        # Validate required fields
        if lon is None or lat is None or duration is None:
            self._respond(400, {"error": "Missing required fields: lon, lat, duration"})
            return

        try:
            lon = float(lon)
            lat = float(lat)
            duration = int(duration)
        except (ValueError, TypeError):
            self._respond(400, {"error": "Invalid field types"})
            return

        if duration < 1 or duration > 168:
            self._respond(400, {"error": "Duration must be between 1 and 168 hours"})
            return

        # Instant mode: proxy to Cloud Run
        if mode == "instant":
            result = fallback_cloud_run(lon, lat, duration)
            self._respond(200, result)
            return

        # Email mode: trigger GitHub Actions
        if not email:
            self._respond(400, {"error": "Email is required for email mode"})
            return

        request_id = str(uuid.uuid4())[:8]
        result = trigger_github_actions(lon, lat, duration, email, request_id)

        if result.get("ok"):
            self._respond(200, {
                "status": "queued",
                "request_id": request_id,
                "message": f"Simulation queued. Results will be emailed to {email}.",
            })
        else:
            # Fallback to Cloud Run on GitHub API failure
            print(f"GitHub Actions trigger failed: {result.get('error')}, falling back to Cloud Run")
            cr_result = fallback_cloud_run(lon, lat, duration)
            cr_result["fallback"] = True
            cr_result["note"] = "GitHub Actions unavailable, using Cloud Run instant mode"
            self._respond(200, cr_result)

    def _respond(self, status: int, data: dict):
        self.send_response(status)
        self._set_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def _set_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
