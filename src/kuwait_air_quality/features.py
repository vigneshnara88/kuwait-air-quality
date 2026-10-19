"""Wind transforms and exact elapsed-time lags within stations."""

import numpy as np
import pandas as pd


def add_features(panel: pd.DataFrame) -> pd.DataFrame:
    frame = panel.sort_values(["station_id", "timestamp"]).reset_index(drop=True).copy()
    frame["log_pm25"] = np.log(frame["pm25"].where(frame["pm25"].gt(0)))
    history = frame.set_index(["station_id", "timestamp"])["log_pm25"]
    for hours in (1, 2):
        lookup = pd.MultiIndex.from_arrays([
            frame["station_id"], frame["timestamp"] - pd.Timedelta(hours=hours),
        ], names=["station_id", "timestamp"])
        frame[f"log_pm25_lag{hours}"] = history.reindex(lookup).to_numpy()
    if "wind_direction" in frame:
        angle = np.deg2rad(frame["wind_direction"])
        frame["wind_sin"] = np.sin(angle)
        frame["wind_cos"] = np.cos(angle)
    if "wind_speed" in frame:
        for column in ("co", "h2s"):
            if column in frame:
                frame[f"wind_{column}"] = frame["wind_speed"] * frame[column]
        for column in ("wind_sin", "wind_cos"):
            if column in frame:
                frame[f"{column}_speed"] = frame["wind_speed"] * frame[column]
    return frame
