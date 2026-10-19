"""Contiguous artificial outages and error summaries that retain coverage."""

import numpy as np
import pandas as pd

from .spatial import StationNetwork, fill_idw


def make_outages(
    panel: pd.DataFrame, *, start: pd.Timestamp, end: pd.Timestamp,
    hours: int = 168, blocks_per_station: int = 3, seed: int = 42,
) -> tuple[np.ndarray, list[dict]]:
    if start >= end or hours < 1 or blocks_per_station < 1:
        raise ValueError("Use an ordered time window and positive outage length/count.")
    if panel.duplicated(["station_id", "timestamp"]).any():
        raise ValueError("Outage generation requires unique station/timestamp rows.")
    frame = panel.reset_index(drop=True)
    mask = np.zeros(len(frame), dtype=bool)
    rng = np.random.default_rng(seed)
    placed = []
    for station, group in frame.groupby("station_id", sort=True):
        group = group.sort_values("timestamp")
        eligible = group["pm25"].notna() & group["timestamp"].ge(start) & group["timestamp"].lt(end)
        observed_window = eligible.rolling(hours, min_periods=hours).sum().eq(hours)
        if hours == 1:
            consecutive = pd.Series(True, index=group.index)
        else:
            hourly_step = group["timestamp"].diff().eq(pd.Timedelta(hours=1))
            consecutive = hourly_step.rolling(hours - 1, min_periods=hours - 1).sum().eq(hours - 1)
        candidate_ends = np.flatnonzero((observed_window & consecutive).to_numpy())
        count = 0
        for last in rng.permutation(candidate_ends):
            rows = group.index[last - hours + 1:last + 1].to_numpy()
            if mask[rows].any():
                continue
            mask[rows] = True
            placed.append({
                "station_id": station, "start": frame.loc[rows[0], "timestamp"].isoformat(),
                "end": frame.loc[rows[-1], "timestamp"].isoformat(), "hours": hours,
            })
            count += 1
            if count == blocks_per_station:
                break
    return mask, placed


def _metrics(truth: np.ndarray, predicted: np.ndarray) -> dict:
    valid_truth = np.isfinite(truth)
    scored = valid_truth & np.isfinite(predicted)
    n_total, n_scored = int(valid_truth.sum()), int(scored.sum())
    result = {
        "n_targets": n_total, "n_scored": n_scored,
        "coverage": n_scored / n_total if n_total else None,
        "rmse": None, "mae": None, "r2": None,
    }
    if n_scored:
        error = predicted[scored] - truth[scored]
        result["rmse"] = float(np.sqrt(np.mean(error**2)))
        result["mae"] = float(np.mean(np.abs(error)))
        denominator = float(np.sum((truth[scored] - truth[scored].mean())**2))
        if n_scored > 1 and denominator > 0:
            result["r2"] = float(1 - np.sum(error**2) / denominator)
    return result


def prediction_metrics(truth: np.ndarray, predicted: np.ndarray, *, tail_quantile: float = 0.9) -> dict:
    truth = np.asarray(truth, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    if truth.shape != predicted.shape or truth.ndim != 1:
        raise ValueError("Truth and prediction must be equally sized one-dimensional arrays.")
    if not 0 < tail_quantile < 1:
        raise ValueError("tail_quantile must be strictly between zero and one.")
    known = np.isfinite(truth)
    threshold = float(np.quantile(truth[known], tail_quantile)) if known.any() else None
    tail = known & (truth >= threshold) if threshold is not None else np.zeros(len(truth), dtype=bool)
    return {
        "overall": _metrics(truth, predicted),
        "tail_quantile": tail_quantile, "tail_threshold": threshold,
        "upper_tail": _metrics(truth[tail], predicted[tail]),
    }


def evaluate_idw(
    panel: pd.DataFrame, network: StationNetwork, *, start: pd.Timestamp, end: pd.Timestamp,
    hours: int = 168, blocks_per_station: int = 3, seed: int = 42,
    power: float = 1.0, neighbors: int | None = 7,
) -> tuple[pd.DataFrame, dict]:
    frame = panel.reset_index(drop=True)
    mask, placed = make_outages(
        frame, start=start, end=end, hours=hours,
        blocks_per_station=blocks_per_station, seed=seed,
    )
    if not mask.any():
        raise ValueError("No fully observed contiguous hourly outage blocks fit in the selected window.")
    hidden = frame.copy()
    hidden.loc[mask, "pm25"] = np.nan
    filled = fill_idw(hidden, network, power=power, neighbors=neighbors)
    scored = frame.loc[mask, ["station_id", "timestamp", "pm25"]].rename(columns={"pm25": "truth"}).copy()
    scored["prediction"] = filled.loc[mask, "pm25_idw"].to_numpy()
    metadata = prediction_metrics(scored["truth"].to_numpy(), scored["prediction"].to_numpy())
    metadata.update({
        "units": "micrograms per cubic metre", "seed": seed,
        "start_inclusive": start.isoformat(), "end_exclusive": end.isoformat(),
        "outage_hours": hours, "requested_blocks_per_station": blocks_per_station,
        "requested_blocks_total": int(frame["station_id"].nunique()) * blocks_per_station,
        "placed_blocks_total": len(placed), "blocks": placed,
        "power": power, "neighbors": neighbors,
    })
    return scored.reset_index(drop=True), metadata
