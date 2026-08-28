import pytest
import numpy as np
import sys
import os

# Add backend directory to sys.path if not present
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from ml.foundation_loader import FoundationEngineLoader
from ml.residual_adapter import PhysicsResidualAdapter

@pytest.fixture
def loader():
    return FoundationEngineLoader(model_id="amazon/chronos-bolt-tiny", device="cpu")

@pytest.fixture
def adapter():
    return PhysicsResidualAdapter()

def test_zero_shot_inference_dimensions_and_bounds(loader):
    history = [100.0 + float(i) for i in range(168)]
    p10, p50, p90 = loader.predict_zero_shot(history, prediction_length=72)

    assert len(p10) == 72
    assert len(p50) == 72
    assert len(p90) == 72
    assert np.all(p10 <= p50 + 1e-5)
    assert np.all(p50 <= p90 + 1e-5)
    assert np.all(p10 >= 0.0)

def test_physics_residual_bounds_and_continuity(adapter):
    c_base = np.full(72, 150.0)
    h_base = np.full(72, 400.0)
    u_wind = np.full(72, 0.8)
    v_wind = np.full(72, -0.4)
    fire_hotspots = [{"latitude": 30.5, "longitude": 75.5, "frp": 300.0}]

    c_final = adapter.apply_coupling(
        c_base, h_base, u_wind, v_wind, 28.6139, 77.2090, fire_hotspots
    )

    assert len(c_final) == 72
    assert np.all(c_final >= 0.0)
    assert np.all(np.isfinite(c_final))
    assert np.mean(c_final) >= np.mean(c_base)

def test_inference_latency_sla(loader):
    history = [150.0] * 168
    # Warm-up pass
    loader.predict_zero_shot(history, prediction_length=72)
    
    t0 = pytest.importorskip("time").perf_counter()
    loader.predict_zero_shot(history, prediction_length=72)
    elapsed_ms = (pytest.importorskip("time").perf_counter() - t0) * 1000.0

    # Model inference latency SLA: sub-100ms on local CPU once warm
    assert elapsed_ms < 100.0, f"Latency SLA breached: {elapsed_ms:.2f}ms > 100ms"

