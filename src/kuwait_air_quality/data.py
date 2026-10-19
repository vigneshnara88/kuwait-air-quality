"""Explicit monitoring-panel input contracts and missingness summaries."""

from pathlib import Path

import numpy as np
import pandas as pd


MEASUREMENTS = ("pm25", "pm10", "h2s", "no", "co", "co2", "wind_speed", "wind_direction")


def parse_timestamp(value: str) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        raise ValueError("Timestamp boundaries require an explicit timezone offset or Z.")
    return timestamp.tz_convert("UTC")


def read_panel(path: Path) -> pd.DataFrame:
    panel = pd.read_csv(path, dtype={"station_id": "string", "timestamp": "string"})
    required = {"station_id", "timestamp", "pm25"}
    if not required.issubset(panel.columns):
        raise ValueError(f"Monitoring input requires {sorted(required)}.")
    if panel.empty or panel["station_id"].fillna("").str.strip().eq("").any():
        raise ValueError("Provide nonempty records and station identifiers.")
    zoned = panel["timestamp"].str.contains(r"(?:Z|[+-]\d{2}:\d{2})$", regex=True).fillna(False)
    if not zoned.all():
        raise ValueError("Every timestamp must include a timezone offset or Z.")
    panel["timestamp"] = pd.to_datetime(panel["timestamp"], format="mixed", utc=True, errors="raise")
    if panel.duplicated(["station_id", "timestamp"]).any():
        raise ValueError("Resolve duplicate station/timestamp records before analysis.")
    for column in MEASUREMENTS:
        if column not in panel:
            continue
        panel[column] = pd.to_numeric(panel[column], errors="raise").astype(float)
        if np.isinf(panel[column]).any() or (panel[column].dropna() < 0).any():
            raise ValueError(f"{column} must be nonnegative and finite, or missing.")
    if "wind_direction" in panel and (panel["wind_direction"].dropna() > 360).any():
        raise ValueError("wind_direction must be in [0, 360] degrees.")
    return panel.sort_values(["station_id", "timestamp"]).reset_index(drop=True)


def long_to_wide(
    records: pd.DataFrame, *, station: str, time: str, pollutant: str, value: str,
    duplicate_rule: str = "error",
) -> pd.DataFrame:
    """Pivot a long report without silently choosing how repeated readings combine."""
    if duplicate_rule not in {"error", "mean", "first"}:
        raise ValueError("duplicate_rule must be error, mean, or first.")
    work = records[[station, time, pollutant, value]].copy()
    if work[[station, time, pollutant]].isna().any().any():
        raise ValueError("Long reports require nonmissing station, time, and pollutant keys.")
    work[value] = pd.to_numeric(work[value], errors="raise")
    keys = [station, time, pollutant]
    if duplicate_rule == "error":
        if work.duplicated(keys).any():
            raise ValueError("Repeated station/time/pollutant readings require an explicit duplicate_rule.")
        values = work.set_index(keys)[value]
    else:
        values = work.groupby(keys, observed=True, sort=False)[value].agg(duplicate_rule)
    result = values.unstack(pollutant).reset_index()
    result.columns.name = None
    return result.rename(columns={station: "station_id", time: "timestamp"})


def missingness_tables(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary, runs = [], []
    columns = [column for column in MEASUREMENTS if column in panel]
    for station, group in panel.groupby("station_id", sort=True):
        group = group.sort_values("timestamp")
        for column in columns:
            missing = group[column].isna()
            summary.append({
                "station_id": station, "variable": column, "n_rows": len(group),
                "n_observed": int((~missing).sum()), "n_missing": int(missing.sum()),
                "missing_fraction": float(missing.mean()),
            })
            breaks = missing.ne(missing.shift()) | group["timestamp"].diff().ne(pd.Timedelta(hours=1))
            for _, run in group.loc[missing].groupby(breaks.cumsum().loc[missing]):
                runs.append({
                    "station_id": station, "variable": column,
                    "start": run["timestamp"].iloc[0], "end": run["timestamp"].iloc[-1],
                    "missing_hours": len(run),
                })
    return pd.DataFrame(summary), pd.DataFrame(
        runs, columns=["station_id", "variable", "start", "end", "missing_hours"]
    )
