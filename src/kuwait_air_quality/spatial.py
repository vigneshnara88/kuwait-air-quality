"""Same-time inverse-distance interpolation from observed neighbouring stations."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist


@dataclass(frozen=True)
class StationNetwork:
    station_to_index: dict[str, int]
    distances: np.ndarray

    @classmethod
    def from_csv(cls, path: Path) -> "StationNetwork":
        stations = pd.read_csv(path, dtype={"station_id": "string"})
        if not {"station_id", "x_m", "y_m"}.issubset(stations):
            raise ValueError("Station input requires station_id, x_m, and y_m.")
        if stations.empty or stations["station_id"].fillna("").str.strip().eq("").any():
            raise ValueError("Supply nonempty station identifiers and coordinates.")
        if stations["station_id"].duplicated().any():
            raise ValueError("Coordinates must have exactly one row per station.")
        xy = stations[["x_m", "y_m"]].apply(pd.to_numeric, errors="raise").to_numpy(dtype=float)
        if not np.isfinite(xy).all():
            raise ValueError("Projected station coordinates must be finite.")
        distances = cdist(xy, xy)
        np.fill_diagonal(distances, np.inf)
        return cls(dict(zip(stations["station_id"], range(len(stations)))), distances)


def idw_value(target: int, snapshot: np.ndarray, network: StationNetwork, power: float, neighbors: int | None) -> float:
    distances = network.distances[target]
    available = np.isfinite(snapshot) & np.isfinite(distances)
    d, values = distances[available], snapshot[available]
    if len(values) == 0:
        return np.nan
    colocated = d == 0
    if colocated.any():
        return float(values[colocated].mean())
    order = np.argsort(d, kind="stable")
    if neighbors is not None:
        order = order[:neighbors]
    d, values = d[order], values[order]
    # Ratios are in (0, 1], avoiding unnecessarily large inverse-distance powers.
    weights = (d.min() / d) ** power
    return float(weights @ values / weights.sum())


def fill_idw(
    panel: pd.DataFrame, network: StationNetwork, *, power: float = 1.0,
    neighbors: int | None = 7,
) -> pd.DataFrame:
    if not np.isfinite(power) or power <= 0:
        raise ValueError("IDW power must be finite and positive.")
    if neighbors is not None and (not isinstance(neighbors, int) or neighbors < 1):
        raise ValueError("neighbors must be a positive integer or None.")
    unknown = set(panel["station_id"]) - set(network.station_to_index)
    if unknown:
        raise ValueError(f"Missing coordinates for {len(unknown)} monitoring station(s).")
    if panel.duplicated(["station_id", "timestamp"]).any():
        raise ValueError("IDW requires unique station/timestamp rows.")
    result = panel.reset_index(drop=True).copy()
    result["pm25_idw"] = result["pm25"].astype(float)
    result["was_imputed"] = False
    for _, group in result.groupby("timestamp", sort=False):
        indices = group["station_id"].map(network.station_to_index).to_numpy(dtype=int)
        snapshot = np.full(len(network.station_to_index), np.nan)
        snapshot[indices] = group["pm25"].to_numpy(dtype=float)
        for row in group.index[group["pm25"].isna()]:
            target = network.station_to_index[result.at[row, "station_id"]]
            estimate = idw_value(target, snapshot, network, power, neighbors)
            result.at[row, "pm25_idw"] = estimate
            result.at[row, "was_imputed"] = np.isfinite(estimate)
    return result
