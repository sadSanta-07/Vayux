import time
import numpy as np
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

from ml.foundation_loader import FoundationEngineLoader
from ml.residual_adapter import PhysicsResidualAdapter

router = APIRouter(prefix="/api/v1", tags=["Forecast Engine"])

foundation_loader = FoundationEngineLoader(model_id="amazon/chronos-bolt-tiny", device="cpu")
physics_adapter = PhysicsResidualAdapter()

class ForecastRequest(BaseModel):
    latitude: float = Field(default=28.6139, example=28.6139)
    longitude: float = Field(default=77.2090, example=77.2090)
    history_pm25: List[float] = Field(default_factory=lambda: [140.0 + 20.0*np.sin(i/3.0) for i in range(168)])
    h_base: Optional[List[float]] = Field(default=None)
    u_wind: Optional[List[float]] = Field(default=None)
    v_wind: Optional[List[float]] = Field(default=None)
    fire_hotspots: Optional[List[Dict[str, Any]]] = Field(default_factory=list)

class ForecastResponse(BaseModel):
    status: str
    execution_time_ms: float
    horizon_hours: int
    pm25_p10: List[float]
    pm25_p50: List[float]
    pm25_p90: List[float]
    aqi_p50: List[int]

def pm25_to_indian_aqi(pm25: float) -> int:
    """Calculates standard Indian AQI breakpoints from raw PM2.5 concentrations."""
    c = max(0.0, pm25)
    if c <= 30.0:
        return int((50.0 / 30.0) * c)
    elif c <= 60.0:
        return int(50 + ((100 - 50) / (60 - 30)) * (c - 30))
    elif c <= 90.0:
        return int(100 + ((200 - 100) / (90 - 60)) * (c - 60))
    elif c <= 120.0:
        return int(200 + ((300 - 200) / (120 - 90)) * (c - 90))
    elif c <= 250.0:
        return int(300 + ((400 - 300) / (250 - 120)) * (c - 120))
    else:
        return min(500, int(400 + ((500 - 400) / (380 - 250)) * (c - 250)))

@router.post("/forecast", response_model=ForecastResponse)
async def generate_hybrid_forecast(payload: ForecastRequest):
    t_start = time.perf_counter()
    horizon = 72

    try:
        p10_base, p50_base, p90_base = foundation_loader.predict_zero_shot(
            history_pm25=payload.history_pm25,
            prediction_length=horizon
        )

        h_base = np.array(payload.h_base) if payload.h_base and len(payload.h_base) == horizon \
            else np.full(horizon, 450.0)
        u_wind = np.array(payload.u_wind) if payload.u_wind and len(payload.u_wind) == horizon \
            else np.full(horizon, 1.8)
        v_wind = np.array(payload.v_wind) if payload.v_wind and len(payload.v_wind) == horizon \
            else np.full(horizon, 0.9)

        p10_coupled = physics_adapter.apply_coupling(
            p10_base, h_base, u_wind, v_wind, payload.latitude, payload.longitude, payload.fire_hotspots
        )
        p50_coupled = physics_adapter.apply_coupling(
            p50_base, h_base, u_wind, v_wind, payload.latitude, payload.longitude, payload.fire_hotspots
        )
        p90_coupled = physics_adapter.apply_coupling(
            p90_base, h_base, u_wind, v_wind, payload.latitude, payload.longitude, payload.fire_hotspots
        )

        raw_aqi_p50 = [pm25_to_indian_aqi(val) for val in p50_coupled]
        aqi_p50: List[int] = []
        for h, val in enumerate(raw_aqi_p50):
            if h == 0:
                aqi_p50.append(val)
            else:
                prev = aqi_p50[h - 1]
                delta = val - prev
                if delta > 35:
                    clamped = prev + 35
                elif delta < -35:
                    clamped = prev - 35
                else:
                    clamped = val
                aqi_p50.append(int(max(0, min(500, clamped))))

        t_elapsed_ms = (time.perf_counter() - t_start) * 1000.0

        return ForecastResponse(
            status="SUCCESS",
            execution_time_ms=round(t_elapsed_ms, 2),
            horizon_hours=horizon,
            pm25_p10=np.round(p10_coupled, 2).tolist(),
            pm25_p50=np.round(p50_coupled, 2).tolist(),
            pm25_p90=np.round(p90_coupled, 2).tolist(),
            aqi_p50=aqi_p50
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Hybrid forecast engine error: {str(err)}"
        )