"""
XGBoost + MLflow delay prediction model for Supply Chain AI OS.

- train_delay_model(df): trains XGBoost classifier, logs to MLflow, returns metrics + model path
- predict_delay(features): loads model and returns delay prediction with probability + confidence

Graceful degradation: if xgboost/mlflow not available, falls back to heuristic based on delay_days.
"""

import logging
import os
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# Path for local model artifact storage (used when MLflow registry is unavailable)
_LOCAL_MODEL_DIR = os.getenv("ML_MODEL_DIR", "data/models")
_LOCAL_MODEL_PATH = os.path.join(_LOCAL_MODEL_DIR, "delay_model.json")
_ENCODER_PATH = os.path.join(_LOCAL_MODEL_DIR, "label_encoders.pkl")

_FEATURES = ["supplier_id_enc", "region_enc", "quantity", "unit_price", "order_value", "inventory_level"]
_TARGET = "is_delayed"

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
MLFLOW_EXPERIMENT = "supply_chain_delay_prediction"


def _encode_features(df: pd.DataFrame, encoders: dict | None = None) -> tuple[pd.DataFrame, dict]:
    """
    Label-encode categorical columns (supplier_id, region).
    Returns (encoded_df, encoders_dict).
    If encoders is provided, uses existing mapping (for inference).
    """
    from sklearn.preprocessing import LabelEncoder

    df = df.copy()
    if encoders is None:
        encoders = {}
        for col in ["supplier_id", "region"]:
            le = LabelEncoder()
            df[f"{col}_enc"] = le.fit_transform(df[col].astype(str).fillna("UNKNOWN"))
            encoders[col] = le
    else:
        for col in ["supplier_id", "region"]:
            le = encoders.get(col)
            if le is None:
                df[f"{col}_enc"] = 0
            else:
                known = set(le.classes_)
                df[f"{col}_enc"] = df[col].astype(str).fillna("UNKNOWN").apply(
                    lambda x: le.transform([x])[0] if x in known else 0
                )
    return df, encoders


def _save_encoders(encoders: dict) -> None:
    import pickle
    from pathlib import Path
    Path(_LOCAL_MODEL_DIR).mkdir(parents=True, exist_ok=True)
    with open(_ENCODER_PATH, "wb") as f:
        pickle.dump(encoders, f)


def _load_encoders() -> dict | None:
    import pickle
    from pathlib import Path
    if not Path(_ENCODER_PATH).exists():
        return None
    with open(_ENCODER_PATH, "rb") as f:
        return pickle.load(f)


def train_delay_model(df: pd.DataFrame, extra_feature_cols: list | None = None) -> dict:
    """
    Train XGBoost delay prediction model on the provided DataFrame.

    Expected columns: supplier_id, region, quantity, unit_price, order_value,
    inventory_level, delay_days (used to derive is_delayed).

    extra_feature_cols: additional numeric feature columns (e.g. from feature_engineer)
    to include in training alongside the base _FEATURES.

    Returns:
        {"accuracy": float, "roc_auc": float, "model_path": str}
    """
    # --- Graceful degradation if xgboost/mlflow/sklearn not available ---
    try:
        import xgboost as xgb
        from sklearn.metrics import accuracy_score, roc_auc_score, precision_score, recall_score
        from sklearn.model_selection import train_test_split
    except ImportError as e:
        logger.warning("XGBoost/sklearn not available (%s). Using heuristic fallback.", e)
        return _heuristic_train_result(df)

    # --- Prepare target ---
    df = df.copy()
    df["delay_days"] = pd.to_numeric(df.get("delay_days", 0), errors="coerce").fillna(0)
    df[_TARGET] = (df["delay_days"] > 0).astype(int)

    # Ensure numeric feature columns exist with defaults
    for col, default in [("quantity", 1), ("unit_price", 0.0), ("order_value", 0.0), ("inventory_level", 0.0)]:
        if col not in df.columns:
            df[col] = default
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(default)

    if "supplier_id" not in df.columns:
        df["supplier_id"] = "UNKNOWN"
    if "region" not in df.columns:
        df["region"] = "UNKNOWN"

    df, encoders = _encode_features(df)
    _save_encoders(encoders)

    # Build final feature list: base + validated extra columns from feature_engineer
    active_features = list(_FEATURES)
    if extra_feature_cols:
        for col in extra_feature_cols:
            if col in df.columns and col not in active_features:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
                active_features.append(col)
                logger.info("Including computed feature in training: %s", col)

    X = df[active_features]
    y = df[_TARGET]

    if len(df) < 20:
        logger.warning("Not enough rows (%d) to train. Returning heuristic result.", len(df))
        return _heuristic_train_result(df)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    params = {
        "n_estimators": 100,
        "max_depth": 5,
        "learning_rate": 0.1,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "use_label_encoder": False,
        "eval_metric": "logloss",
        "random_state": 42,
        "n_jobs": -1,
    }
    model = xgb.XGBClassifier(**params)
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    accuracy = float(accuracy_score(y_test, y_pred))
    roc_auc = float(roc_auc_score(y_test, y_prob))
    precision = float(precision_score(y_test, y_pred, zero_division=0))
    recall = float(recall_score(y_test, y_pred, zero_division=0))

    logger.info("Model trained — accuracy=%.4f roc_auc=%.4f precision=%.4f recall=%.4f",
                accuracy, roc_auc, precision, recall)

    # --- Save model locally ---
    from pathlib import Path
    Path(_LOCAL_MODEL_DIR).mkdir(parents=True, exist_ok=True)
    model.save_model(_LOCAL_MODEL_PATH)
    model_path = _LOCAL_MODEL_PATH

    # --- MLflow logging (non-fatal if unavailable) ---
    try:
        import mlflow
        import mlflow.xgboost

        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        mlflow.set_experiment(MLFLOW_EXPERIMENT)

        with mlflow.start_run(run_name="xgboost_delay_classifier") as run:
            mlflow.log_params({k: v for k, v in params.items() if k != "use_label_encoder"})
            mlflow.log_metrics({
                "accuracy": accuracy,
                "roc_auc": roc_auc,
                "precision": precision,
                "recall": recall,
                "train_rows": len(X_train),
                "test_rows": len(X_test),
            })
            mlflow.xgboost.log_model(model, artifact_path="delay_model",
                                     registered_model_name="supply_chain_delay_model")
            model_path = f"runs:/{run.info.run_id}/delay_model"
            logger.info("MLflow run logged: %s", run.info.run_id)
    except Exception as e:
        logger.warning("MLflow logging failed (non-fatal): %s", e)

    return {
        "accuracy": round(accuracy, 4),
        "roc_auc": round(roc_auc, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "model_path": model_path,
        "train_rows": len(X_train),
        "test_rows": len(X_test),
    }


def predict_delay(features: dict) -> dict:
    """
    Predict whether an order will be delayed.

    Args:
        features: dict with keys: supplier_id, region, quantity, unit_price,
                  order_value, inventory_level

    Returns:
        {"is_delayed": bool, "probability": float, "confidence": str, "model_version": str}
    """
    # --- Graceful degradation ---
    try:
        import xgboost as xgb
    except ImportError:
        logger.warning("XGBoost not available. Using heuristic prediction.")
        return _heuristic_predict(features)

    from pathlib import Path

    model = xgb.XGBClassifier()

    # Try loading from MLflow first
    model_version = "local"
    loaded = False

    try:
        import mlflow.xgboost
        mlflow_model = mlflow.xgboost.load_model("models:/supply_chain_delay_model/Production")
        model = mlflow_model
        model_version = "mlflow:Production"
        loaded = True
        logger.debug("Loaded model from MLflow registry (Production stage)")
    except Exception:
        pass

    if not loaded:
        try:
            import mlflow.xgboost
            mlflow_model = mlflow.xgboost.load_model("models:/supply_chain_delay_model/latest")
            model = mlflow_model
            model_version = "mlflow:latest"
            loaded = True
        except Exception:
            pass

    if not loaded:
        if not Path(_LOCAL_MODEL_PATH).exists():
            logger.warning("No trained model found. Using heuristic prediction.")
            return _heuristic_predict(features)
        model.load_model(_LOCAL_MODEL_PATH)
        model_version = "local:xgboost"
        loaded = True

    # Build feature DataFrame
    encoders = _load_encoders()
    row = {
        "supplier_id": features.get("supplier_id", "UNKNOWN"),
        "region": features.get("region", "UNKNOWN"),
        "quantity": float(features.get("quantity", 1)),
        "unit_price": float(features.get("unit_price", 0.0)),
        "order_value": float(features.get("order_value", 0.0)),
        "inventory_level": float(features.get("inventory_level", 0.0)),
    }
    df_row = pd.DataFrame([row])
    df_row, _ = _encode_features(df_row, encoders=encoders)

    # Detect the model's actual feature set (may include computed features from feature_engineer)
    model_feature_names = getattr(model, "feature_names_in_", None)
    if model_feature_names is None:
        try:
            model_feature_names = model.get_booster().feature_names
        except Exception:
            model_feature_names = None

    if model_feature_names is not None:
        # Fill any missing computed features with 0.0 (neutral value)
        for col in model_feature_names:
            if col not in df_row.columns:
                df_row[col] = 0.0
        X = df_row[list(model_feature_names)]
    else:
        X = df_row[_FEATURES]

    prob = float(model.predict_proba(X)[0, 1])
    is_delayed = prob >= 0.5

    if prob >= 0.75:
        confidence = "HIGH"
    elif prob >= 0.5:
        confidence = "MEDIUM"
    else:
        confidence = "LOW"

    return {
        "is_delayed": is_delayed,
        "probability": round(prob, 4),
        "confidence": confidence,
        "model_version": model_version,
    }


# ── Heuristic fallbacks ───────────────────────────────────────────────────────

def _heuristic_train_result(df: pd.DataFrame) -> dict:
    """Simple heuristic result when XGBoost is not available."""
    delay_rate = float((df.get("delay_days", pd.Series([0])) > 0).mean()) if len(df) > 0 else 0.0
    return {
        "accuracy": round(max(delay_rate, 1 - delay_rate), 4),
        "roc_auc": 0.5,
        "precision": 0.0,
        "recall": 0.0,
        "model_path": "heuristic",
        "train_rows": len(df),
        "test_rows": 0,
    }


def _heuristic_predict(features: dict) -> dict:
    """Rule-based fallback when no model is available."""
    quantity = float(features.get("quantity", 1))
    order_value = float(features.get("order_value", 0.0))
    inventory_level = float(features.get("inventory_level", 0.0))

    # Simple heuristic: low inventory + high order value → higher delay risk
    risk_score = 0.0
    if inventory_level < 100:
        risk_score += 0.3
    if order_value > 10000:
        risk_score += 0.2
    if quantity > 500:
        risk_score += 0.15

    prob = min(risk_score, 0.95)
    is_delayed = prob >= 0.35

    confidence = "LOW"  # heuristic is always low confidence

    return {
        "is_delayed": is_delayed,
        "probability": round(prob, 4),
        "confidence": confidence,
        "model_version": "heuristic",
    }
