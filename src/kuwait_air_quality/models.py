"""OLS/HC3 and quantile models with an explicit chronological fitting cutoff."""

import numpy as np
import pandas as pd
import statsmodels.api as sm

from .evaluation import prediction_metrics
from .features import add_features


ALLOWED_FEATURES = {
    "pm10", "h2s", "no", "co", "co2", "wind_speed", "wind_sin", "wind_cos",
    "log_pm25_lag1", "log_pm25_lag2", "wind_co", "wind_h2s",
    "wind_sin_speed", "wind_cos_speed",
}


def fit_regressions(
    panel: pd.DataFrame, *, predictors: list[str], train_before: pd.Timestamp,
    quantiles: tuple[float, ...] = (0.1, 0.5, 0.9),
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    if not predictors or len(set(predictors)) != len(predictors):
        raise ValueError("Provide a nonempty list of distinct predictors.")
    if set(predictors) - ALLOWED_FEATURES:
        raise ValueError(f"Unsupported features: {sorted(set(predictors) - ALLOWED_FEATURES)}")
    if len(set(quantiles)) != len(quantiles) or any(not 0 < q < 1 for q in quantiles):
        raise ValueError("Quantiles must be distinct and strictly between zero and one.")
    frame = add_features(panel)
    if set(predictors) - set(frame):
        raise ValueError(f"Missing predictor inputs: {sorted(set(predictors) - set(frame))}")
    before = frame["timestamp"].lt(train_before)
    complete = np.isfinite(frame[["log_pm25", *predictors]]).all(axis=1)
    training = frame.loc[before & complete]
    evaluation = frame.loc[~before & frame["log_pm25"].notna()]
    predictable = np.isfinite(evaluation[predictors]).all(axis=1)
    if len(training) <= len(predictors) + 1:
        raise ValueError("Too few complete training observations for the requested design.")
    if evaluation.empty:
        raise ValueError("No positive observed PM2.5 values remain after the training cutoff.")
    x_train = sm.add_constant(training[predictors], has_constant="add")
    if np.linalg.matrix_rank(x_train.to_numpy()) != x_train.shape[1]:
        raise ValueError("Training predictors are linearly dependent; revise the specification.")
    y_train = training["log_pm25"]
    models = {"ols_hc3": sm.OLS(y_train, x_train).fit(cov_type="HC3")}
    for q in quantiles:
        models[f"quantile_{q:g}"] = sm.QuantReg(y_train, x_train).fit(q=q, vcov="robust", max_iter=5000)
    coefficients, predictions, scores = [], [], {}
    for name, model in models.items():
        intervals = model.conf_int()
        for term in model.params.index:
            coefficients.append({
                "model": name, "term": term, "estimate": float(model.params[term]),
                "std_error": float(model.bse[term]), "p_value": float(model.pvalues[term]),
                "ci_lower": float(intervals.loc[term, 0]), "ci_upper": float(intervals.loc[term, 1]),
            })
        rows = evaluation[["station_id", "timestamp", "log_pm25"]].copy()
        rows["prediction_log_pm25"] = np.nan
        if predictable.any():
            x_eval = sm.add_constant(evaluation.loc[predictable, predictors], has_constant="add")
            rows.loc[predictable, "prediction_log_pm25"] = model.predict(x_eval)
        rows["model"] = name
        predictions.append(rows)
        scores[name] = prediction_metrics(rows["log_pm25"].to_numpy(), rows["prediction_log_pm25"].to_numpy())
        if name.startswith("quantile_"):
            q = float(name.split("_", 1)[1])
            residual = rows.loc[predictable, "log_pm25"] - rows.loc[predictable, "prediction_log_pm25"]
            scores[name]["pinball_loss"] = float(np.maximum(q * residual, (q - 1) * residual).mean()) if len(residual) else None
            scores[name]["fit_iterations"] = int(model.iterations)
    metadata = {
        "train_before": train_before.isoformat(), "features": predictors,
        "n_training_rows_before_complete_case_filter": int(before.sum()),
        "n_training_complete": len(training), "n_evaluation_targets": len(evaluation),
        "n_evaluation_predictable": int(predictable.sum()),
        "outcome": "natural log of positive observed PM2.5", "scores": scores,
        "evaluation": "conditional held-out-time predictions using observed contemporaneous covariates and exact lags",
    }
    return pd.DataFrame(coefficients), pd.concat(predictions, ignore_index=True), metadata
