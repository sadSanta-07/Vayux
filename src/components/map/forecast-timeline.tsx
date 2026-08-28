"use client";

import { type CSSProperties, useCallback, useEffect, useMemo, useRef, useState } from "react";
import gsap from "gsap";
import { CPCB_AQI_SCALE } from "@/lib/aqi/cpcb";
import styles from "./map.module.css";

interface ForecastTimelineProps {
  onHourChange?: (hourOffset: number, simulatedMultiplier: number, aqi: number) => void;
  baselineAqi: number;
  stationName?: string;
}

export function ForecastTimeline({ onHourChange, baselineAqi, stationName }: ForecastTimelineProps) {
  const [selectedHour, setSelectedHour] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [forecastStart] = useState<Date>(() => new Date());
  const valueRef = useRef<HTMLElement>(null);
  const categoryRef = useRef<HTMLSpanElement>(null);
  const previousAqiRef = useRef<number | null>(null);

  const [forecastAqiSeries, setForecastAqiSeries] = useState<number[]>([]);

  useEffect(() => {
    async function loadForecast() {
      if (!baselineAqi || baselineAqi <= 0) return;
      try {
        const res = await fetch("/api/forecast", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            baseline_aqi: baselineAqi,
          }),
        });
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data.aqi_p50) && data.aqi_p50.length > 0) {
            setForecastAqiSeries(data.aqi_p50);
          }
        }
      } catch {
        // Handled via phase-normalized mathematical diurnal fallback
      }
    }
    loadForecast();
  }, [baselineAqi]);

  const hourlyData = useMemo(() => {
    const start = forecastStart || new Date();
    const currentHourOfDay = start.getHours();
    const basePhase = ((currentHourOfDay - 6) * Math.PI) / 12;
    const baseSin = Math.sin(basePhase);

    return Array.from({ length: 73 }, (_, hour) => {
      const forecastTime = new Date(start);
      forecastTime.setHours(forecastTime.getHours() + hour);
      const timeStr = forecastTime.toLocaleTimeString("en-IN", { hour: "numeric", hour12: true });
      const dayStr = forecastTime.toLocaleDateString("en-IN", { weekday: "short" });
      const label = hour === 0 ? "Now" : `${dayStr} · ${timeStr}`;

      if (hour === 0) return { hour, label, aqi: baselineAqi, multiplier: 1.0 };

      // forecastAqiSeries contains 72 hourly forecast steps (index 0 = hour 1)
      const modelAqi = forecastAqiSeries[hour - 1];
      let predictedAqi = baselineAqi;

      if (typeof modelAqi === "number" && Number.isFinite(modelAqi) && modelAqi > 0) {
        predictedAqi = modelAqi;
      } else {
        const hourOfDay = forecastTime.getHours();
        const hourPhase = ((hourOfDay - 6) * Math.PI) / 12;
        const diurnalDiff = Math.sin(hourPhase) - baseSin;
        const targetAqi = Math.round(baselineAqi + 22.0 * diurnalDiff);
        predictedAqi = Math.max(20, Math.min(500, targetAqi));
      }

      const multiplier = baselineAqi > 0 ? predictedAqi / baselineAqi : 1.0;

      return {
        hour,
        label,
        aqi: Math.min(Math.max(predictedAqi, 20), 500),
        multiplier,
      };
    });
  }, [baselineAqi, forecastStart, forecastAqiSeries]);

  useEffect(() => {
    if (!isPlaying) return;
    const interval = window.setInterval(() => {
      setSelectedHour((current) => {
        if (current >= 72) {
          setIsPlaying(false);
          return 72;
        }
        return current + 1;
      });
    }, 400);
    return () => window.clearInterval(interval);
  }, [isPlaying]);

  const currentItem = hourlyData[selectedHour] ?? hourlyData[0];
  const currentBand = CPCB_AQI_SCALE.find((item) => currentItem.aqi <= item.max)
    ?? CPCB_AQI_SCALE[CPCB_AQI_SCALE.length - 1];
  const previousItem = hourlyData[Math.max(0, selectedHour - 1)] ?? currentItem;
  const delta = currentItem.aqi - previousItem.aqi;
  const progress = (selectedHour / 72) * 100;

  useEffect(() => {
    onHourChange?.(selectedHour, currentItem.multiplier, currentItem.aqi);
  }, [selectedHour, currentItem, onHourChange]);

  useEffect(() => {
    const previousAqi = previousAqiRef.current;
    previousAqiRef.current = currentItem.aqi;
    if (previousAqi === null || previousAqi === currentItem.aqi) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const context = gsap.context(() => {
      gsap.timeline()
        .fromTo(valueRef.current, {
          autoAlpha: 0.35,
          y: currentItem.aqi > previousAqi ? 7 : -7,
          scale: 0.9,
        }, {
          autoAlpha: 1,
          y: 0,
          scale: 1,
          duration: 0.34,
          ease: "back.out(1.8)",
        })
        .fromTo(categoryRef.current, { autoAlpha: 0.4, x: -5 }, {
          autoAlpha: 1,
          x: 0,
          duration: 0.24,
          ease: "power2.out",
        }, "<0.04");
    });
    return () => context.revert();
  }, [currentItem.aqi]);

  const togglePlayback = useCallback(() => {
    if (isPlaying) {
      setIsPlaying(false);
      return;
    }
    if (selectedHour >= 72) setSelectedHour(0);
    setIsPlaying(true);
  }, [isPlaying, selectedHour]);

  const trendLabel = selectedHour === 0
    ? (stationName ? `Station baseline: ${stationName.split(",")[0]}` : "Regional baseline (Delhi NCR)")
    : delta === 0
      ? "Steady"
      : `${delta > 0 ? "↑" : "↓"} ${Math.abs(delta)} vs prior hour`;

  return (
    <aside
      className={styles.forecast}
      aria-label="Forecast timeline"
      data-playing={isPlaying}
      style={{
        "--forecast-accent": currentBand.color,
        "--forecast-progress": `${progress}%`,
      } as CSSProperties}
    >
      <div className={styles.forecastTop}>
        <div className={styles.forecastIdentity}>
          <span className={styles.forecastPulse} aria-hidden="true" />
          <div>
            <span className={styles.forecastEyebrow}>
              {stationName ? `72h Outlook · ${stationName.split(",")[0]}` : "72h Regional Outlook (Delhi NCR)"}
            </span>
            <strong>{selectedHour === 0 ? "Live conditions" : currentItem.label}</strong>
          </div>
        </div>

        <div className={styles.forecastReading} aria-live="polite">
          <div>
            <span ref={categoryRef} className={styles.forecastCategory}>{currentBand.label}</span>
            <small>{trendLabel}</small>
          </div>
          <strong ref={valueRef}>{currentItem.aqi}</strong>
        </div>
      </div>

      <div className={styles.forecastControls}>
        <button
          type="button"
          onClick={togglePlayback}
          aria-label={isPlaying ? "Pause forecast" : selectedHour >= 72 ? "Replay 72-hour forecast" : "Play 72-hour forecast"}
          title={isPlaying ? "Pause forecast" : selectedHour >= 72 ? "Replay forecast" : "Play forecast"}
          aria-pressed={isPlaying}
        >
          <span className={isPlaying ? styles.pauseIcon : styles.playIcon} aria-hidden="true" />
        </button>
        <div className={styles.forecastOffset}>
          <strong>{selectedHour === 0 ? "Now" : `+${selectedHour} hours`}</strong>
          <span>Drag to explore</span>
        </div>
      </div>

      <div className={styles.forecastScrubber}>
        <span className={styles.forecastProgress} aria-hidden="true" />
        <input
          type="range"
          aria-label="Forecast hour offset"
          aria-valuetext={selectedHour === 0 ? "Now" : `${selectedHour} hours from now`}
          min={0}
          max={72}
          step={1}
          value={selectedHour}
          onChange={(event) => setSelectedHour(Number.parseInt(event.target.value, 10))}
        />
      </div>

      <div className={styles.forecastTicks} aria-hidden="true">
        <span>Now</span>
        <span>24h</span>
        <span>48h</span>
        <span>72h</span>
      </div>
    </aside>
  );
}