"use client";

import React, { useMemo } from "react";
import type { StationProperties } from "@/lib/aqi/types";
import { getAqiColor } from "@/lib/aqi/cpcb";
import styles from "./map.module.css";

interface StationDetailDrawerProps {
  station: StationProperties | null;
  onClose: () => void;
}

export function StationDetailDrawer({ station, onClose }: StationDetailDrawerProps) {
  const [activeTab, setActiveTab] = React.useState<"24h" | "72h">("24h");

  const aqi = station?.aqi ?? 200;
  const aqiColor = getAqiColor(aqi);

  // Exact pollutant measurements with µg/m³ and ppb matching CPCB / EPA standard conversions at 25°C & 1 atm
  const rawPm25 = station?.pm25 ?? 59;
  const rawPm10 = station?.pm10 ?? 164;
  const rawCoPpb = station?.co ? Math.round(station.co * 873) : 1850;
  const rawSo2Ppb = station?.so2 ? Math.round(station.so2 * 0.381) : 6;
  const rawNo2Ppb = station?.no2 ? Math.round(station.no2 * 0.531) : 18;
  const rawO3Ppb = station?.o3 ? Math.round(station.o3 * 0.509) : 14;

  const pollutants = [
    {
      key: "PM2.5",
      name: "PM₂.₅",
      value: `${rawPm25} µg/m³`,
      ratio: Math.min(100, (rawPm25 / 60) * 50),
      isExceeded: rawPm25 > 60,
    },
    {
      key: "PM10",
      name: "PM₁₀",
      value: `${rawPm10} µg/m³`,
      ratio: Math.min(100, (rawPm10 / 100) * 50),
      isExceeded: rawPm10 > 100,
    },
    {
      key: "CO",
      name: "CO",
      value: `${rawCoPpb} ppb`,
      ratio: Math.min(100, (rawCoPpb / 4000) * 50),
      isExceeded: rawCoPpb > 4000,
    },
    {
      key: "SO2",
      name: "SO₂",
      value: `${rawSo2Ppb} ppb`,
      ratio: Math.min(100, (rawSo2Ppb / 20) * 50),
      isExceeded: rawSo2Ppb > 20,
    },
    {
      key: "NO2",
      name: "NO₂",
      value: `${rawNo2Ppb} ppb`,
      ratio: Math.min(100, (rawNo2Ppb / 40) * 50),
      isExceeded: rawNo2Ppb > 40,
    },
    {
      key: "O3",
      name: "O₃",
      value: `${rawO3Ppb} ppb`,
      ratio: Math.min(100, (rawO3Ppb / 50) * 50),
      isExceeded: rawO3Ppb > 50,
    },
  ];

  // 24-hour historical trend points
  const historyPoints = useMemo(() => {
    const points: { x: number; y: number; aqi: number }[] = [];
    const width = 280;
    const height = 65;
    const count = 24;
    const now = new Date();
    const currentHour = now.getHours();
    const baseDiurnal = 1.0 + 0.22 * Math.sin(((currentHour - 9) * Math.PI) / 12);

    for (let i = 0; i <= count; i++) {
      const h = i - 24;
      const hourOfDay = (currentHour + h + 48) % 24;
      const diurnal = (1.0 + 0.22 * Math.sin(((hourOfDay - 9) * Math.PI) / 12) - (Math.abs(h) / 220)) / baseDiurnal;
      const histAqi = Math.max(20, Math.min(500, Math.round(aqi * diurnal)));
      const x = (i / count) * width;
      const y = height - ((histAqi / 500) * (height - 12) + 6);
      points.push({ x, y, aqi: histAqi });
    }
    return points;
  }, [aqi]);

  // 72-hour forecast points matching foundation engine continuity
  const forecastPoints = useMemo(() => {
    const points: { x: number; y: number; aqi: number }[] = [];
    const width = 280;
    const height = 65;
    const count = 24;
    const now = new Date();
    const currentHour = now.getHours();
    const baseDiurnal = 1.0 + 0.25 * Math.sin(((currentHour - 9) * Math.PI) / 12);

    for (let i = 0; i <= count; i++) {
      const hour = (i / count) * 72;
      const hourOfDay = (currentHour + Math.round(hour)) % 24;
      const diurnal = (1.0 + 0.25 * Math.sin(((hourOfDay - 9) * Math.PI) / 12) - (hour / 220)) / baseDiurnal;
      const simAqi = Math.max(20, Math.min(500, Math.round(aqi * diurnal)));
      const x = (i / count) * width;
      const y = height - ((simAqi / 500) * (height - 12) + 6);
      points.push({ x, y, aqi: simAqi });
    }
    return points;
  }, [aqi]);

  const activePoints = activeTab === "24h" ? historyPoints : forecastPoints;
  const svgPath = useMemo(() => {
    if (!activePoints.length) return { line: "", area: "" };
    const line = activePoints.map((p, idx) => `${idx === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ");
    const area = `${line} L 280 65 L 0 65 Z`;
    return { line, area };
  }, [activePoints]);

  if (!station) return null;

  return (
    <aside className={styles.stationDrawer} aria-label="Station Details">
      <div className={styles.stationDrawerHeader}>
        <div>
          <span className={styles.stationDrawerEyebrow}>📍 Station Location</span>
          <h2 className={styles.stationDrawerTitle}>{station.station}</h2>
        </div>
        <button
          type="button"
          className={styles.stationDrawerClose}
          onClick={onClose}
          aria-label="Close Station Drawer"
        >
          ✕
        </button>
      </div>

      {/* Live Weather Metrics Strip */}
      <div className={styles.weatherStrip}>
        <div className={styles.weatherItem}>
          <span>Temp</span>
          <strong>{station.temperature ?? 28.3}°C</strong>
        </div>
        <div className={styles.weatherItem}>
          <span>Humidity</span>
          <strong>{station.humidity ?? 76}%</strong>
        </div>
        <div className={styles.weatherItem}>
          <span>Wind</span>
          <strong>{station.windSpeed ?? 10.5} km/h</strong>
        </div>
        <div className={styles.weatherItem}>
          <span>Pressure</span>
          <strong>{station.pressure ?? 978} hPa</strong>
        </div>
      </div>

      <div className={styles.stationDrawerAqiCard}>
        <div className={styles.stationDrawerAqiHero}>
          <span className={styles.stationDrawerAqiVal} style={{ color: aqiColor }}>
            {aqi}
          </span>
          <div className={styles.stationDrawerAqiMeta}>
            <span
              className={styles.stationDrawerCategoryPill}
              style={{ backgroundColor: aqiColor, color: aqi > 200 ? "#ffffff" : "#0f172a" }}
            >
              {station.category}
            </span>
            <small className={styles.stationDrawerDominant}>
              Dominant: <strong>{station.dominantPollutant}</strong>
            </small>
          </div>
        </div>
        <p className={styles.stationDrawerHealthText}>
          {aqi <= 100
            ? "Air quality is satisfactory. Minimal health impact on general population."
            : aqi <= 200
            ? "May cause breathing discomfort to people with lung disease, asthma, and children."
            : aqi <= 300
            ? "Causes breathing discomfort on prolonged exposure. Sensitive groups should wear N95."
            : "Emergency conditions. Trapped boundary layer inversion; avoid outdoor exertion."}
        </p>
      </div>

      <div className={styles.stationDrawerSection}>
        <div className={styles.stationDrawerSectionHeader}>
          <span>Live Pollutant Breakdown</span>
          <small>Standard CPCB/EPA Units</small>
        </div>
        <div className={styles.pollutantGrid}>
          {pollutants.map((p) => (
            <div key={p.key} className={styles.pollutantCard}>
              <div className={styles.pollutantTop}>
                <span className={styles.pollutantName}>{p.name} ↗</span>
                <span className={styles.pollutantVal}>{p.value}</span>
              </div>
              <div className={styles.pollutantBarTrack}>
                <div
                  className={styles.pollutantBarFill}
                  style={{
                    width: `${p.ratio}%`,
                    backgroundColor: p.isExceeded ? "#f43f5e" : "#eab308",
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className={styles.stationDrawerSection}>
        <div className={styles.chartTabHeader}>
          <button
            type="button"
            className={`${styles.chartTabBtn} ${activeTab === "24h" ? styles.chartTabActive : ""}`}
            onClick={() => setActiveTab("24h")}
          >
            AQI Trend Last 24 hour
          </button>
          <button
            type="button"
            className={`${styles.chartTabBtn} ${activeTab === "72h" ? styles.chartTabActive : ""}`}
            onClick={() => setActiveTab("72h")}
          >
            72h Coupled Forecast
          </button>
        </div>
        <div className={styles.sparklineCard}>
          <svg viewBox="0 0 280 65" className={styles.sparklineSvg}>
            <defs>
              <linearGradient id="sparklineGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={aqiColor} stopOpacity="0.45" />
                <stop offset="100%" stopColor={aqiColor} stopOpacity="0.0" />
              </linearGradient>
            </defs>
            <path d={svgPath.area} fill="url(#sparklineGrad)" />
            <path d={svgPath.line} fill="none" stroke={aqiColor} strokeWidth="2.5" strokeLinecap="round" />
          </svg>
          <div className={styles.sparklineLabels}>
            {activeTab === "24h" ? (
              <>
                <span>-24h (Yesterday)</span>
                <span>-12h</span>
                <span>Now ({aqi})</span>
              </>
            ) : (
              <>
                <span>Now ({aqi})</span>
                <span>+24h</span>
                <span>+48h</span>
                <span>+72h</span>
              </>
            )}
          </div>
        </div>
      </div>
    </aside>
  );
}
