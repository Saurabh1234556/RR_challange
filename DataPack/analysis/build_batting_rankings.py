#!/usr/bin/env python3
"""Rate batters against their own normal-pressure chase baseline."""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR if (SCRIPT_DIR / "ball_by_ball.csv").exists() else SCRIPT_DIR.parent
OUTPUT_DIR = ROOT / "analysis"
SOURCE = OUTPUT_DIR / "batting_pressure_deliveries.tsv"


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
    player_bands = defaultdict(lambda: defaultdict(lambda: {"balls": 0, "runs": 0, "dismissals": 0}))
    with SOURCE.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            band = row["batting_pressure_band"]
            if band not in {"high", "normal"} or row["extras_type"] == "wide":
                continue
            key = (row["striker_id"], row["striker_name"])
            values = player_bands[key][band]
            values["balls"] += 1
            values["runs"] += int(row["runs"])
            values["dismissals"] += row["is_wicket"].lower() == "true" and row["dismissed_player_id"] == row["striker_id"]

    high_exposure = sorted(values["high"]["balls"] for values in player_bands.values() if values["high"]["balls"])
    minimum_exposure = math.ceil(percentile(high_exposure, 0.80))
    candidates = []
    for (player_id, player_name), values in player_bands.items():
        high = values["high"]
        normal = values["normal"]
        if high["balls"] < minimum_exposure or normal["balls"] < minimum_exposure:
            continue
        high_run_rate = high["runs"] / high["balls"]
        normal_run_rate = normal["runs"] / normal["balls"]
        high_dismissal_rate = high["dismissals"] / high["balls"]
        normal_dismissal_rate = normal["dismissals"] / normal["balls"]
        candidates.append({
            "striker_id": player_id, "striker_name": player_name, "high_balls": high["balls"], "high_runs": high["runs"],
            "high_dismissals": high["dismissals"], "high_runs_per_ball": high_run_rate, "high_dismissal_rate": high_dismissal_rate,
            "normal_balls": normal["balls"], "normal_runs": normal["runs"], "normal_dismissals": normal["dismissals"],
            "normal_runs_per_ball": normal_run_rate, "normal_dismissal_rate": normal_dismissal_rate,
            "scoring_delta": high_run_rate - normal_run_rate, "survival_delta": normal_dismissal_rate - high_dismissal_rate,
        })

    scoring_deltas = [candidate["scoring_delta"] for candidate in candidates]
    survival_deltas = [candidate["survival_delta"] for candidate in candidates]
    scoring_mean, survival_mean = mean(scoring_deltas), mean(survival_deltas)
    scoring_sd, survival_sd = standard_deviation(scoring_deltas), standard_deviation(survival_deltas)
    prior_balls = math.ceil(percentile(sorted(candidate["high_balls"] for candidate in candidates), 0.50))
    for candidate in candidates:
        candidate["scoring_delta_z"] = (candidate["scoring_delta"] - scoring_mean) / scoring_sd
        candidate["survival_delta_z"] = (candidate["survival_delta"] - survival_mean) / survival_sd
        candidate["raw_pressure_score"] = (candidate["scoring_delta_z"] + candidate["survival_delta_z"]) / 2
        candidate["reliability_weight"] = candidate["high_balls"] / (candidate["high_balls"] + prior_balls)
        candidate["adjusted_pressure_score"] = candidate["raw_pressure_score"] * candidate["reliability_weight"]

    candidates.sort(key=lambda candidate: (-candidate["adjusted_pressure_score"], -candidate["high_balls"], candidate["striker_name"]))
    for rank, candidate in enumerate(candidates, start=1):
        candidate["rank"] = rank

    columns = [
        "rank", "striker_id", "striker_name", "high_balls", "high_runs", "high_dismissals", "high_runs_per_ball",
        "high_dismissal_rate", "normal_balls", "normal_runs", "normal_dismissals", "normal_runs_per_ball",
        "normal_dismissal_rate", "scoring_delta", "survival_delta", "scoring_delta_z", "survival_delta_z",
        "raw_pressure_score", "reliability_weight", "adjusted_pressure_score",
    ]
    with (OUTPUT_DIR / "batting_pressure_rankings.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(candidates)

    with (OUTPUT_DIR / "batting_rating_method.tsv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(["metric", "value"])
        writer.writerows([
            ["comparison_scope", "High-pressure chase balls versus the same batter's normal-pressure chase balls."],
            ["high_pressure_exposure_population", len(high_exposure)],
            ["high_pressure_exposure_80th_percentile", minimum_exposure],
            ["eligibility", f"At least {minimum_exposure} balls faced in both high- and normal-pressure states."],
            ["eligible_batters", len(candidates)],
            ["scoring_delta", "High-pressure runs per ball minus normal-pressure runs per ball."],
            ["survival_delta", "Normal-pressure dismissal rate minus high-pressure dismissal rate; positive is better."],
            ["component_standardisation", "Each delta is standardized within the eligible population, then equally weighted."],
            ["reliability_adjustment", f"Raw score multiplied by high_balls / (high_balls + {prior_balls}); {prior_balls} is the median high-pressure exposure of eligible batters."],
            ["ranking_metric", "Adjusted pressure score, descending."],
        ])

    print(f"Minimum high/normal-pressure exposure: {minimum_exposure} balls")
    print(f"Eligible batters: {len(candidates)}")
    print(f"Reliability prior: {prior_balls} high-pressure balls")
    print(f"Top-ranked batter: {candidates[0]['striker_name']}")


if __name__ == "__main__":
    main()
