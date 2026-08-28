import time
import logging
import numpy as np
import requests
from typing import List, Dict, Any, Tuple, Optional

try:
    import pyparsing
    if not hasattr(pyparsing, "DelimitedList"):
        pyparsing.DelimitedList = getattr(pyparsing, "delimitedList", getattr(pyparsing, "delimited_list", None))
except Exception:
    pass

logger = logging.getLogger("VayuX.FoundationLoader")

class FoundationEngineLoader:
    """
    Dual-Mode Time-Series Foundation Engine Loader.
    Mode 1: Zero-shot inference via Amazon Chronos-Bolt (PyTorch/ONNX).
    Mode 2: Operational fallback client targeting Open-Meteo CAMS Atmospheric Reanalysis.
    """
    def __init__(self, model_id: str = "amazon/chronos-bolt-tiny", device: str = "cpu", use_onnx: bool = True):
        self.model_id = model_id
        self.device = device
        self.use_onnx = use_onnx
        self.pipeline = None
        self.mode = "CHRONOS_BOLT"
        self._initialize_engine()

    def _initialize_engine(self) -> None:
        try:
            logger.info(f"Loading zero-shot foundation model: {self.model_id} on {self.device}")
            from chronos import BaseChronosPipeline
            import torch
            
            dtype = torch.bfloat16 if self.device == "cuda" else torch.float32
            self.pipeline = BaseChronosPipeline.from_pretrained(
                self.model_id,
                device_map=self.device,
                torch_dtype=dtype
            )
            self.mode = "CHRONOS_BOLT"
            logger.info("Chronos-Bolt foundation model successfully loaded.")
        except Exception as e:
            logger.warning(f"Failed to load Chronos-Bolt model ({e}). Defaulting to Mode 2 (CAMS Reanalysis Fallback).")
            self.mode = "CAMS_FALLBACK"

    def predict_zero_shot(
        self, 
        history_pm25: List[float], 
        prediction_length: int = 72, 
        num_samples: int = 20
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Generates zero-shot PM2.5 predictions for the requested forecast horizon.
        Returns a tuple containing p10, p50, and p90 quantile forecasts as 1D arrays.
        """
        start_time = time.perf_counter()
        
        if self.mode == "CHRONOS_BOLT" and self.pipeline is not None:
            try:
                import torch
                context_tensor = torch.tensor(history_pm25, dtype=torch.float32).unsqueeze(0)
                
                if hasattr(self.pipeline, "predict_quantiles"):
                    quantiles, _ = self.pipeline.predict_quantiles(
                        context_tensor,
                        prediction_length=prediction_length,
                        quantile_levels=[0.10, 0.50, 0.90]
                    )
                    q_np = quantiles[0].cpu().numpy()
                    p10 = np.maximum(0.0, q_np[:, 0])
                    p50 = np.maximum(0.0, q_np[:, 1])
                    p90 = np.maximum(0.0, q_np[:, 2])
                else:
                    try:
                        forecast = self.pipeline.predict(
                            inputs=context_tensor,
                            prediction_length=prediction_length
                        )
                    except TypeError:
                        forecast = self.pipeline.predict(
                            context=context_tensor,
                            prediction_length=prediction_length,
                            num_samples=num_samples
                        )
                    samples = forecast[0].cpu().numpy()
                    p10 = np.maximum(0.0, np.quantile(samples, 0.10, axis=0))
                    p50 = np.maximum(0.0, np.quantile(samples, 0.50, axis=0))
                    p90 = np.maximum(0.0, np.quantile(samples, 0.90, axis=0))
                
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                logger.debug(f"Chronos-Bolt zero-shot inference completed in {elapsed_ms:.2f}ms")
                return p10, p50, p90
            except Exception as e:
                logger.error(f"Chronos-Bolt inference pass failed: {e}. Executing CAMS fallback.")
                return self._fetch_cams_fallback(prediction_length)
        else:
            return self._fetch_cams_fallback(prediction_length)

    def _fetch_cams_fallback(self, prediction_length: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Retrieves real-time European CAMS atmospheric forecasts from Open-Meteo API.
        """
        logger.info("Executing CAMS Reanalysis Fallback API query.")
        try:
            url = "https://air-quality-api.open-meteo.com/v1/air-quality"
            params = {
                "latitude": 28.6139,
                "longitude": 77.2090,
                "hourly": "pm2_5",
                "forecast_days": int(np.ceil(prediction_length / 24))
            }
            response = requests.get(url, params=params, timeout=3.0)
            response.raise_for_status()
            data = response.json()
            cams_series = np.array(data["hourly"]["pm2_5"][:prediction_length], dtype=np.float64)
            
            p50 = cams_series
            p10 = cams_series * 0.85
            p90 = cams_series * 1.15
            return p10, p50, p90
        except Exception as err:
            logger.error(f"CAMS API query failed: {err}. Generating synthetic physics baseline.")
            hours = np.arange(prediction_length)
            synthetic_p50 = 180.0 + 40.0 * np.sin(2 * np.pi * hours / 24.0)
            return synthetic_p50 * 0.8, synthetic_p50, synthetic_p50 * 1.2
