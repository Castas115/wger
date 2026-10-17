#!/usr/bin/env python3
"""Push program.yaml into a wger instance via the REST API.

Env vars:
  WGER_URL        base URL, default https://wger.lan.home
  WGER_TOKEN      API token (DRF "Token" auth) - required unless --dry-run
  WGER_INSECURE   "1" (default) skips TLS verification for the home-ca cert

Usage:
  python3 scripts/import_wger_routine.py --dry-run
  WGER_TOKEN=xxx python3 scripts/import_wger_routine.py
"""
import argparse
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
BLOCK_ORDER = ["B1", "B2", "B3", "B4", "B5"]
WEEK_ORDER = ["W1", "W2", "W3", "W4"]
CELL_RE = re.compile(r"^(\d+)x([\d.]+)(?:-([\d.]+))?\s*@([\d.]+)$")


def parse_cell(cell):
    m = CELL_RE.match(cell.strip())
    if not m:
        raise ValueError(f"bad cell: {cell!r}")
    sets, reps_lo, reps_hi, rpe = m.groups()
    return int(sets), float(reps_lo), (float(reps_hi) if reps_hi else None), float(rpe)


def iteration_of(block_key, week_key):
    return BLOCK_ORDER.index(block_key) * len(WEEK_ORDER) + WEEK_ORDER.index(week_key) + 1


class WgerClient:
    def __init__(self, base_url, token, insecure, dry_run):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.dry_run = dry_run
        self.ctx = ssl._create_unverified_context() if insecure else None
        self.n_calls = 0

    def post(self, path, payload):
        self.n_calls += 1
        if self.dry_run:
            print(f"POST {path:24s} {json.dumps(payload)}")
            return {"id": -self.n_calls}
        url = f"{self.base_url}/api/v2/{path}/"
        body = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Token {self.token}")
        try:
            with urllib.request.urlopen(req, context=self.ctx, timeout=15) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            print(f"FAILED POST {path}: {e.code} {e.read().decode()[:800]}", file=sys.stderr)
            raise


def push_set_configs(client, slot_entry_id, iteration, sets, reps_lo, reps_hi, rir, repeat):
    client.post("sets-config", {
        "slot_entry": slot_entry_id, "iteration": iteration, "value": sets, "repeat": repeat,
    })
    client.post("repetitions-config", {
        "slot_entry": slot_entry_id, "iteration": iteration, "value": reps_lo, "repeat": repeat,
    })
    if reps_hi is not None:
        client.post("max-repetitions-config", {
            "slot_entry": slot_entry_id, "iteration": iteration, "value": reps_hi, "repeat": repeat,
        })
    client.post("rir-config", {
        "slot_entry": slot_entry_id, "iteration": iteration, "value": rir, "repeat": repeat,
    })


def make_slot_entry(client, day_id, order, exercise_id):
    slot = client.post("slot", {"day": day_id, "order": order})
    entry = client.post("slot-entry", {"slot": slot["id"], "exercise": exercise_id})
    return entry["id"]


def push_block_progression(client, slot_entry_id, blocks, field):
    for bk in BLOCK_ORDER:
        if bk not in blocks:
            continue
        for wk in WEEK_ORDER:
            cell = blocks[bk][field][wk]
            sets, reps_lo, reps_hi, rpe = parse_cell(cell)
            iteration = iteration_of(bk, wk)
            push_set_configs(client, slot_entry_id, iteration, sets, reps_lo, reps_hi, 10 - rpe, repeat=False)


def push_flat(client, slot_entry_id, flat_cell):
    sets, reps_lo, reps_hi, rpe = parse_cell(flat_cell)
    push_set_configs(client, slot_entry_id, 1, sets, reps_lo, reps_hi, 10 - rpe, repeat=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="print API calls instead of sending them")
    args = ap.parse_args()

    base_url = os.environ.get("WGER_URL", "https://wger.lan.home")
    token = os.environ.get("WGER_TOKEN")
    insecure = os.environ.get("WGER_INSECURE", "1") == "1"
    if not args.dry_run and not token:
        sys.exit("WGER_TOKEN env var required (export it, don't paste it in chat)")

    data = yaml.safe_load((ROOT / "program.yaml").read_text())
    routine = data["routine"]
    start = date.fromisoformat(routine["start_date"])
    end = start + timedelta(weeks=routine["duration_weeks"]) - timedelta(days=1)

    client = WgerClient(base_url, token, insecure, args.dry_run)

    r = client.post("routine", {
        "name": routine["name"],
        "description": routine.get("description", ""),
        "start": start.isoformat(),
        "end": end.isoformat(),
        "fit_in_week": routine["fit_in_week"],
    })
    routine_id = r["id"]
    print(f"routine id={routine_id}")

    for day in data["days"]:
        d = client.post("day", {
            "routine": routine_id,
            "order": day["order"],
            "name": day["label"],
            "is_rest": False,
        })
        day_id = d["id"]
        print(f"  day {day['label']} id={day_id}")

        slot_order = 1
        for ex in day["exercises"]:
            if ex["kind"] == "main":
                top_id = make_slot_entry(client, day_id, slot_order, ex["wger_exercise_id"]); slot_order += 1
                push_block_progression(client, top_id, ex["blocks"], "top_set")
                back_id = make_slot_entry(client, day_id, slot_order, ex["wger_exercise_id"]); slot_order += 1
                push_block_progression(client, back_id, ex["blocks"], "backoff")
            elif ex["kind"] == "work":
                eid = make_slot_entry(client, day_id, slot_order, ex["wger_exercise_id"]); slot_order += 1
                push_block_progression(client, eid, ex["blocks"], "work")
            else:  # flat
                eid = make_slot_entry(client, day_id, slot_order, ex["wger_exercise_id"]); slot_order += 1
                push_flat(client, eid, ex["flat"])
            print(f"    {ex['name']} ok")

    print(f"done, {client.n_calls} API calls")


if __name__ == "__main__":
    main()
