"""
ML router — delay prediction endpoint.

POST /ml/predict
    Accepts order feature JSON, returns XGBoost delay prediction.
    Falls back to heuristic if model has not been trained yet.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


class DelayPredictRequest(BaseModel):
    supplier_id: str = Field(..., description="Supplier identifier")
    region: str = Field(..., description="Destination region / port")
    quantity: int = Field(..., ge=1, description="Order quantity (units)")
    unit_price: float = Field(..., ge=0.0, description="Unit price (USD)")
    order_value: float = Field(..., ge=0.0, description="Total order value (USD)")
    inventory_level: float = Field(..., ge=0.0, description="Current inventory level at destination")


class DelayPredictResponse(BaseModel):
    is_delayed: bool
    probability: float
    confidence: str
    model_version: str


@router.post("/predict", response_model=DelayPredictResponse, summary="Predict order delay probability")
async def predict_delay_endpoint(request: DelayPredictRequest):
    """
    Predict whether an order is likely to be delayed.

    Uses the trained XGBoost model (logged via MLflow). If the model has not
    been trained yet, returns a rule-based heuristic prediction with
    model_version='heuristic'.
    """
    features = {
        "supplier_id": request.supplier_id,
        "region": request.region,
        "quantity": request.quantity,
        "unit_price": request.unit_price,
        "order_value": request.order_value,
        "inventory_level": request.inventory_level,
    }

    try:
        from pipeline.ml_model import predict_delay
        result = predict_delay(features)
    except ImportError as e:
        logger.warning("pipeline.ml_model import failed (%s). Using inline heuristic.", e)
        result = _inline_heuristic(features)
    except Exception as e:
        logger.error("predict_delay raised an unexpected error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Prediction failed: {e}")

    return DelayPredictResponse(
        is_delayed=result["is_delayed"],
        probability=result["probability"],
        confidence=result["confidence"],
        model_version=result.get("model_version", "unknown"),
    )


def _inline_heuristic(features: dict) -> dict:
    """Minimal heuristic used when pipeline.ml_model cannot be imported."""
    order_value = float(features.get("order_value", 0))
    inventory_level = float(features.get("inventory_level", 0))
    quantity = float(features.get("quantity", 1))

    risk = 0.0
    if inventory_level < 100:
        risk += 0.3
    if order_value > 10000:
        risk += 0.2
    if quantity > 500:
        risk += 0.15

    prob = min(risk, 0.95)
    return {
        "is_delayed": prob >= 0.35,
        "probability": round(prob, 4),
        "confidence": "LOW",
        "model_version": "heuristic",
    }
