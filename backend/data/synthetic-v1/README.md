# Synthetic Terra Clinic datasets, version 1

These fixtures represent one fictional outpatient clinic. All text and counts are generated. The public references informed the structure. No hospital records were copied and the statistical distributions have not been calibrated to an observed clinic.

## Document retrieval

Index only `rag/documents/`. The eight original English guides cover arrival, opening hours, bookings, cancellations, wayfinding and privacy. Each guide is a searchable, single-page PDF. Use the sibling `rag/evaluation.jsonl` for evaluation. Sixteen questions have an expected filename, page and literal supporting span. Four questions have no supporting document. Measure retrieval accuracy, correct citations and abstention separately. This is a small functional benchmark with two paraphrased questions per topic, suitable for demonstrating retrieval and grounding.

The organization follows public outpatient patient-information materials such as the [NHS outpatient guide](https://www.nhs.uk/nhs-services/hospitals/going-into-hospital/as-an-outpatient-or-day-patient/). Operational details follow the fictional Terra guides and demo floor directory.

## Daily appointment regression

`linear-regression/daily-demand.xlsx` has one row for each IST calendar date in 2023–2025. Each row reports the final status of appointments scheduled for that day. The target `demand` counts completed visits plus no-shows, equal to booked minus cancelled. It measures non-cancelled scheduled load. Latent demand from patients unable to obtain slots is unobserved.

Use weekday (Monday = 0), elapsed time, published capacity and historical demand as predictors. Capacity assumes six clinicians and half-hour slots. The generator models a weekday pattern, annual seasonality, gradual growth, correlated daily fluctuations, occasional staffing reductions and random cancellations and no-shows. Sundays and three specified calendar holidays have zero capacity. All rates and closures are simulation choices.

`demand_lag_7d` is demand seven calendar days earlier. `demand_mean_prior_4_weekdays` averages the four previous occurrences of the target weekday. Initial blanks indicate insufficient history. Exclude same-day booked, cancelled, completed and no_show from predictors because they reveal the target. For forecasts spanning multiple days, construct all features from history available at the forecast origin.

Use the supplied chronological split: 912 training days through June 2025, 92 validation days in July–September, and 92 test days in October–December. Compare regression with a same-weekday baseline using identical forecast origins. Report open-day error alongside all-day error.

[NHS England general practice appointment statistics](https://digital.nhs.uk/data-and-information/publications/statistical/appointments-in-general-practice/appointments-in-general-practice-supporting-information) informed the scheduling and attendance vocabulary. [AIIMS Raipur](https://www.aiimsraipur.edu.in/user/monthly-achivement.php) publishes monthly average daily OPD attendance, a different measure from this daily scheduled-load target.

## Reproduction

From the repository root, run `scripts/generate_training_sets.py` with the bundled Python runtime containing ReportLab and the companion Node artifact runtime to regenerate both releases. Seed 8241 controls the daily simulation. Verification loaded the guides through the application's chunker, checked all labelled evidence spans, reconciled the daily counts and historical features, and fitted the existing demand trainer on the training split.
