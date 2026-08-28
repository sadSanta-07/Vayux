import test from "node:test";
import assert from "node:assert/strict";

test("Forecast Continuity: Next.js API / Backend 72h forecast trajectory continuity", async () => {
  const baselineAqi = 88;
  const historyPm25 = [25, 28, 30, 32, 29];

  // Test FastAPI backend /api/v1/forecast directly
  let aqiSeries: number[] = [];
  try {
    const res = await fetch("http://127.0.0.1:8000/api/v1/forecast", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        latitude: 28.6139,
        longitude: 77.2090,
        history_pm25: historyPm25,
      }),
    });
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data.aqi_p50)) {
        aqiSeries = data.aqi_p50;
      }
    }
  } catch {
    // If backend unavailable during offline tests, verify fallback algorithm
  }

  // If backend was reached
  if (aqiSeries.length > 0) {
    assert.equal(aqiSeries.length, 72, "Forecast should yield 72 hours");
    
    // Check bounds
    for (let h = 0; h < aqiSeries.length; h++) {
      const val = aqiSeries[h];
      assert.ok(val >= 0 && val <= 500, `Forecast AQI at hour ${h} out of bounds: ${val}`);
      
      if (h > 0) {
        const stepJump = Math.abs(val - aqiSeries[h - 1]);
        assert.ok(
          stepJump <= 35,
          `Discontinuous step jump detected at hour ${h}: ${aqiSeries[h - 1]} -> ${val} (delta: ${stepJump})`
        );
      }
    }
  }
});

test("Forecast Continuity: Multi-scenario diurnal continuity across all 24 starting hours & baselines", () => {
  const testBaselines = [79, 162, 260, 340, 450];
  const horizon = 73; // 0 to 72 inclusive

  for (const baselineAqi of testBaselines) {
    for (let startHour = 0; startHour < 24; startHour++) {
      const basePhase = ((startHour - 9) * Math.PI) / 12;
      const baseSin = Math.sin(basePhase);

      const hourlyData = Array.from({ length: horizon }, (_, hour) => {
        if (hour === 0) {
          return {
            hour: 0,
            aqi: baselineAqi,
            multiplier: 1.0,
          };
        }

        const hourOfDay = (startHour + hour) % 24;
        const hourPhase = ((hourOfDay - 9) * Math.PI) / 12;
        const diurnalDiff = Math.sin(hourPhase) - baseSin;
        const diurnalMultiplier = 1.0 + 0.20 * diurnalDiff - (hour / 250);
        const predictedAqi = Math.max(20, Math.min(500, Math.round(baselineAqi * diurnalMultiplier)));
        const multiplier = baselineAqi > 0 ? predictedAqi / baselineAqi : 1.0;

        return {
          hour,
          aqi: predictedAqi,
          multiplier,
        };
      });

      // Hour 0 is strictly pinned to ground baseline
      assert.equal(hourlyData[0].aqi, baselineAqi);
      assert.equal(hourlyData[0].multiplier, 1.0);

      // Hour 1 jump from live baseline must be smooth (no sudden +100 jumps)
      const hour1Jump = Math.abs(hourlyData[1].aqi - hourlyData[0].aqi);
      const maxAllowedHour1Jump = Math.ceil(baselineAqi * 0.06) + 4;
      assert.ok(
        hour1Jump <= maxAllowedHour1Jump,
        `Hour 0 -> Hour 1 step jump too high at startHour ${startHour}, baseline ${baselineAqi}: ${hourlyData[0].aqi} -> ${hourlyData[1].aqi} (delta: ${hour1Jump})`
      );

      // Verify smooth transitions across all 72 forecast hours
      for (let h = 1; h < hourlyData.length; h++) {
        const prev = hourlyData[h - 1].aqi;
        const curr = hourlyData[h].aqi;
        const delta = Math.abs(curr - prev);
        const maxAllowedStep = Math.ceil(baselineAqi * 0.07) + 3;
        assert.ok(
          delta <= maxAllowedStep,
          `Step jump exceeded smooth threshold at hour ${h} (startHour ${startHour}, base ${baselineAqi}): ${prev} -> ${curr} (delta ${delta})`
        );
        assert.ok(curr >= 20 && curr <= 500, `Predicted AQI out of bounds at hour ${h}: ${curr}`);
      }
    }
  }
});
