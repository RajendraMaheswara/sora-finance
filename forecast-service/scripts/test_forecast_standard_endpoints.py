#!/usr/bin/env python3
"""Smoke-test standar forecast endpoints.

Contoh single ingredient:
python scripts/test_forecast_standard_endpoints.py \
  --base-url http://localhost:5000 \
  --service-key "$INTERNAL_SERVICE_KEY" \
  --store-id b4e2f559-9615-4263-84fe-9ee97780748f \
  --ingredient-id b98b5042-30b5-4dc7-80ce-7dbb4797c4c7

Contoh semua ingredient dalam store:
python scripts/test_forecast_standard_endpoints.py \
  --base-url http://localhost:5000 \
  --service-key "$INTERNAL_SERVICE_KEY" \
  --store-id b4e2f559-9615-4263-84fe-9ee97780748f
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

HORIZONS = ["daily", "weekly", "monthly"]
MODULES = ["visitors", "sales", "inventory"]


@dataclass
class TestResult:
    module: str
    horizon: str
    endpoint: str
    ok: bool
    status_code: int
    message: str


def build_payload(module: str, store_id: str, ingredient_id: Optional[str], horizon: str) -> Dict[str, Any]:
    payload = {
        "store_id": store_id,
        "horizon_label": horizon,
        "horizon_count": 1,
    }
    if module == "inventory" and ingredient_id:
        payload["ingredient_id"] = ingredient_id
    return payload


def post_json(base_url: str, service_key: str, path: str, payload: Dict[str, Any]) -> requests.Response:
    headers = {"Content-Type": "application/json"}
    if service_key:
        headers["X-Service-Key"] = service_key
    return requests.post(f"{base_url.rstrip('/')}{path}", headers=headers, json=payload, timeout=120)


def check_envelope(data: Dict[str, Any], *, expect_save: bool) -> Optional[str]:
    for field in ("status", "message", "request", "data"):
        if field not in data:
            return f"missing response field: {field}"
    if data.get("status") not in ("success", "partial_success"):
        return f"unexpected status: {data.get('status')}"
    if expect_save and "save_result" not in data:
        return "missing save_result"
    if expect_save and data.get("save_result", {}).get("status") != "saved":
        return f"save_result not saved: {data.get('save_result')}"
    return None


def run_tests(args: argparse.Namespace) -> List[TestResult]:
    results: List[TestResult] = []
    for module in MODULES:
        for horizon in HORIZONS:
            payload = build_payload(module, args.store_id, args.ingredient_id, horizon)
            for action, expected_code, expect_save in (("preview", 200, False), ("save", 201, True)):
                path = f"/api/forecast/{module}/{action}"
                try:
                    response = post_json(args.base_url, args.service_key, path, payload)
                    try:
                        body = response.json()
                    except json.JSONDecodeError:
                        body = {"raw": response.text}

                    error = None
                    expected_codes = {expected_code}
                    if module == "inventory":
                        expected_codes.add(207)
                    if response.status_code not in expected_codes:
                        error = f"expected one of {sorted(expected_codes)}, got {response.status_code}: {body}"
                    elif isinstance(body, dict):
                        error = check_envelope(body, expect_save=expect_save)
                    else:
                        error = f"response is not object: {body}"

                    results.append(TestResult(module, horizon, action, error is None, response.status_code, error or "OK"))
                except Exception as exc:
                    results.append(TestResult(module, horizon, action, False, 0, str(exc)))

            run_path = f"/api/forecast/{module}/run"
            try:
                response = post_json(args.base_url, args.service_key, run_path, payload)
                ok = response.status_code == 404
                results.append(TestResult(module, horizon, "run_removed", ok, response.status_code, "OK" if ok else "endpoint /run masih aktif atau tidak 404"))
            except Exception as exc:
                results.append(TestResult(module, horizon, "run_removed", False, 0, str(exc)))
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:5000")
    parser.add_argument("--service-key", default="")
    parser.add_argument("--store-id", required=True)
    parser.add_argument("--ingredient-id", default=None)
    args = parser.parse_args()

    results = run_tests(args)
    failed = [r for r in results if not r.ok]

    for r in results:
        mark = "PASS" if r.ok else "FAIL"
        print(f"[{mark}] {r.module:9s} {r.horizon:7s} {r.endpoint:11s} HTTP={r.status_code} {r.message}")

    print(f"\nTotal: {len(results)} | Passed: {len(results) - len(failed)} | Failed: {len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
