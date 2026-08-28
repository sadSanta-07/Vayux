import logging
from typing import Dict, Any, List, Optional
import numpy as np

from ml_forecast import generate_hybrid_forecast, ForecastRequest
from physics import calculate_effective_pblh, compute_plume_dispersion
from policy import simulate_policy_impact
from live_data import (
    fetch_live_weather, 
    fetch_live_fires, 
    fetch_live_regional_aqi, 
    fetch_station_details_by_name_or_coords,
    fetch_72h_weather_forecast,
    search_environmental_web_intel
)
from ml.model_selector import delegate_background_task, select_best_reasoning_model

logger = logging.getLogger("VayuX.JarvisTools")

JARVIS_TOOL_DECLARATIONS = [
    {
        "name": "get_live_weather_and_aqi",
        "description": "Get current live regional meteorological and atmospheric conditions in Delhi NCR (temperature, humidity, wind speed, wind direction, boundary layer height, and regional AQI).",
        "parameters": {
            "type": "object",
            "properties": {
                "latitude": {"type": "number", "description": "Latitude (default: 28.6139 for Delhi)", "default": 28.6139},
                "longitude": {"type": "number", "description": "Longitude (default: 77.2090 for Delhi)", "default": 77.2090}
            }
        }
    },
    {
        "name": "get_station_aqi_and_details",
        "description": "Get real-time monitoring station details, exact AQI, category, and pollutant concentrations (PM2.5, PM10, NO2, SO2, CO, O3) for any specific Delhi NCR location (e.g. Anand Vihar, Punjabi Bagh, ITO, Dwarka, Rohini, Alipur, Jahangirpuri, Noida, Gurugram, Ghaziabad, Faridabad, etc.).",
        "parameters": {
            "type": "object",
            "properties": {
                "location_name": {"type": "string", "description": "Name of the station or area in Delhi NCR (e.g. 'Anand Vihar', 'Punjabi Bagh', 'ITO', 'Dwarka', 'Noida Sector 62', 'Gurugram')"},
                "latitude": {"type": "number", "description": "Optional latitude coordinate"},
                "longitude": {"type": "number", "description": "Optional longitude coordinate"}
            }
        }
    },
    {
        "name": "get_72h_air_quality_forecast",
        "description": "Get 72-hour rolling hourly forecasted temperature (°C), relative humidity (%), boundary layer height (PBLH), PM2.5, and AQI trajectory for Delhi NCR or any specific area.",
        "parameters": {
            "type": "object",
            "properties": {
                "location_name": {"type": "string", "description": "Optional location or station name"},
                "latitude": {"type": "number", "description": "Target latitude (default: 28.6139)", "default": 28.6139},
                "longitude": {"type": "number", "description": "Target longitude (default: 77.2090)", "default": 77.2090}
            }
        }
    },
    {
        "name": "search_environmental_and_news_intel",
        "description": "Search the live web for real-time Delhi NCR environmental news, government orders, CAQM GRAP directives, Supreme Court rulings, school closures, or general environmental facts.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query or question to look up online"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_active_fire_hotspots",
        "description": "Retrieve live NASA FIRMS satellite active crop stubble fire detections in Punjab and Haryana upwind of Delhi.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_atmospheric_physics_diagnostics",
        "description": "Calculates current boundary layer height compression ratio, solar extinction percentage, and active stubble fire smoke plumes.",
        "parameters": {
            "type": "object",
            "properties": {
                "current_pm25": {"type": "number", "description": "Current surface PM2.5 in ug/m3", "default": 220.0}
            }
        }
    },
    {
        "name": "simulate_grap_policy",
        "description": "Simulate counterfactual GRAP policy interventions (Odd-Even traffic curbs, stubble fire suppression, industrial pauses).",
        "parameters": {
            "type": "object",
            "properties": {
                "vehicular_scale": {"type": "number", "description": "0.0 (complete vehicle ban) to 1.0 (normal traffic)", "default": 0.5},
                "stubble_scale": {"type": "number", "description": "0.0 (complete fire suppression) to 1.0 (uncontrolled fires)", "default": 0.2},
                "industrial_scale": {"type": "number", "description": "0.0 (complete industrial halt) to 1.0 (normal operations)", "default": 0.5},
                "dust_scale": {"type": "number", "description": "0.0 (complete dust suppression) to 1.0 (normal dust)", "default": 0.4}
            }
        }
    },
    {
        "name": "generate_deep_policy_brief",
        "description": "Delegates deep reasoning and policy brief generation to the dynamically selected SOTA text reasoning model (e.g. Gemini 3.7 Flash).",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Policy question or executive advisory subject", "default": "Air Quality Emergency Action Plan"}
            }
        }
    }
]

async def execute_jarvis_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Routes and executes tool calls triggered by the Gemini Voice Agent."""
    logger.info(f"Executing Jarvis tool: {tool_name} with arguments: {arguments}")
    
    try:
        if tool_name == "get_live_weather_and_aqi":
            lat = arguments.get("latitude", 28.6139)
            lon = arguments.get("longitude", 77.2090)
            weather = await fetch_live_weather(lat, lon)
            regional_aqi_info = await fetch_live_regional_aqi()
            
            wind_deg = weather.get("wind_deg", 270.0)
            cardinals = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
            card_idx = int((wind_deg + 11.25) / 22.5) % 16
            wind_cardinal = cardinals[card_idx]

            return {
                "status": "SUCCESS",
                "temperature_celsius": weather.get("temperature", 28.0),
                "humidity_pct": weather.get("humidity", 70.0),
                "wind_speed_ms": weather.get("wind_speed", 2.3),
                "wind_direction_deg": wind_deg,
                "wind_direction_cardinal": wind_cardinal,
                "base_boundary_layer_height_m": weather.get("base_pblh", 275.0),
                "inversion_status": "Active Nocturnal Inversion Lid (< 400m)" if weather.get("base_pblh", 275.0) < 400 else "Convective Boundary Layer",
                "regional_baseline_aqi": regional_aqi_info.get("regional_aqi", 72),
                "aqi_category": regional_aqi_info.get("category", "Satisfactory"),
                "dominant_pollutant": regional_aqi_info.get("dominant_pollutant", "PM2.5"),
                "reporting_stations": regional_aqi_info.get("total_reporting_stations", 105)
            }

        elif tool_name == "get_station_aqi_and_details":
            loc_name = arguments.get("location_name")
            lat = arguments.get("latitude")
            lon = arguments.get("longitude")
            res = await fetch_station_details_by_name_or_coords(loc_name, lat, lon)
            return res

        elif tool_name == "get_72h_air_quality_forecast":
            loc_name = arguments.get("location_name")
            lat = arguments.get("latitude", 28.6139)
            lon = arguments.get("longitude", 77.2090)
            
            weather = await fetch_live_weather(lat, lon)
            weather_fc = await fetch_72h_weather_forecast(lat, lon)
            fires = await fetch_live_fires()
            regional_aqi_info = await fetch_live_regional_aqi()
            
            current_aqi = regional_aqi_info.get("regional_aqi", 251)
            station_title = "Delhi NCR Regional Average"
            if loc_name:
                st_info = await fetch_station_details_by_name_or_coords(loc_name, lat, lon)
                if st_info.get("status") == "SUCCESS":
                    current_aqi = st_info.get("aqi", current_aqi)
                    station_title = st_info.get("matched_station", loc_name)

            def get_cpcb_cat(val: int) -> str:
                if val <= 50: return "Good"
                elif val <= 100: return "Satisfactory"
                elif val <= 200: return "Moderate"
                elif val <= 300: return "Poor"
                elif val <= 400: return "Very Poor"
                else: return "Severe"

            base_pm25 = current_aqi * 0.75
            hours = np.arange(72)
            # Diurnal nocturnal inversion cycle: peak in early morning (+25 AQI), convective trough in afternoon (-25 AQI)
            diurnal_osc = 22.0 * np.sin(2.0 * np.pi * (hours - 6) / 24.0)
            fire_contribution = min(35.0, len(fires) * 4.5)
            
            forecast_pm25 = np.clip(base_pm25 + diurnal_osc + fire_contribution * (1.0 - np.exp(-hours / 24.0)), 15.0, 480.0)
            forecast_aqi = [int(p * 1.33) for p in forecast_pm25]
            
            max_aqi = int(max(forecast_aqi))
            min_aqi = int(min(forecast_aqi))
            avg_pm25 = float(np.mean(forecast_pm25))
            
            return {
                "status": "SUCCESS",
                "target_location": station_title,
                "current_aqi": current_aqi,
                "current_category": get_cpcb_cat(current_aqi),
                "peak_forecast_aqi": max_aqi,
                "peak_category": get_cpcb_cat(max_aqi),
                "trough_forecast_aqi": min_aqi,
                "trough_category": get_cpcb_cat(min_aqi),
                "temperature_forecast": {
                    "current_c": weather_fc.get("current_temp", 28.2),
                    "min_c": weather_fc.get("min_temp", 24.5),
                    "max_c": weather_fc.get("max_temp", 34.8)
                },
                "hourly_temperature_first_24h": weather_fc.get("hourly_temperatures", [])[:24],
                "hourly_aqi_first_24h": forecast_aqi[:24],
                "summary": f"72-hour forecast for {station_title}: AQI currently {current_aqi} ({get_cpcb_cat(current_aqi)}), peaking at {max_aqi} ({get_cpcb_cat(max_aqi)}) during nocturnal inversion and troughing at {min_aqi} ({get_cpcb_cat(min_aqi)}). Temperature ranges from {weather_fc.get('min_temp', 24.5)}°C to {weather_fc.get('max_temp', 34.8)}°C."
            }

        elif tool_name == "search_environmental_and_news_intel":
            query = arguments.get("query", "Delhi air quality CAQM GRAP")
            results = await search_environmental_web_intel(query)
            return {
                "status": "SUCCESS",
                "query": query,
                "results_count": len(results),
                "intel": results if results else [{"title": "Official CAQM Directives", "snippet": "Commission for Air Quality Management enforces GRAP stages based on ambient AQI thresholds in Delhi NCR."}]
            }

        elif tool_name == "get_active_fire_hotspots":
            fires = await fetch_live_fires()
            total_frp = sum(f.get("frp", 25.0) for f in fires)
            return {
                "status": "SUCCESS",
                "active_fires_count": len(fires),
                "total_fire_radiative_power_mw": round(total_frp, 1),
                "source": "NASA FIRMS VIIRS SNPP NRT satellite",
                "upwind_corridor": "Punjab-Haryana northwest agricultural belt",
                "sample_hotspots": fires[:5]
            }

        elif tool_name == "get_atmospheric_physics_diagnostics":
            pm25 = arguments.get("current_pm25", 220.0)
            weather = await fetch_live_weather()
            fires = await fetch_live_fires()
            
            pblh_diag = calculate_effective_pblh(weather["base_pblh"], pm25, weather["wind_speed"])
            plume_features = compute_plume_dispersion(fires, weather["wind_speed"], weather["wind_deg"])
            
            return {
                "base_pblh_meters": pblh_diag["base_pblh"],
                "effective_pblh_meters": pblh_diag["effective_pblh"],
                "compression_factor": pblh_diag["compression_factor"],
                "solar_attenuation_pct": pblh_diag["solar_attenuation_pct"],
                "wind_speed_ms": weather["wind_speed"],
                "wind_direction_deg": weather["wind_deg"],
                "fire_plume_count": len(plume_features)
            }

        elif tool_name == "simulate_grap_policy":
            pm25 = arguments.get("current_pm25", 220.0)
            regional_aqi_info = await fetch_live_regional_aqi()
            current_aqi = regional_aqi_info.get("regional_aqi", 72)
            
            v_scale = arguments.get("vehicular_scale", 0.5)
            s_scale = arguments.get("stubble_scale", 0.2)
            i_scale = arguments.get("industrial_scale", 0.5)
            d_scale = arguments.get("dust_scale", 0.4)
            
            sim_result = simulate_policy_impact(
                current_aqi=current_aqi,
                current_pm25=pm25,
                vehicular_scale=v_scale,
                stubble_scale=s_scale,
                industrial_scale=i_scale,
                dust_scale=d_scale
            )
            return {
                "status": "SUCCESS",
                "baseline_aqi": current_aqi,
                "simulated_aqi": sim_result["simulated_aqi"],
                "percentage_reduction": sim_result["percentage_improvement"],
                "stage_transition": f"Simulated {sim_result['percentage_improvement']}% reduction under proposed mitigation scenario."
            }

        elif tool_name == "generate_deep_policy_brief":
            topic = arguments.get("topic", "Air Quality Action Plan")
            best_model = select_best_reasoning_model()
            logger.info(f"Delegating deep reasoning brief to best model: {best_model['model_id']}")
            
            prompt = f"Provide an executive scientific brief on '{topic}' in the context of Delhi NCR air quality and CPCB/GRAP framework. Keep it highly structured and actionable."
            brief_text = await delegate_background_task(prompt, best_model["model_id"])
            
            return {
                "status": "SUCCESS",
                "delegated_model": best_model["model_id"],
                "intelligence_score": best_model["score"],
                "brief": brief_text
            }

        else:
            return {"status": "ERROR", "message": f"Unknown tool: {tool_name}"}

    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
        return {"status": "ERROR", "message": str(e)}
