#!/usr/bin/env python3
"""Create cricket-context evidence tables for the pressure-ranking report."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
PRESSURE_DELIVERIES = SCRIPT_DIR / "batting_pressure_deliveries.tsv"
RAW_DELIVERIES = ROOT / "ball_by_ball.csv"
NON_BOWLER_EXTRAS = {"byes", "legbyes", "Penalty"}
NON_BOWLER_WICKETS = {"RunOut", "Retire Out", "Obstracting the field", "Obstructing the field"}
YORKER_STYLES = {"Yorker", "Wide Yorker"}


def rate(numerator: int, denominator: int, multiplier: int = 100) -> float | str:
    return round(multiplier * numerator / denominator, 2) if denominator else ""


def bowler_runs_conceded(row: dict[str, str]) -> int:
    extras = 0
    if row["extras_type"] not in NON_BOWLER_EXTRAS:
        extras = int(row["extras1_runs"]) + int(row["extras_2_runs"])
    return int(row["runs"]) + extras


def bowler_wicket(row: dict[str, str]) -> bool:
    return row["is_wicket"].lower() == "true" and row["dismissal_type"] not in NON_BOWLER_WICKETS


def main() -> None:
    with PRESSURE_DELIVERIES.open(newline="", encoding="utf-8") as handle:
        deliveries = list(csv.DictReader(handle, delimiter="\t"))
    with RAW_DELIVERIES.open(newline="", encoding="utf-8") as handle:
        styles = {
            (row["match_id"], row["innings"], row["overid"], row["over_ball_num"]): row["delivery_style"]
            for row in csv.DictReader(handle)
        }

    batting = defaultdict(lambda: defaultdict(int))
    bowling = defaultdict(lambda: defaultdict(int))
    groups = defaultdict(list)
    for row in deliveries:
        groups[(row["match_id"], row["innings"], row["overid"])].append(row)
        if row["batting_pressure_band"] != "high":
            continue

        batter = batting[(row["striker_id"], row["striker_name"])]
        if row["extras_type"] != "wide":
            batter["high_balls"] += 1
            batter["high_runs"] += int(row["runs"])
            if row["innings_phase"] == "death":
                batter["death_balls"] += 1
                batter["death_runs"] += int(row["runs"])
            if int(row["wickets_in_hand_before"] or 10) <= 5:
                batter["low_wicket_balls"] += 1
                batter["low_wicket_runs"] += int(row["runs"])

        if row["is_legal_delivery"] != "true":
            continue
        bowler = bowling[(row["bowler_id"], row["bowler_name"])]
        bowler["high_legal_balls"] += 1
        bowler["high_runs_conceded"] += bowler_runs_conceded(row)
        bowler["high_wickets"] += bowler_wicket(row)
        if row["innings_phase"] == "death":
            bowler["death_legal_balls"] += 1
            bowler["death_runs_conceded"] += bowler_runs_conceded(row)
            bowler["death_wickets"] += bowler_wicket(row)
            style = styles.get((row["match_id"], row["innings"], row["overid"], row["over_ball_num"]), "")
            if style in YORKER_STYLES:
                bowler["death_yorker_legal_balls"] += 1
                bowler["death_yorker_runs_conceded"] += bowler_runs_conceded(row)
                bowler["death_yorker_wickets"] += bowler_wicket(row)

    for group in groups.values():
        group.sort(key=lambda row: int(row["over_ball_num"]))
        for index, row in enumerate(group):
            is_boundary = row["is_four"].lower() == "true" or row["is_six"].lower() == "true"
            if row["batting_pressure_band"] != "high" or not is_boundary:
                continue
            next_legal = next((item for item in group[index + 1 :] if item["is_legal_delivery"] == "true"), None)
            if not next_legal or next_legal["bowler_id"] != row["bowler_id"]:
                continue
            bowler = bowling[(row["bowler_id"], row["bowler_name"])]
            bowler["boundary_recovery_opportunities"] += 1
            bowler["boundary_recovery_legal_balls"] += 1
            bowler["boundary_recovery_runs_conceded"] += bowler_runs_conceded(next_legal)
            bowler["boundary_recovery_wickets"] += bowler_wicket(next_legal)

    batting_columns = [
        "striker_id", "striker_name", "high_pressure_balls", "high_pressure_runs", "high_pressure_strike_rate",
        "death_pressure_balls", "death_pressure_runs", "death_pressure_strike_rate", "low_wicket_pressure_balls",
        "low_wicket_pressure_runs", "low_wicket_pressure_strike_rate",
    ]
    with (SCRIPT_DIR / "batting_cricket_context_evidence.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=batting_columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for (player_id, player_name), values in sorted(batting.items(), key=lambda item: (-item[1]["high_balls"], item[0][1])):
            writer.writerow(
                {
                    "striker_id": player_id,
                    "striker_name": player_name,
                    "high_pressure_balls": values["high_balls"],
                    "high_pressure_runs": values["high_runs"],
                    "high_pressure_strike_rate": rate(values["high_runs"], values["high_balls"]),
                    "death_pressure_balls": values["death_balls"],
                    "death_pressure_runs": values["death_runs"],
                    "death_pressure_strike_rate": rate(values["death_runs"], values["death_balls"]),
                    "low_wicket_pressure_balls": values["low_wicket_balls"],
                    "low_wicket_pressure_runs": values["low_wicket_runs"],
                    "low_wicket_pressure_strike_rate": rate(values["low_wicket_runs"], values["low_wicket_balls"]),
                }
            )

    bowling_columns = [
        "bowler_id", "bowler_name", "high_pressure_legal_balls", "high_pressure_runs_conceded", "high_pressure_economy",
        "high_pressure_wickets", "death_pressure_legal_balls", "death_pressure_runs_conceded", "death_pressure_economy",
        "death_pressure_wickets", "death_yorker_legal_balls", "death_yorker_runs_conceded", "death_yorker_economy",
        "death_yorker_wickets", "death_yorker_share", "boundary_recovery_opportunities", "boundary_recovery_runs_conceded",
        "boundary_recovery_economy", "boundary_recovery_wickets",
    ]
    with (SCRIPT_DIR / "bowling_cricket_context_evidence.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=bowling_columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for (player_id, player_name), values in sorted(bowling.items(), key=lambda item: (-item[1]["high_legal_balls"], item[0][1])):
            writer.writerow(
                {
                    "bowler_id": player_id,
                    "bowler_name": player_name,
                    "high_pressure_legal_balls": values["high_legal_balls"],
                    "high_pressure_runs_conceded": values["high_runs_conceded"],
                    "high_pressure_economy": rate(values["high_runs_conceded"], values["high_legal_balls"], 6),
                    "high_pressure_wickets": values["high_wickets"],
                    "death_pressure_legal_balls": values["death_legal_balls"],
                    "death_pressure_runs_conceded": values["death_runs_conceded"],
                    "death_pressure_economy": rate(values["death_runs_conceded"], values["death_legal_balls"], 6),
                    "death_pressure_wickets": values["death_wickets"],
                    "death_yorker_legal_balls": values["death_yorker_legal_balls"],
                    "death_yorker_runs_conceded": values["death_yorker_runs_conceded"],
                    "death_yorker_economy": rate(values["death_yorker_runs_conceded"], values["death_yorker_legal_balls"], 6),
                    "death_yorker_wickets": values["death_yorker_wickets"],
                    "death_yorker_share": rate(values["death_yorker_legal_balls"], values["death_legal_balls"]),
                    "boundary_recovery_opportunities": values["boundary_recovery_opportunities"],
                    "boundary_recovery_runs_conceded": values["boundary_recovery_runs_conceded"],
                    "boundary_recovery_economy": rate(values["boundary_recovery_runs_conceded"], values["boundary_recovery_legal_balls"], 6),
                    "boundary_recovery_wickets": values["boundary_recovery_wickets"],
                }
            )

    with (SCRIPT_DIR / "cricket_context_feature_record.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["feature", "availability", "model_use", "reason"])
        writer.writerows(
            [
                ["Death overs", "Complete from overid", "Supporting evidence", "Time pressure already appears in the core pressure index; adding it again would double count."],
                ["Wickets in hand", "Complete from delivery sequence", "Core pressure index and supporting evidence", "Wickets lost is already a continuous pressure input; low-wicket splits show batting context."],
                ["Yorkers", "Explicit Yorker and Wide Yorker labels", "Supporting bowling evidence", "Used for high-pressure death-over execution, not a score weight, to avoid rewarding volume of attempts over outcomes."],
                ["Post-boundary recovery", "Derived from next legal ball in the same over", "Supporting bowling evidence", "Measures immediate response after a conceded four or six without claiming an unobserved psychological state."],
                ["Batter handedness and bowling style", "Available", "Future context adjustment", "Needs a minimum-sample match-up model before it can be used fairly in rankings."],
                ["Pace or spin", "Available", "Future context adjustment", "Useful for descriptive splits but not included until sample-adjusted validation is complete."],
            ]
        )

    print(f"Batting context rows: {len(batting)}")
    print(f"Bowling context rows: {len(bowling)}")


if __name__ == "__main__":
    main()
