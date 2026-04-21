"""Vercel serverless proxy for CWA Tide forecast (F-A0021-001).

Keeps the CWA authorization key (``CWAAUTHCODE``) server-side and forwards
whitelisted query parameters to the Central Weather Administration's tide
forecast endpoint. Supports pagination (``limit`` / ``offset``) and the
other filters documented in the F-A0021-001 swagger page.
"""

from http.server import BaseHTTPRequestHandler
import json
import os
from urllib.parse import parse_qs, urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


CWA_TIDE_URL = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-A0021-001"

SCALAR_PARAMS = {"limit", "offset", "format", "timeFrom", "timeTo"}
ARRAY_PARAMS = {
    "LocationName",
    "LocationId",
    "WeatherElement",
    "TideRange",
    "sort",
    "Date",
    "hhmmss",
}


def build_cwa_url(query: dict, auth: str) -> str:
    """Translate incoming query parameters into a CWA request URL.

    ``query`` is the dict returned by ``urllib.parse.parse_qs`` (values are
    lists). CWA expects repeated query parameters for array-valued filters,
    which ``urlencode(..., doseq=True)`` produces directly.
    """

    params = [("Authorization", auth)]

    if "format" not in query:
        params.append(("format", "JSON"))

    for key, values in query.items():
        if not values:
            continue
        if key in SCALAR_PARAMS:
            params.append((key, values[-1]))
        elif key in ARRAY_PARAMS:
            for v in values:
                # The front-end may pass either repeated params or a single
                # comma-joined string; both forms are flattened here.
                for item in str(v).split(","):
                    item = item.strip()
                    if item:
                        params.append((key, item))

    return f"{CWA_TIDE_URL}?{urlencode(params)}"


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self):
        auth = os.environ.get("CWAAUTHCODE", "")
        if not auth:
            self._respond(500, {"error": "CWAAUTHCODE not configured"})
            return

        query_string = ""
        if "?" in self.path:
            query_string = self.path.split("?", 1)[1]
        query = parse_qs(query_string, keep_blank_values=False)

        url = build_cwa_url(query, auth)

        req = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "seacurrent-tide-proxy/1.0",
            },
            method="GET",
        )

        try:
            with urlopen(req, timeout=15) as resp:
                body = resp.read()
                status = resp.status
        except HTTPError as exc:
            self._respond(exc.code, {"error": f"CWA API error: {exc.reason}"})
            return
        except URLError as exc:
            self._respond(502, {"error": f"Upstream request failed: {exc.reason}"})
            return
        except Exception as exc:  # noqa: BLE001
            self._respond(502, {"error": str(exc)})
            return

        self.send_response(status)
        self._set_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "public, max-age=300")
        self.end_headers()
        self.wfile.write(body)

    def _respond(self, status: int, data: dict):
        self.send_response(status)
        self._set_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def _set_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
