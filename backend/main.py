import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

from fastapi import FastAPI, WebSocket, Body ,APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import datetime

from physics import calculate_effective_pblh, compute_plume_dispersion
from policy import simulate_policy_impact
from live_data import fetch_live_weather, fetch_live_fires
from ml_forecast import router as forecast_router
from jarvis.live_session import handle_jarvis_live_websocket
from ml.model_selector import select_best_reasoning_model, delegate_background_task

app = FastAPI(
    title="vayuX Coupled Atmospheric & Jarvis Intelligence Engine",
    description="Physics-informed aerosol-meteorology modeling with real-time voice Jarvis co-pilot for SIH 2026",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(forecast_router)

@app.websocket("/ws/jarvis-live")
async def jarvis_live_endpoint(websocket: WebSocket):
    """Real-time bi-directional voice WebSocket stream for Jarvis Co-Pilot."""
    await handle_jarvis_live_websocket(websocket)

@app.get("/health")
def health_check():
    best_model = select_best_reasoning_model()
    return {
        "status": "operational",
        "engine": "vayuX-Atmospheric-Physics-v2",
        "jarvis_voice_engine": "Gemini-2.5-Flash-Native-Audio-Dialog",
        "reasoning_model_selected": best_model.get("model_id", "gemini-3.7-flash")
    }

@app.get("/api/v1/models/best-reasoning-model")
def get_best_reasoning_model():
    """Returns the dynamically selected highest-intelligence Gemini model scored via /gemini-model-selection."""
    return select_best_reasoning_model()

@app.post("/api/v1/physics/pblh-feedback")
async def get_pblh_feedback(base_pblh: float = 850.0, pm25: float = 220.0, wind_speed: float = 2.4):
    live_weather = await fetch_live_weather()
    b_pblh = base_pblh if base_pblh != 850.0 else live_weather["base_pblh"]
    w_speed = wind_speed if wind_speed != 2.4 else live_weather["wind_speed"]
    return calculate_effective_pblh(b_pblh, pm25, w_speed)

@app.post("/api/v1/physics/plume-dispersion")
async def get_plume_dispersion(wind_speed: float = 3.5, wind_deg: float = 315.0):
    live_weather = await fetch_live_weather()
    live_fires = await fetch_live_fires()
    w_speed = wind_speed if wind_speed != 3.5 else live_weather["wind_speed"]
    w_deg = wind_deg if wind_deg != 315.0 else live_weather["wind_deg"]
    features = compute_plume_dispersion(live_fires, w_speed, w_deg)
    return {"type": "FeatureCollection", "features": features}

@app.post("/api/v1/policy/generate-advisory")
async def generate_advisory(data: dict):
    baseline_aqi = data.get("baseline_aqi", 340)
    simulated_aqi = data.get("simulated_aqi", 250)
    reduction = data.get("percentage_improvement", 26.5)
    
    current_date = datetime.datetime.now().strftime("%d %B %Y, %H:%M HRS")
    
    prompt = f"""You are the Chief Atmospheric Scientist and Policy Advisor to the Government of NCT Delhi and Commission for Air Quality Management (CAQM).
Synthesize an authoritative, actionable, and mathematically grounded Executive Policy Brief based on these active VayuX simulation results:
- Current Live Baseline AQI: {baseline_aqi}
- Simulated Intervention Target AQI: {simulated_aqi}
- Predicted Particulate Reduction: {reduction}% Improvement
- Date/Time: {current_date}

Format the response cleanly in professional Markdown with these sections:
# URGENT EXECUTIVE POLICY ADVISORY: AIR QUALITY MITIGATION
**TO:** Office of the Chief Minister & Chief Secretary, Government of NCT Delhi  
**DATE:** {current_date}  
**AUTHOR:** VayuX Autonomous Atmospheric Intelligence Engine

### 1. Executive Meteorological Situation Assessment
Explain boundary layer compression (PBLH < 350m nocturnal inversion lid), upwind stubble transport, and urban stagnation.

### 2. Evaluated Policy Intervention Results
Summarize baseline ({baseline_aqi}) vs simulated outcome ({simulated_aqi}) with {reduction}% particulate density relief.

### 3. Immediate Statutory Action Plan (CAQM & DPCC Directives)
List 3-4 specific, high-leverage statutory directives under GRAP Stage-IV / Stage-III.
"""
    delegated_report = await delegate_background_task(prompt)
    
    if delegated_report and not delegated_report.startswith("["):
        return {"status": "success", "advisory_markdown": delegated_report, "model": select_best_reasoning_model().get("model_id")}

    # Robust local fallback if offline
    fallback_report = f"""# URGENT EXECUTIVE POLICY ADVISORY
**TO:** Office of the Chief Secretary & Delhi Pollution Control Committee (DPCC)  
**DATE:** {current_date}  
**SUBJECT:** Real-Time Air Quality Intervention & Simulation Impact Assessment  

---

### 1. Current Situation & Meteorological Briefing
* **Live Baseline AQI:** {baseline_aqi} (Severe / Hazardous Category)
* **Planetary Boundary Layer Height (PBLH):** Compressed (< 350m nocturnal inversion lid active).
* **Primary Drivers:** Stubble transport from upwind agricultural belts combined with urban vehicular stagnation.

### 2. Evaluated Policy Intervention Results
Based on the active simulation parameters executed in the **VayuX Policy Sandbox**:
* **Optimized Target AQI:** {simulated_aqi}
* **Net Particulate Reduction:** **{reduction}% Improvement** in ground-level $PM_{2.5}$ density.
 "Do not use LaTeX or mathematical formatting. Write PM2.5 as plain text."

### 3. Statutory Actionable Recommendations (CAQM Compliance)
1. **Enforcement:** Immediately deploy mechanical sweepers and water anti-smog guns along the Anand Vihar and Wazirpur transit corridors.
2. **Industrial Curtailment:** Enforce Stage-III restrictions on non-compliant diesel generator sets across industrial clusters in Noida and Gurugram.
3. **Public Advisory:** Issue an orange-level health alert via the **VayuVani Voice Network**, advising vulnerable populations to restrict outdoor exposure.

*Report automatically generated and verified by the VayuX Two-Way Coupled Atmospheric Engine.*
"""
    return {"status": "success", "advisory_markdown": fallback_report, "model": "template-fallback"}

    # UptimeRobot Ping Route
@app.head("/")
@app.get("/")
async def root_ping():
    return {"status": "ok", "message": "VayuX Engine is live."}

class PolicySimulationRequest(BaseModel):
    baseline_aqi: int = Field(default=340)
    baseline_pm25: Optional[float] = Field(default=None)
    vehicular: Optional[float] = Field(default=None)
    vehicular_scale: Optional[float] = Field(default=None)
    vehicular_multiplier: Optional[float] = Field(default=None)
    stubble: Optional[float] = Field(default=None)
    stubble_scale: Optional[float] = Field(default=None)
    stubble_multiplier: Optional[float] = Field(default=None)
    industrial: Optional[float] = Field(default=None)
    industrial_scale: Optional[float] = Field(default=None)
    dust: Optional[float] = Field(default=None)
    dust_scale: Optional[float] = Field(default=None)

@app.post("/api/v1/policy/simulate")
@app.post("/simulate")
def run_policy_simulation(
    payload: PolicySimulationRequest = Body(default=None),
    baseline_aqi: Optional[int] = None,
    baseline_pm25: Optional[float] = None,
    vehicular: Optional[float] = None,
    vehicular_scale: Optional[float] = None,
    stubble: Optional[float] = None,
    stubble_scale: Optional[float] = None,
    industrial: Optional[float] = None,
    industrial_scale: Optional[float] = None,
    dust: Optional[float] = None,
    dust_scale: Optional[float] = None,
):
    # Resolve values with fallbacks
    r_aqi = 340
    r_pm25 = None
    r_vehicular = 1.0
    r_stubble = 1.0
    r_industrial = 1.0
    r_dust = 1.0

    # 1. Read from payload if it exists
    if payload is not None:
        r_aqi = payload.baseline_aqi
        r_pm25 = payload.baseline_pm25

        # Vehicular
        for v in [payload.vehicular_scale, payload.vehicular_multiplier, payload.vehicular]:
            if v is not None:
                r_vehicular = v
                break

        # Stubble
        for s in [payload.stubble_scale, payload.stubble_multiplier, payload.stubble]:
            if s is not None:
                r_stubble = s
                break

        # Industrial
        for i in [payload.industrial_scale, payload.industrial]:
            if i is not None:
                r_industrial = i
                break

        # Dust
        for d in [payload.dust_scale, payload.dust]:
            if d is not None:
                r_dust = d
                break

    # 2. Query parameters override payload
    if baseline_aqi is not None:
        r_aqi = baseline_aqi
    if baseline_pm25 is not None:
        r_pm25 = baseline_pm25

    if vehicular_scale is not None:
        r_vehicular = vehicular_scale
    elif vehicular is not None:
        r_vehicular = vehicular

    if stubble_scale is not None:
        r_stubble = stubble_scale
    elif stubble is not None:
        r_stubble = stubble

    if industrial_scale is not None:
        r_industrial = industrial_scale
    elif industrial is not None:
        r_industrial = industrial

    if dust_scale is not None:
        r_dust = dust_scale
    elif dust is not None:
        r_dust = dust

    # 3. Final default for baseline_pm25 if it's still None
    if r_pm25 is None:
        r_pm25 = r_aqi * 0.7647 if r_aqi != 340 else 260.0

    return simulate_policy_impact(
        baseline_aqi=r_aqi,
        baseline_pm25=r_pm25,
        vehicular_scale=r_vehicular,
        stubble_scale=r_stubble,
        industrial_scale=r_industrial,
        dust_scale=r_dust
    )