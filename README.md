# Kuwait air quality: missingness and PM2.5 modelling

Research code for understanding gaps in a monitoring network and modelling PM2.5 across stations. The workflow combines missingness summaries, inverse-distance-weighted spatial imputation, artificial outage evaluation, and regression models with pollutant and wind features.

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
