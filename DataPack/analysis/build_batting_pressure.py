#!/usr/bin/env python3
"""Classify chase deliveries by batting pressure using observed T20 match states."""

from __future__ import annotations

import csv
from bisect import bisect_right
from collections import defaultdict
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR if (SCRIPT_DIR / "ball_by_ball.csv").exists() else SCRIPT_DIR.parent
OUTPUT_DIR = ROOT / "analysis"
SOURCE = OUTPUT_DIR / "clean_delivery_base.tsv"


def percentile(sorted_values: list[float], fraction: float) -> float:
    index = (len(sorted_values) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (index - lower)


def main() -> None:
    with SOURCE.open(newline="", encoding="utf-8") as handle:
        deliveries = list(csv.DictReader(handle, delimiter="\t"))

    def is_chase_state(row: dict[str, str]) -> bool:
        return (
            row["innings"] == "2"
            and bool(row["runs_required_before"])
            and int(row["runs_required_before"]) > 0
            and int(row["balls_remaining_before"]) > 0
        )

    chase_rows = [row for row in deliveries if is_chase_state(row)]
    required_rates = sorted(float(row["required_run_rate_before"]) for row in chase_rows)
    rate_median = percentile(required_rates, 0.50)
    rate_upper_quartile = percentile(required_rates, 0.75)
    labelled_rows = []
    for row in deliveries:
        labelled = dict(row)
        labelled.update({
            "is_chase_state": "false", "wickets_in_hand_before": "", "required_rate_percentile": "",
            "wicket_pressure": "", "time_pressure": "", "batting_pressure_index": "",
            "batting_pressure_band": "not_applicable",
        })
        if is_chase_state(row):
            required_rate = float(row["required_run_rate_before"])
            wickets_lost = int(row["wickets_before"])
            scheduled_balls = int(row["scheduled_balls"])
            balls_remaining = int(row["balls_remaining_before"])
            rate_pressure = round(bisect_right(required_rates, required_rate) / len(required_rates), 4)
            wicket_pressure = wickets_lost / 10
            time_pressure = 1 - balls_remaining / scheduled_balls
            pressure_index = round((rate_pressure + wicket_pressure + time_pressure) / 3, 4)
            labelled.update({
                "is_chase_state": "true", "wickets_in_hand_before": 10 - wickets_lost,
                "required_rate_percentile": rate_pressure, "wicket_pressure": round(wicket_pressure, 4),
                "time_pressure": round(time_pressure, 4), "batting_pressure_index": pressure_index,
            })
        labelled_rows.append(labelled)

    chase_indices = sorted(float(row["batting_pressure_index"]) for row in labelled_rows if row["is_chase_state"] == "true")
    index_median = percentile(chase_indices, 0.50)
    index_upper_quartile = percentile(chase_indices, 0.75)
    for row in labelled_rows:
        if row["is_chase_state"] == "true":
            pressure_index = float(row["batting_pressure_index"])
            row["batting_pressure_band"] = (
                "high" if pressure_index >= index_upper_quartile else "moderate" if pressure_index >= index_median else "normal"
            )

    output_columns = list(deliveries[0].keys()) + [
        "is_chase_state", "wickets_in_hand_before", "required_rate_percentile", "wicket_pressure",
        "time_pressure", "batting_pressure_index", "batting_pressure_band",
    ]
    with (OUTPUT_DIR / "batting_pressure_deliveries.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(labelled_rows)

    player_rows = defaultdict(lambda: {"balls_faced": 0, "bat_runs": 0, "fours": 0, "sixes": 0, "dismissals": 0})
    for row in labelled_rows:
        if row["batting_pressure_band"] == "not_applicable":
            continue
        key = (row["striker_id"], row["striker_name"], row["batting_pressure_band"])
        player = player_rows[key]
        if row["extras_type"] != "wide":
            player["balls_faced"] += 1
        player["bat_runs"] += int(row["runs"])
        player["fours"] += row["is_four"].lower() == "true"
        player["sixes"] += row["is_six"].lower() == "true"
        player["dismissals"] += row["dismissed_player_id"] == row["striker_id"] and row["is_wicket"].lower() == "true"

    summary_columns = ["striker_id", "striker_name", "pressure_band", "balls_faced", "bat_runs", "strike_rate", "fours", "sixes", "dismissals"]
    with (OUTPUT_DIR / "batting_pressure_player_summary.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=summary_columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for (player_id, player_name, band), values in sorted(player_rows.items(), key=lambda item: (item[0][2], -item[1]["balls_faced"], item[0][1])):
            writer.writerow({
                "striker_id": player_id, "striker_name": player_name, "pressure_band": band,
                "balls_faced": values["balls_faced"], "bat_runs": values["bat_runs"],
                "strike_rate": round(100 * values["bat_runs"] / values["balls_faced"], 2) if values["balls_faced"] else "",
                "fours": values["fours"], "sixes": values["sixes"], "dismissals": values["dismissals"],
            })

    with (OUTPUT_DIR / "batting_pressure_definition.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["metric", "value"])
        writer.writerows([
            ["scope", "Second-innings deliveries before the target is reached; abandoned matches excluded."],
            ["eligible_chase_deliveries", len(required_rates)],
            ["required_run_rate_median", round(rate_median, 3)],
            ["required_run_rate_75th_percentile", round(rate_upper_quartile, 3)],
            ["pressure_index", "Mean of required-run-rate percentile, wickets-lost share, and elapsed-ball share."],
            ["weighting", "Equal weights after normalising components to 0-1; no subjective weight is assumed before validation."],
            ["normal_band", f"Pressure index below {index_median:.4f} (bottom 50% of eligible chase states)."],
            ["moderate_band", f"Pressure index from {index_median:.4f} up to {index_upper_quartile:.4f} (50th-75th percentile)."],
            ["high_band", f"Pressure index at or above {index_upper_quartile:.4f} (top 25% of eligible chase states)."],
            ["ball_faced_rule", "A wide is excluded from balls faced; other delivery types are retained."],
        ])

    print(f"Eligible chase deliveries: {len(chase_rows)}")
    print(f"Required run-rate median / 75th percentile: {rate_median:.3f} / {rate_upper_quartile:.3f}")
    print(f"Pressure-index median / 75th percentile: {index_median:.4f} / {index_upper_quartile:.4f}")
    print(f"High-pressure deliveries: {sum(row['batting_pressure_band'] == 'high' for row in labelled_rows)}")


if __name__ == "__main__":
    main()
