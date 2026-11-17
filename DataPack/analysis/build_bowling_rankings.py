#!/usr/bin/env python3
"""Rate bowlers against their own normal-pressure chase baseline."""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR if (SCRIPT_DIR / "ball_by_ball.csv").exists() else SCRIPT_DIR.parent
OUTPUT_DIR = ROOT / "analysis"
SOURCE = OUTPUT_DIR / "batting_pressure_deliveries.tsv"
NON_BOWLER_EXTRAS = {"byes", "legbyes", "Penalty"}
NON_BOWLER_WICKETS = {"RunOut", "Retire Out", "Obstracting the field", "Obstructing the field"}


def percentile(sorted_values: list[float], fraction: float) -> float:
    index = (len(sorted_values) - 1) * fraction
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (index - lower)


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def standard_deviation(values: list[float]) -> float:
    centre = mean(values)
    return math.sqrt(sum((value - centre) ** 2 for value in values) / (len(values) - 1))


def main() -> None:
    player_bands = defaultdict(lambda: defaultdict(lambda: {"balls": 0, "runs": 0, "wickets": 0}))
    with SOURCE.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            band = row["batting_pressure_band"]
            if band not in {"high", "normal"} or row["is_legal_delivery"] != "true":
                continue
            values = player_bands[(row["bowler_id"], row["bowler_name"])][band]
            extras = 0
            if row["extras_type"] not in NON_BOWLER_EXTRAS:
                extras = int(row["extras1_runs"]) + int(row["extras_2_runs"])
            values["balls"] += 1
            values["runs"] += int(row["runs"]) + extras
            values["wickets"] += (
                row["is_wicket"].lower() == "true" and row["dismissal_type"] not in NON_BOWLER_WICKETS
            )

    high_exposure = sorted(values["high"]["balls"] for values in player_bands.values() if values["high"]["balls"])
    minimum_exposure = math.ceil(percentile(high_exposure, 0.80))
    candidates = []
    for (bowler_id, bowler_name), values in player_bands.items():
        high = values["high"]
        normal = values["normal"]
        if high["balls"] < minimum_exposure or normal["balls"] < minimum_exposure:
            continue
        high_economy = 6 * high["runs"] / high["balls"]
        normal_economy = 6 * normal["runs"] / normal["balls"]
        high_wicket_rate = high["wickets"] / high["balls"]
        normal_wicket_rate = normal["wickets"] / normal["balls"]
        candidates.append(
            {
                "bowler_id": bowler_id,
                "bowler_name": bowler_name,
                "high_legal_balls": high["balls"],
                "high_runs_conceded": high["runs"],
                "high_wickets": high["wickets"],
                "high_economy": high_economy,
                "high_wicket_rate": high_wicket_rate,
                "normal_legal_balls": normal["balls"],
                "normal_runs_conceded": normal["runs"],
                "normal_wickets": normal["wickets"],
                "normal_economy": normal_economy,
                "normal_wicket_rate": normal_wicket_rate,
                "run_suppression_delta": normal_economy - high_economy,
                "wicket_delta": high_wicket_rate - normal_wicket_rate,
            }
        )

    suppression = [candidate["run_suppression_delta"] for candidate in candidates]
    wickets = [candidate["wicket_delta"] for candidate in candidates]
    suppression_mean = mean(suppression)
    wicket_mean = mean(wickets)
    suppression_sd = standard_deviation(suppression)
    wicket_sd = standard_deviation(wickets)
    prior_balls = math.ceil(percentile(sorted(candidate["high_legal_balls"] for candidate in candidates), 0.50))

    for candidate in candidates:
        candidate["run_suppression_z"] = (candidate["run_suppression_delta"] - suppression_mean) / suppression_sd
        candidate["wicket_delta_z"] = (candidate["wicket_delta"] - wicket_mean) / wicket_sd
        candidate["raw_pressure_score"] = (candidate["run_suppression_z"] + candidate["wicket_delta_z"]) / 2
        candidate["reliability_weight"] = candidate["high_legal_balls"] / (candidate["high_legal_balls"] + prior_balls)
        candidate["adjusted_pressure_score"] = candidate["raw_pressure_score"] * candidate["reliability_weight"]

    candidates.sort(key=lambda candidate: (-candidate["adjusted_pressure_score"], -candidate["high_legal_balls"], candidate["bowler_name"]))
    for rank, candidate in enumerate(candidates, start=1):
        candidate["rank"] = rank

    columns = [
        "rank", "bowler_id", "bowler_name", "high_legal_balls", "high_runs_conceded", "high_wickets", "high_economy",
        "high_wicket_rate", "normal_legal_balls", "normal_runs_conceded", "normal_wickets", "normal_economy",
        "normal_wicket_rate", "run_suppression_delta", "wicket_delta", "run_suppression_z", "wicket_delta_z",
        "raw_pressure_score", "reliability_weight", "adjusted_pressure_score",
    ]
    with (OUTPUT_DIR / "bowling_pressure_rankings.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(candidates)

    with (OUTPUT_DIR / "bowling_rating_method.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["metric", "value"])
        writer.writerows(
            [
                ["comparison_scope", "High-pressure chase balls versus the same bowler's normal-pressure chase balls."],
                ["high_pressure_exposure_population", len(high_exposure)],
                ["high_pressure_exposure_80th_percentile", minimum_exposure],
                ["eligibility", f"At least {minimum_exposure} legal balls in both high- and normal-pressure states."],
                ["eligible_bowlers", len(candidates)],
                ["runs_conceded", "Batting runs plus bowler-attributed extras; byes, leg-byes and penalty runs excluded."],
                ["wicket_credit", "Run outs, retire outs and obstructing-the-field dismissals excluded."],
                ["run_suppression_delta", "Normal-pressure economy minus high-pressure economy."],
                ["wicket_delta", "High-pressure wicket rate minus normal-pressure wicket rate."],
                ["component_standardisation", "Each delta is standardized within the eligible population, then equally weighted."],
                ["reliability_adjustment", f"Raw score multiplied by high_legal_balls / (high_legal_balls + {prior_balls}); {prior_balls} is the median high-pressure exposure of eligible bowlers."],
                ["ranking_metric", "Adjusted pressure score, descending."],
            ]
        )

    print(f"Minimum high/normal-pressure exposure: {minimum_exposure} legal balls")
    print(f"Eligible bowlers: {len(candidates)}")
    print(f"Reliability prior: {prior_balls} high-pressure legal balls")
    print(f"Top-ranked bowler: {candidates[0]['bowler_name']}")


if __name__ == "__main__":
    main()
