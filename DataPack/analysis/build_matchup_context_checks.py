#!/usr/bin/env python3
"""Build matchup-controlled pressure evidence from supplied delivery attributes."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
PRESSURE_DELIVERIES = SCRIPT_DIR / "batting_pressure_deliveries.tsv"
RAW_DELIVERIES = ROOT / "ball_by_ball.csv"
MINIMUM_CONTEXT_BALLS = 12
NON_BOWLER_EXTRAS = {"byes", "legbyes", "Penalty"}
NON_BOWLER_WICKETS = {"RunOut", "Retire Out", "Obstracting the field", "Obstructing the field"}


def rate(numerator: int, denominator: int, multiplier: int = 100) -> float:
    return round(multiplier * numerator / denominator, 3)


def bowler_runs(row: dict[str, str]) -> int:
    extras = 0
    if row["extras_type"] not in NON_BOWLER_EXTRAS:
        extras = int(row["extras1_runs"]) + int(row["extras_2_runs"])
    return int(row["runs"]) + extras


def main() -> None:
    with PRESSURE_DELIVERIES.open(newline="", encoding="utf-8") as handle:
        deliveries = list(csv.DictReader(handle, delimiter="\t"))
    with RAW_DELIVERIES.open(newline="", encoding="utf-8") as handle:
        source = {
            (row["match_id"], row["innings"], row["overid"], row["over_ball_num"]): row
            for row in csv.DictReader(handle)
        }

    batting = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {"balls": 0, "runs": 0, "dismissals": 0})))
    bowling = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {"balls": 0, "runs": 0, "wickets": 0})))
    for row in deliveries:
        band = row["batting_pressure_band"]
        if band not in {"high", "normal"}:
            continue
        key = (row["match_id"], row["innings"], row["overid"], row["over_ball_num"])
        context = source[key]
        if row["extras_type"] != "wide":
            values = batting[(row["striker_id"], row["striker_name"])][context["pace_or_spin"]][band]
            values["balls"] += 1
            values["runs"] += int(row["runs"])
            values["dismissals"] += row["is_wicket"].lower() == "true" and row["dismissed_player_id"] == row["striker_id"]
        if row["is_legal_delivery"] == "true":
            values = bowling[(row["bowler_id"], row["bowler_name"])][context["batting_type"]][band]
            values["balls"] += 1
            values["runs"] += bowler_runs(row)
            values["wickets"] += row["is_wicket"].lower() == "true" and row["dismissal_type"] not in NON_BOWLER_WICKETS

    batting_columns = [
        "striker_id", "striker_name", "bowling_context", "high_balls", "high_runs", "high_runs_per_ball",
        "normal_balls", "normal_runs", "normal_runs_per_ball", "runs_per_ball_delta", "high_dismissals",
        "normal_dismissals", "dismissal_rate_delta",
    ]
    valid_batting = 0
    with (SCRIPT_DIR / "batting_matchup_evidence.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=batting_columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for (player_id, player_name), contexts in sorted(batting.items(), key=lambda item: item[0][1]):
            for context, values in sorted(contexts.items()):
                high, normal = values["high"], values["normal"]
                if high["balls"] < MINIMUM_CONTEXT_BALLS or normal["balls"] < MINIMUM_CONTEXT_BALLS:
                    continue
                valid_batting += 1
                high_rate = high["runs"] / high["balls"]
                normal_rate = normal["runs"] / normal["balls"]
                writer.writerow(
                    {
                        "striker_id": player_id, "striker_name": player_name, "bowling_context": context,
                        "high_balls": high["balls"], "high_runs": high["runs"], "high_runs_per_ball": round(high_rate, 4),
                        "normal_balls": normal["balls"], "normal_runs": normal["runs"], "normal_runs_per_ball": round(normal_rate, 4),
                        "runs_per_ball_delta": round(high_rate - normal_rate, 4), "high_dismissals": high["dismissals"],
                        "normal_dismissals": normal["dismissals"],
                        "dismissal_rate_delta": round(normal["dismissals"] / normal["balls"] - high["dismissals"] / high["balls"], 4),
                    }
                )

    bowling_columns = [
        "bowler_id", "bowler_name", "batter_handedness", "high_legal_balls", "high_runs_conceded", "high_economy",
        "normal_legal_balls", "normal_runs_conceded", "normal_economy", "economy_delta", "high_wickets",
        "normal_wickets", "wicket_rate_delta",
    ]
    valid_bowling = 0
    with (SCRIPT_DIR / "bowling_matchup_evidence.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=bowling_columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for (player_id, player_name), contexts in sorted(bowling.items(), key=lambda item: item[0][1]):
            for context, values in sorted(contexts.items()):
                high, normal = values["high"], values["normal"]
                if high["balls"] < MINIMUM_CONTEXT_BALLS or normal["balls"] < MINIMUM_CONTEXT_BALLS:
                    continue
                valid_bowling += 1
                high_economy = 6 * high["runs"] / high["balls"]
                normal_economy = 6 * normal["runs"] / normal["balls"]
                writer.writerow(
                    {
                        "bowler_id": player_id, "bowler_name": player_name, "batter_handedness": context,
                        "high_legal_balls": high["balls"], "high_runs_conceded": high["runs"], "high_economy": round(high_economy, 4),
                        "normal_legal_balls": normal["balls"], "normal_runs_conceded": normal["runs"], "normal_economy": round(normal_economy, 4),
                        "economy_delta": round(normal_economy - high_economy, 4), "high_wickets": high["wickets"],
                        "normal_wickets": normal["wickets"],
                        "wicket_rate_delta": round(high["wickets"] / high["balls"] - normal["wickets"] / normal["balls"], 4),
                    }
                )

    with (SCRIPT_DIR / "matchup_feature_validation.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["metric", "value"])
        writer.writerows(
            [
                ["batting_control", "Pace versus spin"],
                ["bowling_control", "Right-handed versus left-handed batter"],
                ["minimum_per_context_exposure", MINIMUM_CONTEXT_BALLS],
                ["minimum_interpretation", "At least two overs of high-pressure and two overs of normal-pressure exposure per matchup stratum."],
                ["valid_batting_matchup_rows", valid_batting],
                ["valid_bowling_matchup_rows", valid_bowling],
                ["ranking_status", "Challenger evidence only. Do not replace the main ranking until leave-one-season-out stability is at least as strong."],
            ]
        )
    print(f"Valid batting matchup rows: {valid_batting}")
    print(f"Valid bowling matchup rows: {valid_bowling}")


if __name__ == "__main__":
    main()
