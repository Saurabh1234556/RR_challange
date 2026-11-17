# SupeRR Selector Season 2 — Round 1 Analysis Record

## Objective

Identify the batters and bowlers who perform best in high-pressure T20 chases relative to their own normal-pressure performance. The analysis uses the supplied IPL and T20I data from 2022 onward.

## Source Data and Audit

The source pack contains delivery data, match metadata, playing-squad data, competition/team references, player mappings and the challenge brief. The detailed inventory is in `data_audit_record.tsv`.

Key audit findings:

- 200,999 raw deliveries across 883 matches.
- Match dates range from 22 January 2022 to 1 November 2026.
- All delivery, playing-XI, competition and team foreign-key checks passed.
- Nineteen matches are abandoned. Sixteen have no deliveries and three have partial deliveries.
- All abandoned matches were excluded, leaving 200,741 deliveries across 864 matches and 1,721 innings.
- `playing_eleven.csv` includes squad members as well as players who appeared; use `is_played = true` for participation analysis.

## Analytical Scope

The pressure model is intentionally limited to second-innings chases. A chase has an observable target, required run rate, wickets in hand and balls remaining. This avoids imposing an invented target on first-innings batting.

The raw data was not changed. Derived files were written as TSV files.

## Delivery-Level Context

For each eligible delivery, the clean base calculates:

- score before and after the delivery;
- wickets before and after the delivery;
- legal balls used and balls remaining;
- scheduled innings balls, with revised-overs fields used where supplied;
- chase target, runs required and required run rate;
- innings phase: powerplay, middle or death.

Wides and no-balls are not counted as legal balls for resource calculations.

## Batting Pressure Definition

Eligible chase states are deliveries in innings two before the target is reached and while balls remain.

The batting pressure index is the equally weighted mean of three normalised pre-ball measures:

1. Required-run-rate percentile among all eligible chase states.
2. Wickets-lost share: wickets lost divided by 10.
3. Time pressure: one minus balls remaining divided by scheduled balls.

Equal weights were used because the dataset does not support a defensible prior weighting of urgency, required rate and wicket loss. This is more transparent than hand-picking a single required-run-rate cutoff.

Observed data cutoffs:

- 95,177 eligible chase deliveries.
- Required-run-rate median: 9.538.
- Required-run-rate 75th percentile: 11.891.
- Pressure-index median: 0.3705.
- Pressure-index 75th percentile: 0.5517.

Bands are normal below the median, moderate from the median to the 75th percentile, and high at or above the 75th percentile. This labels 23,795 high-pressure deliveries.

## Batter Rating

Only high- and normal-pressure states are used in the primary comparison. Moderate states are excluded so that the contrast is clear.

For each batter:

- scoring delta = high-pressure runs per ball minus normal-pressure runs per ball;
- survival delta = normal-pressure dismissal rate minus high-pressure dismissal rate.

Both deltas are standardized in the eligible population and equally weighted. A positive value means a batter scores faster and/or is dismissed less often under high pressure than in normal pressure.

Eligibility is data-derived: at least 53 balls faced in both high- and normal-pressure states. This is the 80th percentile of the high-pressure exposure distribution. Forty-eight batters qualify.

The raw score is multiplied by `high-pressure balls / (high-pressure balls + 108)`. The 108-ball prior is the median high-pressure exposure among qualifying batters and shrinks small-sample scores toward the population average.

## Bowler Rating

The same delivery-level pressure labels are used from the defending team’s perspective.

For each bowler:

- run-suppression delta = normal-pressure economy minus high-pressure economy;
- wicket delta = high-pressure wicket rate minus normal-pressure wicket rate.

Runs conceded exclude byes, leg-byes and penalty runs. Wides and no-balls are not legal balls. Run outs, retire outs and obstructing-the-field dismissals are excluded from bowler wicket credit.

Both components are standardized and equally weighted. Bowlers need at least 84 legal balls in both high- and normal-pressure states; this is the 80th percentile of high-pressure bowling exposure. Seventy-nine bowlers qualify. A 143-ball median-exposure prior is used for reliability shrinkage.

## Robustness Checks

Six threshold models were tested for both disciplines:

- high-pressure cutoff at the 70th, 75th and 80th percentiles;
- eligibility cutoff at the 75th and 80th percentiles of high-pressure exposure.

Batting top-10 overlap with the primary model ranges from 6/10 to 9/10. Bowling top-10 overlap ranges from 7/10 to 9/10.

Leave-one-season-out checks were also run. Competition-specific IPL and T20I rankings differ materially, so format evidence is reported as a confidence flag rather than used to alter ranks after the fact.

## Cricket Context Addendum

The model uses cricket knowledge where the data supports it, but does not add correlated factors as arbitrary extra weights.

- Death overs are identified directly from `overid` (overs 16-20). They are reported as supporting evidence because elapsed-ball share is already part of the pressure index. Adding a separate death-over weight would double count the same match-state pressure.
- Wickets in hand are already included continuously through wickets lost in the pressure index. A low-wicket split (five or fewer wickets in hand) is retained as batting evidence rather than an additional score weight.
- Yorkers and wide yorkers are explicitly labelled in the raw data. High-pressure death-over yorker economy, wicket count and yorker share are reported for bowlers. They are not a ranking weight because the number of yorker attempts differs greatly between bowlers and a high attempt count is not automatically good execution.
- Immediate post-boundary recovery is calculated as the next legal ball in the same over after a high-pressure four or six. It is reported as evidence of recovery, not as a claim about unobserved mentality.
- Batter handedness, bowling type, pace/spin, line and delivery style are available. They are reserved for a future match-up model because fair inclusion requires sufficient player-versus-context sample sizes and validation.

This approach adds cricket-specific evidence without overfitting the core ranking to sparse or overlapping signals.

## Matchup-Controlled Challenger

The supplied data also records batting handedness, bowling type and pace/spin. A challenger evidence module now controls batter results for pace versus spin and bowler results for right-handed versus left-handed batters.

Each matchup stratum requires at least 12 high-pressure and 12 normal-pressure balls, equivalent to two overs in each state. This produces 230 valid batting matchup rows and 380 valid bowling matchup rows.

The matchup tables are evidence outputs rather than current ranking weights. They can be promoted only if a leave-one-season-out validation shows that the matchup-adjusted ranking is at least as stable as the current ranking. This prevents a plausible cricket feature from weakening the model through sparse or unvalidated context splits.

The validation was completed. The core batting model retained an average of 7.75 of its top 10 under leave-one-season-out testing, compared with 7.50 for the pace/spin matchup challenger. The core bowling model retained 7.50, compared with 7.25 for the handedness challenger. The matchup-adjusted models are therefore not promoted into the final rank score.

## Interpretation and Limitations

- The rankings measure relative improvement under pressure, not absolute career ability.
- The model uses chases only; first-innings pressure is deliberately not claimed.
- Match roles and opportunities differ between IPL and T20I. A format-evidence flag accompanies the final shortlist.
- Positions with weaker sensitivity results should be described as provisional in the final report.
- Rankings are based on the supplied data only and should not be interpreted as a universal measure of player quality.

## Final Ranked Lists

The batting and bowling ordered lists, evidence flags and confidence notes are in `batting_final_ranking_with_evidence.tsv` and `bowling_final_ranking_with_evidence.tsv`.
