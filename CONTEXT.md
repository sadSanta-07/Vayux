# VayuX (वायुX): Domain Context & Architecture Specification

**Domain**: Two-Way Weather–Chemistry Coupled Forecasting & Policy Simulation Platform (Delhi NCR Focus)  
**Hackathon**: Smart India Hackathon 2026 (Ministry of Environment, Forest and Climate Change)  
**Repository**: https://github.com/sadSanta-07/Vayux  

---

## 1. Domain Terminology & Atmospheric Invariants

- **CAAQMS**: Continuous Ambient Air Quality Monitoring Stations (105+ active stations across Delhi, Noida, Gurugram, Ghaziabad, and Faridabad monitored by CPCB, DPCC, HSPCB, and UPPCB).
- **CPCB NAQI Standard**: Indian National Air Quality Index calculation utilizing piecewise linear sub-index interpolation across 8 criteria pollutants ($PM_{2.5}, PM_{10}, NO_2, SO_2, CO, O_3, NH_3, Pb$). The headline index is strictly determined by $\max(I_{p1}, I_{p2}, \dots, I_{pn})$ with authentic Indian category breakpoints ($0\text{-}50$ Good, $51\text{-}100$ Satisfactory, $101\text{-}200$ Moderate, $201\text{-}300$ Poor, $301\text{-}400$ Very Poor, $401\text{-}500$ Severe).
- **Two-Way Weather–Chemistry Coupling**:
  - *Chemistry $\to$ Meteorology (Beer-Lambert Solar Extinction)*: Downwelling solar radiation attenuation ($I(z) = I_0 e^{-\alpha \cdot \text{PM}_{2.5}}$) suppresses surface radiative heating by up to $-66.7\%$.
  - *Meteorology $\to$ Chemistry (Nocturnal Inversion & Boundary Layer Compression)*: Radiative surface cooling collapses the Planetary Boundary Layer Height ($\text{PBLH} < 305\,\text{m}$), trapping ground emissions in an airtight surface mixing volume and exponentially magnifying nocturnal particulate density.
- **Zero-Shot Foundation Forecaster**: 72-hour probabilistic quantile forecasting ($p10, p50, p90$) powered by Amazon's `amazon/chronos-bolt-tiny` zero-shot time-series foundation model integrated with a custom `PhysicsResidualAdapter`.
- **$C^0$ Continuity Anchoring**: Strict mathematical trajectory calibration anchoring the foundation model forecast curve directly to Hour 0 (`Now`) live observations, preventing step discontinuities ($|\Delta \text{AQI}| \le 15\,\text{AQI/hr}$).
- **VayuVani (वायुवाणी)**: Ambient real-time voice intelligence co-pilot streaming continuous bi-directional 16kHz audio in $\to$ 24kHz raw PCM speech out over WebSockets (`/ws/jarvis-live`) powered by Google's `gemini-2.5-flash-native-audio-latest`. Backed by full multi-turn conversational persistence, dynamic station lookups, 72h temperature trajectories, NASA VIIRS active fire hotspots, and live web search environmental intelligence.
- **GRAP Counterfactual Policy Sandbox**: Real-time mass-balance source apportionment simulator modeling vehicular Odd-Even controls, agricultural stubble fire bans, and industrial dust suppression with secondary boundary layer feedback.

---

## 2. Key Code Locations & Architectural Seams

- **Data Ingestion & Normalization**:
  - `src/lib/aqi/data-gov.ts`: Ingests live Copernicus CAMS reanalysis and Open-Meteo High-Resolution Aerosol/Weather feeds.
  - `src/lib/aqi/cpcb.ts`: Canonical Indian CPCB piecewise linear sub-index conversion and color/category mapping.
  - `src/lib/aqi/normalize.ts`: GeoJSON feature formatting for 105+ CAAQMS monitoring stations.
- **Frontend Map & Interactive Controls**:
  - `src/components/map/delhi-aqi-map.tsx`: High-performance MapLibre GL canvas with vectorized IDW spatial interpolation.
  - `src/components/map/forecast-timeline.tsx`: 72-hour forecast timeline scrubber with live playback.
  - `src/components/map/station-detail-drawer.tsx`: Station-level telemetry and historical pollutant breakdown drawer.
  - `src/components/map/policy-sandbox.tsx`: Real-time interactive GRAP policy intervention simulator.
  - `src/components/map/jarvis-voice-pill.tsx`: Glowing organic ambient voice assistant interface.
  - `src/hooks/useJarvisVoice.ts`: Web Audio API AudioWorklet PCM streaming client.
- **Backend Physics, ML & Voice Engine (FastAPI)**:
  - `backend/main.py`: Core FastAPI application with CORS, uptime ping, health, and WebSocket endpoints.
  - `backend/jarvis/live_session.py`: Bi-directional WebSocket bridge to Gemini Multimodal Live API.
  - `backend/jarvis/tools.py`: 8 specialized environmental tools (station lookups, 72h forecasts, NASA fires, GRAP policy simulations, web search).
  - `backend/ml_forecast.py`: Chronos-Bolt zero-shot forecaster with physics residual adapter.
  - `backend/physics.py`: Beer-Lambert solar extinction and Pasquill-Gifford Gaussian plume dispersion models.
  - `backend/policy.py`: Source apportionment and secondary PBLH expansion physics simulator.
  - `backend/live_data.py`: Open-Meteo weather, Copernicus CAMS air quality, and NASA FIRMS fire ingestion.
