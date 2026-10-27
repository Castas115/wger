#!/usr/bin/env python3
"""Push workouts logged directly in Lyftr back into wger as WorkoutSession/WorkoutLog.

Matches each Lyftr workout exercise to a wger slot_entry by day name + exercise
order (both apps' days mirror program.yaml's exercise order 1:1). Takes explicit
Lyftr workout ids, since Lyftr has no "already synced to wger" marker.

Env vars: WGER_URL, WGER_TOKEN, LYFTR_URL, LYFTR_TOKEN (see import_wger_routine.py
and migrate_from_wger.py for the same pattern).

Usage:
  python3 scripts/sync_lyftr_workouts_to_wger.py --workout-ids 3,4 --routine-id 5 --dry-run
  python3 scripts/sync_lyftr_workouts_to_wger.py --workout-ids 3,4 --routine-id 5
"""
import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta

# Lyftr exercise id -> wger exercise id. Inverse of WGER_TO_LYFTR in
# ../../lyftr/scripts/migrate_from_wger.py - keep both in sync by hand.
LYFTR_TO_WGER = {
    560: 475, 59: 566, 796: 1273, 45: 91, 40: 1380, 73: 73, 860: 1510,
    664: 348, 777: 1519, 285: 257, 376: 1388, 161: 154, 343: 537,
    309: 1932, 604: 507, 96: 1903, 532: 194, 495: 1637, 825: 1185,
}


class Api:
    def __init__(self, base_url, auth_header, insecure):
        self.base_url = base_url.rstrip("/")
        self.auth_header = auth_header
        self.ctx = ssl._create_unverified_context() if insecure else None

    def request(self, method, path, payload=None, params=None):
        url = f"{self.base_url}{path}"
        if params:
            from urllib.parse import urlencode
            url += "?" + urlencode(params)
        body = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(url, data=body, method=method)
        if body is not None:
            req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", self.auth_header)
        try:
            with urllib.request.urlopen(req, context=self.ctx, timeout=20) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            print(f"FAILED {method} {path}: {e.code} {e.read().decode()[:500]}", file=sys.stderr)
            raise


def day_slot_entries_by_exercise(wger, day_id):
    """wger_exercise_id -> queue of slot_entry_ids for that exercise, in slot order.

    A "main" lift (top set + backoff) produces two slots for the same exercise;
    queue order preserves which is which (top always precedes backoff in slot
    order, same as the logging order on the Lyftr side), so popping from the
    front as each Lyftr exercise occurrence is matched keeps them paired
    correctly even when other exercises in between were skipped that session.
    """
    slots = wger.request("GET", "/api/v2/slot/", params={"day": day_id})["results"]
    slots.sort(key=lambda s: s["order"])
    by_exercise = {}
    for slot in slots:
        results = wger.request("GET", "/api/v2/slot-entry/", params={"slot": slot["id"]})["results"]
        for se in results:
            by_exercise.setdefault(se["exercise"], []).append(se["id"])
    return by_exercise


def sync_workout(wger, routine_id, workout, day_id):
    day = wger.request("GET", f"/api/v2/day/{day_id}/")
    by_exercise = day_slot_entries_by_exercise(wger, day_id)

    start_dt = datetime.fromisoformat(workout["started_at"].replace("Z", "+00:00"))
    end_dt = start_dt + timedelta(seconds=workout.get("duration") or 0)

    session = wger.request("POST", "/api/v2/workoutsession/", {
        "routine": routine_id,
        "day": day_id,
        "notes": workout.get("notes", ""),
        "impression": "2",
        "datetime_start": start_dt.isoformat(),
        "datetime_end": end_dt.isoformat() if workout.get("duration") else None,
    })
    print(f"  session created for day {day['name']!r}: {session['id']}")

    exercises = sorted(workout["exercises"], key=lambda e: e["order_index"])
    for ex in exercises:
        wger_exercise_id = LYFTR_TO_WGER.get(ex["exercise_id"])
        if wger_exercise_id is None:
            print(f"  WARN: no wger mapping for lyftr exercise {ex['exercise_id']} "
                  f"({ex['exercise']['name']}), skipping", file=sys.stderr)
            continue
        queue = by_exercise.get(wger_exercise_id)
        if not queue:
            print(f"  WARN: no slot_entry left for wger exercise {wger_exercise_id} "
                  f"({ex['exercise']['name']}) on day {day['name']!r}, skipping", file=sys.stderr)
            continue
        slot_entry_id = queue.pop(0)

        for s in ex["sets"]:
            wger.request("POST", "/api/v2/workoutlog/", {
                "date": start_dt.date().isoformat(),
                "session": session["id"],
                "routine": routine_id,
                "iteration": 1,
                "slot_entry": slot_entry_id,
                "exercise": wger_exercise_id,
                "repetitions": s.get("reps", 0),
                "weight": s.get("weight", 0),
            })
        print(f"    {ex['exercise']['name']} -> wger exercise {wger_exercise_id} (slot_entry {slot_entry_id}): "
              f"{len(ex['sets'])} sets")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workout-ids", required=True, help="comma-separated Lyftr workout ids to push")
    ap.add_argument("--routine-id", type=int, required=True, help="wger routine id")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    wger_token = os.environ.get("WGER_TOKEN")
    lyftr_token = os.environ.get("LYFTR_TOKEN")
    if not wger_token or not lyftr_token:
        sys.exit("WGER_TOKEN and LYFTR_TOKEN both required")

    wger = Api(
        os.environ.get("WGER_URL", "https://wger.lan.home"),
        f"Token {wger_token}",
        os.environ.get("WGER_INSECURE", "1") == "1",
    )
    lyftr = Api(
        os.environ.get("LYFTR_URL", "https://lyftr.lan.home"),
        f"Bearer {lyftr_token}",
        os.environ.get("LYFTR_INSECURE", "1") == "1",
    )

    for wid in [int(x) for x in args.workout_ids.split(",")]:
        workout = lyftr.request("GET", f"/api/v1/workouts/{wid}")["data"]
        day_name = workout["name"].split("—")[-1].strip()
        days = wger.request("GET", "/api/v2/day/", params={"routine": args.routine_id})["results"]
        matches = [d for d in days if d["name"] == day_name]
        if not matches:
            print(f"workout {wid} ({workout['name']!r}): no wger day named {day_name!r}, skipping", file=sys.stderr)
            continue
        day_id = matches[0]["id"]

        print(f"workout {wid}: {workout['name']!r} ({workout['started_at']}) -> wger day {day_id} ({day_name!r})")
        if args.dry_run:
            for ex in workout["exercises"]:
                print(f"  {ex['exercise']['name']}: {len(ex['sets'])} sets")
            continue
        sync_workout(wger, args.routine_id, workout, day_id)


if __name__ == "__main__":
    main()
