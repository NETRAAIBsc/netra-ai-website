#!/usr/bin/env python3
"""Update NETRA holder count and write data/holders.json."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

CONTRACT = "0xd70cE44E1e7fe884235ECCbb47C262c353D2F2e7"
DATA_FILE = Path("data/holders.json")
API_KEY = os.getenv("ETHERSCAN_API_KEY", "").strip()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; NETRA-AI-Holders/1.0; +https://netraai.xyz)",
    "Accept": "application/json,text/plain,text/html,*/*",
}

def fetch_text(url: str, timeout: int = 25) -> str:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")

def official_api() -> tuple[int, str] | None:
    if not API_KEY:
        return None

    params = urllib.parse.urlencode({
        "chainid": "56",
        "module": "token",
        "action": "tokenholdercount",
        "contractaddress": CONTRACT,
        "apikey": API_KEY,
    })
    raw = fetch_text("https://api.etherscan.io/v2/api?" + params)
    payload = json.loads(raw)

    if str(payload.get("status")) == "1":
        value = int(str(payload["result"]).replace(",", ""))
        if value >= 0:
            return value, "Etherscan API V2"
    return None

def parse_holder_count(text: str) -> int | None:
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&#160;", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text)

    patterns = [
        r"Holders?\s*[:\-]?\s*([0-9][0-9,]*)",
        r"([0-9][0-9,]*)\s+Holders?",
        r"Token\s+Holders?[^0-9]{0,100}([0-9][0-9,]*)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            value = int(match.group(1).replace(",", ""))
            if 0 <= value < 1_000_000_000:
                return value
    return None

def public_fallback() -> tuple[int, str] | None:
    urls = [
        f"https://r.jina.ai/http://bscscan.com/token/{CONTRACT}",
        f"https://bscscan.com/token/{CONTRACT}",
    ]
    for url in urls:
        try:
            count = parse_holder_count(fetch_text(url))
            if count is not None:
                return count, "BscScan public page"
        except Exception as exc:
            print(f"Fallback failed for {url}: {exc}", file=sys.stderr)
    return None

def read_previous() -> dict:
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def main() -> int:
    result = None

    try:
        result = official_api()
    except Exception as exc:
        print(f"Official API failed: {exc}", file=sys.stderr)

    if result is None:
        result = public_fallback()

    if result is None:
        previous = read_previous()
        if isinstance(previous.get("holders"), int):
            print("No fresh holder count; preserving previous data.")
            return 0
        print("Unable to obtain holder count.", file=sys.stderr)
        return 1

    holders, source = result
    payload = {
        "contract": CONTRACT,
        "chain": "BNB Smart Chain",
        "holders": holders,
        "updated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": source,
    }

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
