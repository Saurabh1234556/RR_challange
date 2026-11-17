#!/usr/bin/env python3
"""Build clean delivery and innings tables for SupeRR Selector pressure analysis."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR if (SCRIPT_DIR / "ball_by_ball.csv").exists() else SCRIPT_DIR.parent
OUTPUT_DIR = ROOT / "analysis"
RAW_DELIVERIES = ROOT / "ball_by_ball.csv"
MATCHES = ROOT / "matches.csv"
COMPETITIONS = ROOT / "competitions.csv"
EXCLUDED_RESULT = "Match Abandoned"
ILLEGAL_EXTRA_TYPES = {"wide", "Overstep"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def number(value: str) -> int:
    return int(value or 0)


def scheduled_balls(overs: str) -> int:
    if not overs:
        return 120
    whole_overs, _, partial_balls = overs.partition(".")
    return int(whole_overs) * 6 + int(partial_balls or 0)


def phase(over_number: int) -> str:
    if over_number <= 6:
        return "powerplay"
    if over_number <= 15:
        return "middle"
    return "death"


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    competitions = {row["comp_id"]: row for row in read_csv(COMPETITIONS)}
    matches = {row["match_id"]: row for row in read_csv(MATCHES)}
    raw_deliveries = read_csv(RAW_DELIVERIES)
    valid_matches = {
        match_id: match for match_id, match in matches.items() if match["result"] != EXCLUDED_RESULT
    }
    deliveries = [row for row in raw_deliveries if row["match_id"] in valid_matches]
    innings = defaultdict(list)
    for delivery in deliveries:
        innings[(delivery["match_id"], number(delivery["innings"]))].append(delivery)
    for rows in innings.values():
        rows.sort(key=lambda row: (number(row["overid"]), number(row["over_ball_num"]), number(row["innings_ball_num"])))

    first_innings_totals = {}
    for (match_id, innings_number), rows in innings.items():
        if innings_number == 1:
            first_innings_totals[match_id] = sum(number(row["runs"]) + number(row["extras1_runs"]) + number(row["extras_2_runs"]) for row in rows)

    delivery_columns = [
        "match_id", "comp_id", "comp_name", "match_format", "season", "match_date", "venue_country",
        "innings", "overid", "over_ball_num", "innings_ball_num", "innings_phase", "batting_team_id",
        "bowling_team_id", "striker_id", "striker_name", "non_striker_id", "non_striker_name", "bowler_id",
        "bowler_name", "batting_order", "runs", "extras_type", "extras1_runs", "extras_2_runs",
        "runs_on_delivery", "is_four", "is_six", "is_wicket", "dismissal_type", "dismissed_player_id",
        "is_legal_delivery", "score_before", "score_after", "wickets_before",
        "wickets_after", "legal_balls_before", "scheduled_balls", "balls_remaining_before", "chase_target",
        "runs_required_before", "required_run_rate_before",
    ]
    delivery_output = OUTPUT_DIR / "clean_delivery_base.tsv"
    innings_output = OUTPUT_DIR / "innings_summary.tsv"
    innings_rows = []

    with delivery_output.open("w", newline="", encoding="utf-8") as delivery_handle:
        writer = csv.DictWriter(delivery_handle, fieldnames=delivery_columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for (match_id, innings_number), rows in sorted(innings.items()):
            match = valid_matches[match_id]
            competition = competitions[match["comp_id"]]
            max_balls = scheduled_balls(match["first_inn_revised_overs"] if innings_number == 1 else match["second_inn_revised_overs"])
            target = ""
            if innings_number == 2:
                target = number(match["revised_target"]) or first_innings_totals.get(match_id, 0) + 1
            score = wickets = legal_balls = 0
            for row in rows:
                delivery_runs = number(row["runs"]) + number(row["extras1_runs"]) + number(row["extras_2_runs"])
                is_legal = row["extras_type"] not in ILLEGAL_EXTRA_TYPES
                balls_remaining = max(max_balls - legal_balls, 0)
                runs_required = max(target - score, 0) if target else ""
                required_rate = round(runs_required * 6 / balls_remaining, 3) if target and balls_remaining else ""
                writer.writerow({
                    "match_id": match_id, "comp_id": match["comp_id"], "comp_name": competition["comp_name"],
                    "match_format": competition["match_format"], "season": competition["season"], "match_date": match["match_date"],
                    "venue_country": match["venue_country"], "innings": innings_number, "overid": row["overid"],
                    "over_ball_num": row["over_ball_num"], "innings_ball_num": row["innings_ball_num"],
                    "innings_phase": phase(number(row["overid"])), "batting_team_id": row["batting_team_id"],
                    "bowling_team_id": row["bowling_team_id"], "striker_id": row["striker_id"], "striker_name": row["striker_name"],
                    "non_striker_id": row["non_striker_id"], "non_striker_name": row["non_striker_name"], "bowler_id": row["bowler_id"],
                    "bowler_name": row["bowler_name"], "batting_order": row["batting_order"], "runs": row["runs"],
                    "extras_type": row["extras_type"], "extras1_runs": row["extras1_runs"], "extras_2_runs": row["extras_2_runs"],
                    "runs_on_delivery": delivery_runs, "is_four": row["is_four"], "is_six": row["is_six"],
                    "is_wicket": row["is_wicket"], "dismissal_type": row["dismissal_type"],
                    "dismissed_player_id": row["dismissed_player_id"], "is_legal_delivery": str(is_legal).lower(),
                    "score_before": score, "score_after": score + delivery_runs, "wickets_before": wickets,
                    "wickets_after": wickets + (row["is_wicket"].lower() == "true"), "legal_balls_before": legal_balls,
                    "scheduled_balls": max_balls, "balls_remaining_before": balls_remaining, "chase_target": target,
                    "runs_required_before": runs_required, "required_run_rate_before": required_rate,
                })
                score += delivery_runs
                wickets += row["is_wicket"].lower() == "true"
                legal_balls += is_legal
            innings_rows.append({
                "match_id": match_id, "comp_id": match["comp_id"], "match_date": match["match_date"],
                "innings": innings_number, "batting_team_id": rows[0]["batting_team_id"], "bowling_team_id": rows[0]["bowling_team_id"],
                "innings_runs": score, "wickets_lost": wickets, "legal_balls": legal_balls, "scheduled_balls": max_balls,
                "chase_target": target, "result": match["result"],
            })

    with innings_output.open("w", newline="", encoding="utf-8") as innings_handle:
        writer = csv.DictWriter(innings_handle, fieldnames=innings_rows[0].keys(), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(innings_rows)
    print(f"Excluded abandoned matches: {len(matches) - len(valid_matches)}")
    print(f"Clean deliveries written: {len(deliveries)}")
    print(f"Innings summaries written: {len(innings_rows)}")
    print(f"Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
