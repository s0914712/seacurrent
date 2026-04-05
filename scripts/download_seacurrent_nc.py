#!/usr/bin/env python3
"""Download all public sea-current related .nc files from CWA OpenData S3 bucket."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

BUCKET_BASE = "https://cwaopendata.s3.ap-northeast-1.amazonaws.com"
DEFAULT_PREFIX = "Model/"
FALLBACK_KEYS = ["Model/M-B0071-000.nc"]

# Wind forecast GRIB2 files (M-A0064, every 6 hours, 0-84h)
WIND_BASE_URL = f"{BUCKET_BASE}/Model/M-A0064-"
WIND_HOURS = range(0, 85, 6)  # 0, 6, 12, ..., 84 → 15 files


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Download sea-current related NetCDF files from CWA OpenData."
    )
    p.add_argument("--output", default="data/nc_files", help="Directory to store .nc files")
    p.add_argument("--prefix", default=DEFAULT_PREFIX, help="S3 prefix to list")
    p.add_argument(
        "--keyword",
        action="append",
        default=["M-B0071", "current", "sea", "ocean", "海流"],
        help="Keyword filter for key names. Repeat to add more.",
    )
    p.add_argument("--all-nc", action="store_true", help="Download all .nc files")
    p.add_argument("--wind", action="store_true", help="Also download wind GRIB2 files (M-A0064)")
    p.add_argument("--wind-output", default="data/grib2_files", help="Directory for wind GRIB2 files")
    p.add_argument("--force", action="store_true", help="Always re-download")
    p.add_argument("--timeout", type=int, default=30, help="HTTP timeout seconds")
    return p.parse_args()


def http_get_text(url: str, timeout: int) -> str:
    req = Request(url, headers={"User-Agent": "seacurrent-downloader/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def list_keys(prefix: str, timeout: int) -> list[dict[str, str | int]]:
    token: str | None = None
    objects: list[dict[str, str | int]] = []

    while True:
        params = {"list-type": "2", "prefix": prefix}
        if token:
            params["continuation-token"] = token
        query = urlencode(params)
        text = http_get_text(f"{BUCKET_BASE}?{query}", timeout)

        root = ET.fromstring(text)
        ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}

        for content in root.findall("s3:Contents", ns):
            key = content.findtext("s3:Key", default="", namespaces=ns)
            size_str = content.findtext("s3:Size", default="0", namespaces=ns)
            try:
                size = int(size_str)
            except ValueError:
                size = 0
            if key:
                objects.append({"key": key, "size": size})

        is_truncated = root.findtext("s3:IsTruncated", default="false", namespaces=ns)
        if is_truncated.lower() != "true":
            break
        token = root.findtext("s3:NextContinuationToken", default=None, namespaces=ns)
        if not token:
            break

    return objects


def is_target_key(key: str, keywords: Iterable[str], all_nc: bool) -> bool:
    if not key.lower().endswith(".nc"):
        return False
    if all_nc:
        return True
    lower = key.lower()
    return any(k.lower() in lower for k in keywords)


def remote_file_size(url: str, timeout: int) -> int | None:
    try:
        req = Request(url, method="HEAD", headers={"User-Agent": "seacurrent-downloader/1.0"})
        with urlopen(req, timeout=timeout) as resp:
            cl = resp.headers.get("Content-Length")
            return int(cl) if cl and cl.isdigit() else None
    except Exception:  # noqa: BLE001
        return None


def download_file(url: str, dest: Path, timeout: int) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = Request(url, headers={"User-Agent": "seacurrent-downloader/1.0"})
    with urlopen(req, timeout=timeout) as resp, dest.open("wb") as f:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)


def build_url(key: str) -> str:
    return f"{BUCKET_BASE}/{quote(key)}"


def download_wind_files(out_dir: Path, timeout: int, force: bool) -> tuple[int, int, int]:
    """Download CWA wind forecast GRIB2 files (M-A0064-000 ~ M-A0064-084)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    downloaded = skipped = failed = 0
    manifest: list[dict[str, str | int]] = []

    for hour in WIND_HOURS:
        filename = f"M-A0064-{hour:03d}.grb2"
        url = f"{WIND_BASE_URL}{hour:03d}.grb2"
        local = out_dir / filename

        remote_size = remote_file_size(url, timeout)
        if (
            not force
            and local.exists()
            and remote_size is not None
            and local.stat().st_size == remote_size
        ):
            print(f"⏭️ 跳過（已存在）：{filename}")
            skipped += 1
        else:
            print(f"⬇️ 下載風場：{filename}")
            try:
                download_file(url, local, timeout)
                downloaded += 1
            except Exception as exc:  # noqa: BLE001
                print(f"❌ 下載失敗：{filename} ({exc})")
                failed += 1

        manifest.append({
            "filename": filename,
            "url": url,
            "local": str(local),
            "size": local.stat().st_size if local.exists() else 0,
        })

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps({"source": "wind-grib2", "count": len(manifest), "files": manifest},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return downloaded, skipped, failed


def main() -> int:
    args = parse_args()
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        objects = list_keys(args.prefix, args.timeout)
        source = "bucket-list"
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ 無法列出 S3 清單，改用備援清單：{exc}")
        objects = [{"key": k, "size": 0} for k in FALLBACK_KEYS]
        source = "fallback"

    targets = [
        {"key": obj["key"], "size": int(obj.get("size", 0))}
        for obj in objects
        if is_target_key(str(obj["key"]), args.keyword, args.all_nc)
    ]

    if not targets:
        print("找不到符合條件的 .nc 檔案。")
        return 0

    downloaded = 0
    skipped = 0
    manifest: list[dict[str, str | int]] = []
    failed = 0

    for item in sorted(targets, key=lambda x: str(x["key"])):
        key = str(item["key"])
        url = build_url(key)
        filename = Path(key).name
        local = out_dir / filename

        remote_size = int(item["size"]) if int(item["size"]) > 0 else remote_file_size(url, args.timeout)
        if (
            not args.force
            and local.exists()
            and remote_size is not None
            and local.stat().st_size == remote_size
        ):
            print(f"⏭️ 跳過（已存在且大小一致）：{filename}")
            skipped += 1
        else:
            print(f"⬇️ 下載：{key}")
            try:
                download_file(url, local, args.timeout)
                downloaded += 1
            except Exception as exc:  # noqa: BLE001
                print(f"❌ 下載失敗：{key} ({exc})")
                failed += 1

        manifest.append(
            {
                "key": key,
                "url": url,
                "local": str(local),
                "size": local.stat().st_size if local.exists() else 0,
            }
        )

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "source": source,
                "prefix": args.prefix,
                "count": len(manifest),
                "files": manifest,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"✅ 完成。下載 {downloaded} 個、跳過 {skipped} 個、失敗 {failed} 個。")
    print(f"📄 清單：{manifest_path}")

    if args.wind:
        print(f"\n🌬️ 開始下載風場 GRIB2 檔案...")
        w_down, w_skip, w_fail = download_wind_files(
            Path(args.wind_output), args.timeout, args.force,
        )
        print(f"✅ 風場完成。下載 {w_down} 個、跳過 {w_skip} 個、失敗 {w_fail} 個。")
        failed += w_fail

    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
