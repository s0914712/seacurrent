"""Vercel serverless function: trigger drift simulation via GitHub Actions."""

from http.server import BaseHTTPRequestHandler
import json
import os
import uuid
from urllib.request import Request, urlopen


GITHUB_API = "https://api.github.com"
REPO = "s0914712/seacurrent"
WORKFLOW_FILE = "run-simulation.yml"

VALID_MODEL_TYPES = {"leeway", "oceandrift", "openoil"}
ALLOWED_MODEL_PARAMS = {
    "leeway": ["object_type"],
    "oceandrift": ["wind_drift_factor"],
    "openoil": ["oil_type", "amount"],
}


def extract_model_params(data: dict, model_type: str) -> dict:
    """Extract only whitelisted model-specific params from the request."""
    allowed = ALLOWED_MODEL_PARAMS.get(model_type, [])
    return {k: data[k] for k in allowed if k in data}


def trigger_github_actions(
    lon: float, lat: float, duration: int, email: str,
    request_id: str, model_type: str, model_params: dict,
) -> dict:
    """Trigger the run-simulation workflow via GitHub API workflow_dispatch."""
    token = os.environ.get("MyGIT_TOKEN", "")
    if not token:
        return {"error": "MyGIT_TOKEN not configured", "status_code": 500}

    url = f"{GITHUB_API}/repos/{REPO}/actions/workflows/{WORKFLOW_FILE}/dispatches"
    payload = {
        "ref": "main",
        "inputs": {
            "lon": str(lon),
            "lat": str(lat),
            "duration": str(duration),
            "email": email,
            "request_id": request_id,
            "model_type": model_type,
            "model_params": json.dumps(model_params),
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
        model_type = data.get("model_type", "leeway")

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

        if model_type not in VALID_MODEL_TYPES:
            self._respond(400, {"error": f"Invalid model_type. Must be one of: {', '.join(VALID_MODEL_TYPES)}"})
            return

        if not email:
            self._respond(400, {"error": "Email is required. Results will be sent to your email."})
            return

        model_params = extract_model_params(data, model_type)

        request_id = str(uuid.uuid4())[:8]
        result = trigger_github_actions(lon, lat, duration, email, request_id, model_type, model_params)

        if result.get("ok"):
            self._respond(200, {
                "status": "queued",
                "request_id": request_id,
                "model_type": model_type,
                "message": f"Simulation queued. Results will be emailed to {email}.",
            })
        else:
            self._respond(502, {
                "error": f"Failed to trigger simulation: {result.get('error')}",
            })

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
