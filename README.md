# Kuwait air quality: missingness and PM2.5 modelling

Research code for understanding gaps in a monitoring network and modelling PM2.5 across stations. The workflow combines missingness summaries, inverse-distance-weighted spatial imputation, artificial outage evaluation, and regression models with pollutant and wind features.

## Motivation and research questions

Air-quality analysis depends on where and when measurements are available. A missing reading creates a practical question: can the remaining monitoring network provide useful information about the unobserved concentration, or is there too little evidence to fill the gap? Before drawing conclusions from a completed dataset, it matters which stations have gaps, how long those gaps last, and how well an imputation method performs when pollution is unusually high.

The outcome of interest is **PM2.5**, the concentration of fine particulate matter with a diameter of approximately 2.5 micrometres or smaller. This project studies its measurement and conditional relationships with other available pollutant and weather readings. The research questions connect data quality to what can reasonably be learned from the network:

- **Where are the measurement gaps?** Describe missing readings by station and the duration of consecutive hourly gaps, so isolated missing hours can be distinguished from prolonged outages.
- **Can nearby stations help fill them?** Use observations recorded at the same time at other stations as a spatial baseline, then examine when that baseline can provide a prediction.
- **How informative is that baseline during sustained outages?** Hide blocks of known readings and compare the predictions with the observed values, including errors among high-pollution readings.
- **How does PM2.5 vary with the observed conditions?** Model its relationship with wind, other pollutants, and recent within-station readings, and assess whether the relationships support predictions in a later period.

The aim is to support better-informed choices about data preparation and modelling. A completed panel is useful only if its filled values and remaining gaps are understood; the evaluation therefore reports both prediction error and the share of targets for which a prediction is available.

## Research context and contributions

The project is led by **Dr Ghita Berrada, principal investigator**, and **Dr Huda Alrashidi, co-principal investigator**. Vignesh contributes data preparation, missingness analysis, and the implementation and organisation of analytical workflows. **Oskar contributed spatial modelling and artificial-outage experiments**, documented in the project's working material. The broader research and collaborators' findings remain collaborative work.

This repository packages the analytical methods in reusable Python modules. The monitoring dataset, station coordinates, internal reports, and notebook outputs are not distributed. No model-performance figures are asserted by this code release.

## What the code does

| Component | Implementation |
| --- | --- |
| Preparation | Validate a canonical station/time schema; pivot long pollutant reports with an explicit duplicate rule. |
| Missingness | Count missing measurements by station and summarize the lengths of contiguous hourly gaps. |
| Spatial baseline | Fill missing PM2.5 from observed stations at the same timestamp using inverse-distance weights and an optional nearest-neighbour limit. |
| Outage evaluation | Hide contiguous blocks of observed hourly readings; report prediction coverage, RMSE, MAE, R², and upper-tail error. |
| Feature engineering | Circular wind-direction features, wind/pollutant interactions, and exact one- and two-hour within-station log-PM2.5 lags. |
| Statistical modelling | OLS with HC3 covariance and conditional quantile regressions, fitted before an explicit time cutoff and assessed after it. |

IDW is a spatial interpolation baseline. The regression models use contemporaneous pollutant and weather covariates; they assess conditional relationships and prediction given those inputs. They are not automatically future forecasts or evidence of a causal pollution source.

## How the methods answer the questions

**Start with a station-by-time panel.** Private monitoring records are converted to one row per station and timestamp, with pollutant concentrations and any available wind measurements in consistent fields. Missingness summaries describe the recorded panel. Where the question concerns scheduled monitoring coverage, the input must first include the documented hourly operating grid so that entirely absent rows also count as gaps.

**Build a spatial benchmark.** Inverse-distance weighting, or IDW, estimates a missing reading using a weighted average of other stations' observed readings at that same time. Closer stations receive greater weight, with the distance power and neighbour limit controlling how local the estimate is. This gives a clear reference method against which more elaborate approaches could be compared. It also makes the coverage question explicit: if no suitable neighbour is observed, the estimate remains missing.

**Evaluate against readings that are actually known.** Artificial outages temporarily hide consecutive hours with observed PM2.5 and retain those readings as comparison targets. The resulting errors show how the method behaves under that particular outage design. MAE summarizes the average absolute error; RMSE puts more weight on large misses; prediction coverage records how often the method can supply an estimate. Upper-tail errors focus attention on high observed concentrations that an overall average could obscure. These comparisons evaluate a method rather than establish that real outages occur randomly.

**Model average and distributional relationships.** The regression workflow uses the natural logarithm of positive PM2.5 as its outcome. Wind direction becomes sine and cosine features so that directions near 0° and 360° remain adjacent. Recent PM2.5 readings are matched at exact one- and two-hour intervals within each station. Other pollutant levels and selected interactions can enter as explanatory features.

Ordinary least squares describes the conditional mean of log PM2.5. Quantile regression examines selected parts of its conditional distribution: for example, a model for the 90th percentile asks how relatively high concentrations vary with the included inputs. These are different statistical targets, so a quantile prediction should be interpreted at its chosen percentile rather than as another estimate of the mean. A chronological fitting cutoff separates earlier training observations from later evaluation targets.

The outputs connect these steps: station-level gap summaries identify the data-quality problem; masked-outage predictions and coverage describe the spatial baseline; and coefficient tables, held-out predictions, and error summaries describe the regression specifications. They support comparisons of modelling choices and conditional patterns. Identifying the causal effect of an emissions source or intervention would require an additional research design.

## Install

```bash
python -m pip install -e .
```

Use the headers in `templates/` to prepare private inputs under `data/`. Read [the data contract](docs/data.md) before running the commands. No coordinates, station identifiers, or observations are included in the templates.

```bash
kuwait-air-quality missingness --data data/monitoring.csv --output outputs/missingness

kuwait-air-quality idw --data data/monitoring.csv --stations data/stations.csv --power 1 --neighbors 7 --output outputs/idw

kuwait-air-quality evaluate-idw --data data/monitoring.csv --stations data/stations.csv --start 2023-01-01T00:00:00+03:00 --end 2024-01-01T00:00:00+03:00 --outage-hours 168 --blocks-per-station 3 --power 1 --neighbors 7 --output outputs/outage-evaluation

kuwait-air-quality regress --data data/monitoring.csv --train-before 2023-01-01T00:00:00+03:00 --features wind_sin wind_cos log_pm25_lag1 pm10 h2s no co co2 --output outputs/regression
```

Dates above illustrate the command syntax; choose time windows appropriate to the available records. Output folders must be new, which keeps separate runs distinct. Commands write CSV tables and JSON metadata locally. There is no automatic data download or upload.

## Analytical choices

- IDW uses only genuinely observed neighbours in the same timestamp snapshot. It does not feed imputed values back in as additional neighbours. Missing values remain missing when no neighbour is available.
- Outages span consecutive **clock hours** with observed target readings. They are not arbitrary blocks of surviving rows across gaps. The generator records how many requested blocks could actually be placed.
- Error summaries include coverage. A low error on the subset with predictions does not imply that every outage could be filled.
- Wind direction enters as sine and cosine. Lags are matched by station and timestamp, so they cannot cross station boundaries or treat a multi-hour gap as a one-hour lag.
- Regression fitting precedes the chosen cutoff. Held-out predictions can use an actually observed prior-hour PM2.5 value; this is a conditional evaluation, not a recursive multi-step forecast.
- Extreme readings remain in the evaluation. The upper-tail summary helps expose errors that an overall average can hide.

Use separate validation and final evaluation periods when choosing IDW power, neighbour count, model features, or quantiles. Synthetic outages evaluate a specified masking design; they do not establish performance under every real failure mechanism. HC3 adjusts for heteroskedasticity, not serial or spatial dependence.

## Layout

```text
src/kuwait_air_quality/
  data.py        input contracts, report pivoting, missingness
  features.py    wind transforms and exact within-station lags
  spatial.py     spatial distances and IDW
  evaluation.py  contiguous outages and coverage-aware error summaries
  models.py      OLS/HC3 and quantile regression
  cli.py         file-based commands and metadata
docs/
  data.md        private input preparation
  source_notes.md  workflow provenance and contribution boundaries
templates/       empty CSV schemas
```

See [source notes](docs/source_notes.md) for the methods and contribution credits.
