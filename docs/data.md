# Private input preparation

## Monitoring panel

Supply one row per `station_id,timestamp` in a CSV. Station IDs are strings; they do not have to reveal site names. Timestamps must be ISO 8601 strings with an explicit offset or `Z`, such as `2023-01-01T00:00:00+03:00`. They are normalized to UTC. Duplicate station/time rows are rejected.

| Column | Meaning |
| --- | --- |
| `station_id` | Nonempty, consistently mapped station identifier. |
| `timestamp` | Measurement time with timezone offset. |
| `pm25` | PM2.5 concentration in µg/m³, nonnegative or missing. |
| `pm10` | Optional PM10 concentration in µg/m³. |
| `h2s`, `no` | Optional H2S and NO concentrations in ppb. |
| `co`, `co2` | Optional CO and CO2 concentrations in ppm. |
| `wind_speed` | Optional wind speed in m/s. |
| `wind_direction` | Optional meteorological direction in degrees, 0–360; 0 is north. |

Numeric values must be finite or missing. Before export, map invalid/sentinel readings to missing using the provider's documentation and align units across files. Do not assume AQI fields are observed pollutant concentrations or independent predictors of their underlying pollutant. The loader rejects negative concentrations and wind speed; it does not choose a scientific quality-control rule for the raw source.

The project notebooks used source-specific fields such as `Station area`, `Station Name`, `Date and Time`, `ParameterSymbol`, and `Parameter Value`. Their names and whitespace differed across files. The package starts with explicit canonical fields instead of guessing station matches or column meanings. For long reports, `long_to_wide` in `data.py` accepts the relevant column names and an explicit duplicate aggregation choice.

An absent row and an explicit missing reading are distinct. The missingness command counts recorded rows and contiguous missing runs; it does not infer operating periods or create a station/time grid. If the intended denominator is scheduled hourly measurements, first expand each station over its documented operating interval, marking absent observations as missing. Do not create artificial expected observations outside a station's coverage period.

## Station coordinates

IDW additionally requires `station_id,x_m,y_m`, one row per station. All coordinates must use one appropriate projected coordinate reference system with distances in metres. Record that CRS in the run's data preparation notes. Do not pass longitude and latitude in degrees to these fields.

The notebooks contained provisional location mappings. They are excluded from this release. Supply verified station coordinates with the required permissions; the code does not infer coordinates from station names. Co-located neighbours receive their mean observed reading rather than an unstable inverse-zero distance weight.

## Statistical-model inputs

`features.py` creates log PM2.5 only for positive observed concentrations. A zero remains a valid concentration for missingness and IDW, but is outside the log-regression sample. Regressions drop rows only for missing outcomes or requested features and report sample counts. They do not drop every row containing a missing value in any unrelated column.

Available generated features are `wind_sin`, `wind_cos`, `log_pm25_lag1`, `log_pm25_lag2`, `wind_co`, `wind_h2s`, `wind_sin_speed`, and `wind_cos_speed`. Interaction features require their constituent columns. Use a time cutoff before fitting and choose predictors that would be available under the intended prediction task.

## Outputs and privacy

Run outputs can include station/time keys, original measurements, masked targets, predictions, and fitted coefficients. Keep them in ignored `outputs/` directories and review any intended release separately. This repository supplies only source code, documentation, and empty input schemas; it contains no monitoring records, station coordinates, saved fit objects, or numerical research results.
