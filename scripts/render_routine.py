#!/usr/bin/env python3
"""Render routine.html from program.yaml. Single source of truth: program.yaml."""
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "scripts" / "routine_template.html"

CELL_RE = re.compile(r"^(\d+)x([\d.-]+)\s*@([\d.]+)$")


def parse_cell(cell):
    m = CELL_RE.match(cell.strip())
    if not m:
        raise ValueError(f"bad cell: {cell!r}")
    sets, reps, rpe = m.groups()
    return sets, reps, rpe


def fmt_spec(ex):
    suffix = {"leg": " /leg", "arm": " /arm"}.get(ex.get("unilateral"), "")
    if ex["kind"] == "main":
        top_sets, top_reps, rpe = parse_cell(ex["blocks"]["B1"]["top_set"]["W1"])
        back_sets, back_reps, _ = parse_cell(ex["blocks"]["B1"]["backoff"]["W1"])
        return f"{top_sets}×{top_reps} top + {back_sets}×{back_reps} backoff @{rpe}{suffix}"
    if ex["kind"] == "work":
        sets, reps, rpe = parse_cell(ex["blocks"]["B1"]["work"]["W1"])
        return f"{sets}×{reps.replace('-', '–')} @{rpe}{suffix}"
    sets, reps, rpe = parse_cell(ex["flat"])
    return f"{sets}×{reps.replace('-', '–')}{suffix}"


def main():
    data = yaml.safe_load((ROOT / "program.yaml").read_text())

    days_js = []
    for day in data["days"]:
        exercises_js = []
        for ex in day["exercises"]:
            entry = {
                "role": ex["role"],
                "pattern": ex["pattern"],
                "name": ex["name"],
                "spec": fmt_spec(ex),
            }
            if ex["kind"] in ("main", "work"):
                entry["kind"] = ex["kind"]
                entry["blocks"] = ex["blocks"]
            exercises_js.append(entry)
        days_js.append(
            {
                "num": f"Day {day['order']}",
                "name": day["label"],
                "focus": day["focus"],
                "exercises": exercises_js,
            }
        )

    routine = data["routine"]
    template = TEMPLATE.read_text()
    display_name = f"{routine['name']} — {routine['description']}" if routine.get("description") else routine["name"]
    html = (
        template
        .replace("__ROUTINE_NAME_JSON__", json.dumps(display_name, ensure_ascii=False))
        .replace("__START_DATE_JSON__", json.dumps(routine["start_date"]))
        .replace("__DURATION_WEEKS__", str(routine["duration_weeks"]))
        .replace("__DAYS_JSON__", json.dumps(days_js, ensure_ascii=False, indent=2))
    )

    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "routine.html"
    out_path.write_text(html)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
