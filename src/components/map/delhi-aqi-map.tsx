/* eslint-disable @typescript-eslint/no-unused-vars */
"use client";

import { type CSSProperties, useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import { type CanvasSource, type GeoJSONSource, type MapLayerMouseEvent } from "maplibre-gl";
import gsap from "gsap";
import type { AqiApiResponse, StationProperties, SurfaceFeatureCollection } from "@/lib/aqi/types";
import { CPCB_AQI_SCALE, getAqiColor } from "@/lib/aqi/cpcb";
import { NCR_INTERPOLATION_BBOX } from "@/lib/aqi/config";
import { AqiLegend } from "./aqi-legend";
import { MapStatus } from "./map-status";
import { PolicySandbox } from "./policy-sandbox";
import styles from "./map.module.css";
import { ForecastTimeline } from "./forecast-timeline";
import { StationDetailDrawer } from "./station-detail-drawer";

const EMPTY_GEOJSON = { type: "FeatureCollection" as const, features: [] };
const REFRESH_MS = 12 * 60 * 1000;
const SURFACE_SOURCE = "aqi-surface";
const STATIONS_SOURCE = "aqi-stations";
const SURFACE_LAYER = "aqi-surface-bands";
const STATIONS_LAYER = "aqi-stations-circle";
const STATIONS_HIT_LAYER = "aqi-stations-hit";
const NCR_BOUNDS: maplibregl.LngLatBoundsLike = [[75.8, 27], [78.4, 30]];
const INITIAL_VIEW_BOUNDS: maplibregl.LngLatBoundsLike = [[76.72, 28.12], [77.66, 28.92]];
// Desktop opens at a fixed Delhi NCR framing; tweak the zoom to open the default in/out.
const DESKTOP_INITIAL_CENTER: [number, number] = [77.2, 28.55];
const DESKTOP_INITIAL_ZOOM = 11;
const COMPACT_LAYOUT_QUERY = "(max-width: 820px), (max-height: 560px)";
const SURFACE_CANVAS_WIDTH = 512;
const SURFACE_CANVAS_HEIGHT = 688;
const [SURFACE_WEST, SURFACE_SOUTH, SURFACE_EAST, SURFACE_NORTH] = NCR_INTERPOLATION_BBOX;
const SURFACE_COORDINATES: [[number, number], [number, number], [number, number], [number, number]] = [
  [SURFACE_WEST, SURFACE_NORTH],
  [SURFACE_EAST, SURFACE_NORTH],
  [SURFACE_EAST, SURFACE_SOUTH],
  [SURFACE_WEST, SURFACE_SOUTH],
];

const CIRCLE_COLOR_STOPS = CPCB_AQI_SCALE.flatMap((item) => [item.min, item.color]);

type ActivePanel = "overview" | "policy" | null;

export function DelhiAqiMap() {
  const containerRef = useRef<HTMLDivElement>(null);
  const surfaceCanvasRef = useRef<HTMLCanvasElement>(null);
  const pageRef = useRef<HTMLElement>(null);
  const headerRef = useRef<HTMLElement>(null);
  const dockRef = useRef<HTMLDivElement>(null);
  const overviewPanelRef = useRef<HTMLElement>(null);
  const policyPanelRef = useRef<HTMLElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const activePanelRef = useRef<ActivePanel>(null);
  const syncMapLayoutRef = useRef<() => void>(() => { });
  const mapPaddingRef = useRef<maplibregl.PaddingOptions | null>(null);
  const dataRef = useRef<AqiApiResponse | null>(null);
  const [aqiData, setAqiData] = useState<AqiApiResponse | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [updatedAt, setUpdatedAt] = useState<string>();
  const [selectedStation, setSelectedStation] = useState<StationProperties | null>(null);
  const [stationQuery, setStationQuery] = useState("");
  const [activePanel, setActivePanel] = useState<ActivePanel>(null);
  const [forecastAqi, setForecastAqi] = useState<number | null>(null);

  const refreshSurface = useCallback((surfaceData: SurfaceFeatureCollection | null) => {
    const canvas = surfaceCanvasRef.current;
    const map = mapRef.current;
    if (!canvas) return;

    drawAqiSurface(canvas, surfaceData);
    if (!map) return;

    const surface = map.getSource(SURFACE_SOURCE) as CanvasSource | undefined;
    surface?.play();
    map.triggerRepaint();
    if (surface) window.requestAnimationFrame(() => surface.pause());
  }, []);

  const paintAqiData = useCallback((payload: AqiApiResponse | null) => {
    refreshSurface(payload?.surface ?? null);

    const map = mapRef.current;
    if (!map) return;

    const stations = map.getSource(STATIONS_SOURCE) as GeoJSONSource | undefined;
    stations?.setData(payload?.stations ?? EMPTY_GEOJSON);
    if (stations) map.triggerRepaint();
  }, [refreshSurface]);

  const loadAqi = useCallback(async () => {
    try {
      const response = await fetch("/api/aqi", { headers: { Accept: "application/json" } });
      if (!response.ok) {
        const body = await response.json().catch(() => null) as { error?: string } | null;
        throw new Error(body?.error ?? `AQI endpoint returned ${response.status}`);
      }
      const payload = (await response.json()) as AqiApiResponse;
      dataRef.current = payload;
      setAqiData(payload);
      paintAqiData(payload);
      setUpdatedAt(payload.updatedAt);
      setState("ready");
    } catch (error) {
      console.warn("Unable to fetch Delhi NCR AQI map data", error);
      dataRef.current = null;
      setAqiData(null);
      paintAqiData(null);
      setState("error");
    }
  }, [paintAqiData]);

  useEffect(() => {
    activePanelRef.current = activePanel;
    syncMapLayoutRef.current();
  }, [activePanel]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setActivePanel(null);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    maplibregl.setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: "https://tiles.openfreemap.org/styles/dark",
      center: [77.1, 28.5],
      zoom: 7.4,
      pitch: 0,
      bearing: 0,
      minZoom: 7,
      maxZoom: 14,
      maxBounds: NCR_BOUNDS,
      renderWorldCopies: false,
      attributionControl: false,
    });
    mapRef.current = map;

    let layoutFrame = 0;
    let hasFitInitialBounds = false;
    const compactMedia = window.matchMedia(COMPACT_LAYOUT_QUERY);
    const syncMapLayout = () => {
      window.cancelAnimationFrame(layoutFrame);
      layoutFrame = window.requestAnimationFrame(() => {
        const compact = compactMedia.matches;
        const headerHeight = headerRef.current?.offsetHeight ?? 0;
        const dockHeight = dockRef.current?.offsetHeight ?? 0;
        const activeElement = activePanelRef.current === "overview"
          ? overviewPanelRef.current
          : activePanelRef.current === "policy"
            ? policyPanelRef.current
            : null;
        const activeSize = compact ? activeElement?.offsetHeight ?? 0 : activeElement?.offsetWidth ?? 0;
        const padding: maplibregl.PaddingOptions = compact
          ? {
            top: headerHeight + 24,
            right: 76,
            bottom: dockHeight + activeSize + (activeElement ? 36 : 24),
            left: 12,
          }
          : {
            top: headerHeight + 32,
            right: (activeElement ? activeSize + 116 : 96),
            bottom: dockHeight + 32,
            left: 24,
          };

        map.resize();
        map.setMinZoom(compact ? 7 : 8);
        // Remember the panel-aware padding for camera moves (station fly-to) without
        // applying it live — calling setPadding here would pan the map when a panel opens.
        mapPaddingRef.current = padding;
        if (!hasFitInitialBounds && map.loaded()) {
          if (compact) {
            map.fitBounds(INITIAL_VIEW_BOUNDS, { padding, maxZoom: 9.2, duration: 0 });
          } else {
            // jumpTo (not fitBounds + setZoom) so the fixed zoom is authoritative and not
            // overridden by an in-flight ease.
            map.jumpTo({ center: DESKTOP_INITIAL_CENTER, zoom: DESKTOP_INITIAL_ZOOM, padding });
          }
          hasFitInitialBounds = true;
        }
      });
    };
    syncMapLayoutRef.current = syncMapLayout;

    const resizeObserver = new ResizeObserver(syncMapLayout);
    [pageRef.current, headerRef.current, dockRef.current, overviewPanelRef.current, policyPanelRef.current]
      .forEach((element) => { if (element) resizeObserver.observe(element); });
    compactMedia.addEventListener("change", syncMapLayout);
    window.visualViewport?.addEventListener("resize", syncMapLayout);

    map.on("error", (event) => {
      console.warn("MapLibre basemap error", event.error);
    });
    const setupMapLayers = () => {
      const style = map.getStyle();
      if (style?.layers) {
        style.layers.forEach((layer) => {
          if (layer.type === "line") {
            map.setPaintProperty(layer.id, "line-color", "rgba(255, 255, 255, 0.15)");
          }
          else if (layer.type === "fill" || layer.type === "fill-extrusion") {
            const propertyName = layer.type === "fill" ? "fill-color" : "fill-extrusion-color";
            map.setPaintProperty(layer.id, propertyName, "rgba(255, 255, 255, 0.15)");
          }
          else if (layer.type === "symbol") {
            map.setPaintProperty(layer.id, "text-color", "#ffffff");
            map.setPaintProperty(layer.id, "text-halo-color", "rgba(0, 0, 0, 0.4)");
            map.setPaintProperty(layer.id, "text-halo-width", 1);
          }
        });
      }

      if (map.getSource(SURFACE_SOURCE)) {
        if (dataRef.current) paintAqiData(dataRef.current);
        return;
      }

      const initialData = dataRef.current;
      const surfaceCanvas = surfaceCanvasRef.current;
      if (!surfaceCanvas) return;

      drawAqiSurface(surfaceCanvas, initialData?.surface ?? null);
      map.addSource(SURFACE_SOURCE, {
        type: "canvas",
        canvas: surfaceCanvas,
        coordinates: SURFACE_COORDINATES,
        animate: false,
      });
      map.addSource(STATIONS_SOURCE, { type: "geojson", data: initialData?.stations ?? EMPTY_GEOJSON });

      const firstLabelLayer = map.getStyle()?.layers?.find((layer: { type: string; id: string }) => layer.type === "symbol")?.id;

      map.addLayer({
        id: SURFACE_LAYER,
        type: "raster",
        source: SURFACE_SOURCE,
        paint: {
          "raster-opacity": ["interpolate", ["linear"], ["zoom"], 7, 0.92, 11, 0.88, 14, 0.84],
          "raster-resampling": "linear",
          "raster-fade-duration": 0,
        },
      }, firstLabelLayer);

      map.addLayer({
        id: STATIONS_LAYER,
        type: "circle",
        source: STATIONS_SOURCE,
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 8, 4.5, 10, 6, 13, 8.5, 16, 12],
          "circle-color": ["interpolate", ["linear"], ["get", "aqi"], ...CIRCLE_COLOR_STOPS],
          "circle-stroke-width": 1.6,
          "circle-stroke-color": "rgba(255,255,255,0.9)",
          "circle-opacity": 0.95,
        },
      });

      map.addLayer({
        id: STATIONS_HIT_LAYER,
        type: "circle",
        source: STATIONS_SOURCE,
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 8, 12, 10, 16, 14, 24],
          "circle-color": "rgba(0,0,0,0.01)",
          "circle-opacity": 0.01,
        },
      });

      map.on("mouseenter", STATIONS_HIT_LAYER, () => { map.getCanvas().style.cursor = "pointer"; });
      map.on("mouseleave", STATIONS_HIT_LAYER, () => { map.getCanvas().style.cursor = ""; });
      map.on("click", STATIONS_HIT_LAYER, (event: MapLayerMouseEvent) => {
        const feature = event.features?.[0];
        if (!feature || feature.geometry.type !== "Point") return;
        const props = feature.properties as StationProperties;
        
        setStationQuery(props.station);
        setSelectedStation(props);

        const coordinates = feature.geometry.coordinates as [number, number];
        map.flyTo({ center: coordinates, zoom: 12.5, duration: 750, essential: true });
      });

      paintAqiData(dataRef.current);
      syncMapLayout();
    };
    map.on("style.load", setupMapLayers);
    map.once("load", setupMapLayers);
    if (map.isStyleLoaded()) setupMapLayers();

    return () => {
      resizeObserver.disconnect();
      compactMedia.removeEventListener("change", syncMapLayout);
      window.visualViewport?.removeEventListener("resize", syncMapLayout);
      window.cancelAnimationFrame(layoutFrame);
      syncMapLayoutRef.current = () => { };
      map.remove();
      mapRef.current = null;
    };
  }, [paintAqiData]);


  useEffect(() => {
    const fetchInitialData = async () => {
      await loadAqi();
    };

    void fetchInitialData();
    const interval = window.setInterval(() => {
      void loadAqi();
    }, REFRESH_MS);

    return () => window.clearInterval(interval);
  }, [loadAqi]);

  const handleForecastChange = useCallback(
    (_hour: number, multiplier: number, nextAqi: number) => {
      setForecastAqi(nextAqi);
      if (!dataRef.current || !mapRef.current) return;
      const baseData = dataRef.current;

      const modulatedSurface = {
        ...baseData.surface,
        features: (baseData.surface?.features ?? []).map((f) => ({
          ...f,
          properties: {
            ...f.properties,
            aqi: Math.min(Math.round((f.properties?.aqi ?? 200) * multiplier), 500),
            pm25: Number(((f.properties?.pm25 ?? 30) * multiplier).toFixed(1)),
            pm10: Number(((f.properties?.pm10 ?? 80) * multiplier).toFixed(1)),
          },
        })),
      };

      refreshSurface(modulatedSurface);
    },
    [refreshSurface]
  );

  const metrics = useMemo(() => deriveMetrics(aqiData), [aqiData]);
  const stationOptions = useMemo(
    () => aqiData?.stations.features
      .map((feature) => feature.properties.station)
      .sort((a, b) => a.localeCompare(b)) ?? [],
    [aqiData],
  );
  const matchingStationCount = useMemo(() => {
    const needle = stationQuery.trim().toLowerCase();
    if (!needle) return stationOptions.length;
    return stationOptions.filter((station) => station.toLowerCase().includes(needle)).length;
  }, [stationOptions, stationQuery]);

  const filteredStations = useMemo(() => {
    const needle = stationQuery.trim().toLowerCase();
    if (!needle) return aqiData?.stations.features ?? [];
    return (aqiData?.stations.features ?? []).filter((f) =>
      f.properties.station.toLowerCase().includes(needle)
    );
  }, [aqiData, stationQuery]);

const handleStationSearch = useCallback(() => {
    const needle = stationQuery.trim().toLowerCase();
    const match = aqiData?.stations.features.find((feature) =>
      feature.properties.station.toLowerCase().includes(needle)
    );
    const map = mapRef.current;
    if (!match || !map) return;

    const coordinates = match.geometry.coordinates as [number, number];
    map.flyTo({ center: coordinates, zoom: 12.5, duration: 750, essential: true });
    
    setSelectedStation(match.properties);
  }, [aqiData, stationQuery]);

  return (
    <main ref={pageRef} className={styles.mapPage}>
      <div ref={containerRef} className={styles.map} aria-label="Interactive Delhi NCR air quality map" />
      <canvas
        ref={surfaceCanvasRef}
        className={styles.surfaceCanvas}
        width={SURFACE_CANVAS_WIDTH}
        height={SURFACE_CANVAS_HEIGHT}
        aria-hidden="true"
      />
      <div className={styles.mapReadability} aria-hidden="true" />

      <header ref={headerRef} className={styles.topBar}>
        <MapStatus state={state} updatedAt={updatedAt} metrics={metrics} />
        <form className={styles.searchShell} onSubmit={(event) => { event.preventDefault(); handleStationSearch(); }}>
          <span className={styles.searchIcon} aria-hidden="true">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round">
              <circle cx="11" cy="11" r="7" />
              <line x1="20" y1="20" x2="16.5" y2="16.5" />
            </svg>
          </span>
          <input
            type="search"
            placeholder="Search CPCB station..."
            aria-label="Search CPCB station"
            list="station-options"
            value={stationQuery}
            onChange={(event) => setStationQuery(event.target.value)}
          />
          <datalist id="station-options">
            {stationOptions.map((station) => <option key={station} value={station} />)}
          </datalist>
          <button type="submit" aria-label="Go to station">Go</button>
        </form>
      </header>

      <nav className={styles.actionRail} aria-label="Map tools">
        <button
          type="button"
          className={activePanel === "overview" ? styles.actionActive : ""}
          aria-controls="aqi-overview-panel"
          aria-expanded={activePanel === "overview"}
          onClick={() => setActivePanel((current) => current === "overview" ? null : "overview")}
        >
          <span aria-hidden="true">◉</span>
          <small>AQI</small>
        </button>
        <button
          type="button"
          className={activePanel === "policy" ? styles.actionActive : ""}
          aria-controls="policy-panel"
          aria-expanded={activePanel === "policy"}
          onClick={() => setActivePanel((current) => current === "policy" ? null : "policy")}
        >
          <span aria-hidden="true">∫</span>
          <small>Policy</small>
        </button>
      </nav>

      <button
        type="button"
        className={`${styles.panelScrim} ${activePanel ? styles.scrimOpen : ""}`}
        aria-label="Close open map panel"
        tabIndex={activePanel ? 0 : -1}
        onClick={() => setActivePanel(null)}
      />

      <section
        ref={overviewPanelRef}
        id="aqi-overview-panel"
        className={`${styles.detailPanel} ${styles.overviewPanel} ${activePanel === "overview" ? styles.panelOpen : ""}`}
        aria-label="Delhi NCR air quality overview"
        aria-hidden={activePanel !== "overview"}
        inert={activePanel !== "overview"}
      >
        <div className={styles.sheetHandle} aria-hidden="true" />
        <div className={styles.detailHeader}>
          <div className={styles.detailTitle}>
            <span className={styles.detailHeaderIcon} aria-hidden="true">◉</span>
            <div>
              <span className={styles.eyebrow}>Live Air Quality</span>
              <h2>Delhi NCR</h2>
            </div>
          </div>
          <button type="button" className={styles.closeButton} onClick={() => setActivePanel(null)} aria-label="Close AQI overview">×</button>
        </div>

        <div className={styles.regionCard}>
          <div>
            <span className={styles.eyebrow}>Target Sector</span>
            <h1>Delhi NCR</h1>
          </div>
          <span className={styles.livePill}>Live</span>
          <p>
            {metrics.stationCount
              ? `${matchingStationCount} of ${metrics.stationCount} CPCB stations available`
              : "Waiting for CPCB station feed"}
          </p>
        </div>

        <div className={styles.primaryMetric} style={{ "--metric-accent": metrics.color } as CSSProperties}>
          <div className={styles.metricTopline}>
            <span>Regional AQI</span>
            <span>{metrics.category}</span>
          </div>
          <div className={styles.metricValue}>
            <strong>{metrics.regionalAqi ?? "--"}</strong>
            <span>India AQI</span>
          </div>
          <div className={styles.metricBar} aria-hidden="true">
            <span style={{ width: `${metrics.regionalAqi ? Math.min((metrics.regionalAqi / 500) * 100, 100) : 0}%` }} />
          </div>
        </div>

        <div className={styles.metricGrid}>
          <div className={styles.compactMetric}>
            <span>Peak Station</span>
            <strong>{metrics.peakAqi ?? "--"}</strong>
            <small>{metrics.peakStation}</small>
          </div>
          <div className={styles.compactMetric}>
            <span>Driver</span>
            <strong>{metrics.dominantPollutant}</strong>
            <small>{metrics.dominantShare}</small>
          </div>
        </div>

        <div className={styles.physicsCard}>
          <div className={styles.physicsHeader}>
            <span>Atmospheric Inversion & Coupling</span>
            <span className={styles.inversionPill}>Inversion Active</span>
          </div>
          <div className={styles.physicsGrid}>
            <div>
              <span>Boundary Layer (PBLH)</span>
              <strong>353m (Trapped)</strong>
            </div>
            <div>
              <span>Solar Extinction</span>
              <strong>-66.7% Flux</strong>
            </div>
            <div>
              <span>Upwind NASA Fires</span>
              <strong>3 Hotspots</strong>
            </div>
            <div>
              <span>Wind Advection</span>
              <strong>2.4 m/s NW</strong>
            </div>
          </div>
        </div>
      </section>

      <section
        ref={policyPanelRef}
        id="policy-panel"
        className={`${styles.detailPanel} ${styles.policyPanel} ${activePanel === "policy" ? styles.panelOpen : ""}`}
        aria-label="Policy mitigation tools"
        aria-hidden={activePanel !== "policy"}
        inert={activePanel !== "policy"}
      >
        <div className={styles.sheetHandle} aria-hidden="true" />
        <button type="button" className={styles.closeButton} onClick={() => setActivePanel(null)} aria-label="Close policy tools">×</button>
        <PolicySandbox baselineAqi={metrics.regionalAqi ?? 340} />
      </section>
      <StationDetailDrawer station={selectedStation} onClose={() => setSelectedStation(null)} />

      <div ref={dockRef} className={styles.bottomDock}>
        <ForecastTimeline
          onHourChange={handleForecastChange}
          baselineAqi={metrics.regionalAqi ?? 260}
        />
        <AqiLegend activeAqi={forecastAqi ?? metrics.regionalAqi ?? 0} />
        <div className={styles.mapAttribution}>
          <a href="https://openfreemap.org" target="_blank" rel="noreferrer">OpenFreeMap</a>
          <span>·</span>
          <a href="https://www.openmaptiles.org/" target="_blank" rel="noreferrer">© OpenMapTiles</a>
          <span>· Data from </span>
          <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a>
        </div>
      </div>
    </main>
  );
}

interface DashboardMetrics {
  regionalAqi: number | null;
  peakAqi: number | null;
  peakStation: string;
  category: string;
  color: string;
  stationCount: number;
  dominantPollutant: string;
  dominantShare: string;
}

interface SurfaceColorStop {
  aqi: number;
  rgb: readonly [number, number, number];
}

const SURFACE_COLOR_STOPS: readonly SurfaceColorStop[] = [
  { aqi: 0, rgb: hexToRgb(CPCB_AQI_SCALE[0].color) },
  ...CPCB_AQI_SCALE.map((item) => ({
    aqi: (item.min + item.max) / 2,
    rgb: hexToRgb(item.color),
  })),
  { aqi: 500, rgb: hexToRgb(CPCB_AQI_SCALE[CPCB_AQI_SCALE.length - 1].color) },
];

function drawAqiSurface(canvas: HTMLCanvasElement, surface: SurfaceFeatureCollection | null) {
  const context = canvas.getContext("2d", { alpha: true });
  if (!context) return;

  const features = surface?.features ?? [];
  if (!features.length) {
    context.clearRect(0, 0, canvas.width, canvas.height);
    return;
  }

  const longitudes = Array.from(new Set(features.map((feature) => feature.geometry.coordinates[0])))
    .sort((a, b) => a - b);
  const latitudes = Array.from(new Set(features.map((feature) => feature.geometry.coordinates[1])))
    .sort((a, b) => a - b);
  if (longitudes.length < 2 || latitudes.length < 2) {
    context.clearRect(0, 0, canvas.width, canvas.height);
    return;
  }

  const longitudeIndex = new Map(longitudes.map((value, index) => [value, index]));
  const latitudeIndex = new Map(latitudes.map((value, index) => [value, index]));
  const samples = new Float32Array(longitudes.length * latitudes.length);
  samples.fill(Number.NaN);
  features.forEach((feature) => {
    const [longitude, latitude] = feature.geometry.coordinates;
    const x = longitudeIndex.get(longitude);
    const y = latitudeIndex.get(latitude);
    if (x !== undefined && y !== undefined) samples[y * longitudes.length + x] = feature.properties.aqi;
  });

  const image = context.createImageData(canvas.width, canvas.height);
  const maxSampleX = longitudes.length - 1;
  const maxSampleY = latitudes.length - 1;
  for (let pixelY = 0; pixelY < canvas.height; pixelY += 1) {
    const sampleY = (1 - pixelY / (canvas.height - 1)) * maxSampleY;
    const y0 = Math.floor(sampleY);
    const y1 = Math.min(y0 + 1, maxSampleY);
    const yWeight = sampleY - y0;

    for (let pixelX = 0; pixelX < canvas.width; pixelX += 1) {
      const sampleX = (pixelX / (canvas.width - 1)) * maxSampleX;
      const x0 = Math.floor(sampleX);
      const x1 = Math.min(x0 + 1, maxSampleX);
      const xWeight = sampleX - x0;
      const aqi = bilinearSample(samples, longitudes.length, x0, x1, y0, y1, xWeight, yWeight);
      const [red, green, blue] = interpolateSurfaceColor(aqi);
      const offset = (pixelY * canvas.width + pixelX) * 4;
      image.data[offset] = red;
      image.data[offset + 1] = green;
      image.data[offset + 2] = blue;
      image.data[offset + 3] = 255;
    }
  }
  context.putImageData(image, 0, 0);
}

function bilinearSample(
  samples: Float32Array,
  rowWidth: number,
  x0: number,
  x1: number,
  y0: number,
  y1: number,
  xWeight: number,
  yWeight: number,
): number {
  const topLeft = samples[y0 * rowWidth + x0];
  const topRight = samples[y0 * rowWidth + x1];
  const bottomLeft = samples[y1 * rowWidth + x0];
  const bottomRight = samples[y1 * rowWidth + x1];
  const topLeftWeight = (1 - xWeight) * (1 - yWeight);
  const topRightWeight = xWeight * (1 - yWeight);
  const bottomLeftWeight = (1 - xWeight) * yWeight;
  const bottomRightWeight = xWeight * yWeight;
  let weightedValue = 0;
  let totalWeight = 0;

  if (Number.isFinite(topLeft)) {
    weightedValue += topLeft * topLeftWeight;
    totalWeight += topLeftWeight;
  }
  if (Number.isFinite(topRight)) {
    weightedValue += topRight * topRightWeight;
    totalWeight += topRightWeight;
  }
  if (Number.isFinite(bottomLeft)) {
    weightedValue += bottomLeft * bottomLeftWeight;
    totalWeight += bottomLeftWeight;
  }
  if (Number.isFinite(bottomRight)) {
    weightedValue += bottomRight * bottomRightWeight;
    totalWeight += bottomRightWeight;
  }
  return totalWeight ? weightedValue / totalWeight : 0;
}

function interpolateSurfaceColor(aqi: number): readonly [number, number, number] {
  const value = Math.max(0, Math.min(500, aqi));
  const upperIndex = SURFACE_COLOR_STOPS.findIndex((stop) => value <= stop.aqi);
  if (upperIndex <= 0) return SURFACE_COLOR_STOPS[0].rgb;
  const lower = SURFACE_COLOR_STOPS[upperIndex - 1];
  const upper = SURFACE_COLOR_STOPS[upperIndex];
  const progress = (value - lower.aqi) / Math.max(upper.aqi - lower.aqi, 1);
  const eased = progress * progress * (3 - 2 * progress);
  return lower.rgb.map((channel, index) => Math.round(
    channel + (upper.rgb[index] - channel) * eased,
  )) as unknown as readonly [number, number, number];
}

function hexToRgb(color: string): readonly [number, number, number] {
  const value = Number.parseInt(color.slice(1), 16);
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
}

function deriveMetrics(payload: AqiApiResponse | null): DashboardMetrics {
  const stations = payload?.stations.features ?? [];
  if (!stations.length) {
    return {
      regionalAqi: null,
      peakAqi: null,
      peakStation: "No live station",
      category: "Standby",
      color: "#a855f7",
      stationCount: 0,
      dominantPollutant: "AQI",
      dominantShare: "Feed offline",
    };
  }

  const readings = stations.map((feature) => feature.properties);
  const total = readings.reduce((sum, item) => sum + item.aqi, 0);
  const regionalAqi = Math.round(total / readings.length);
  const peak = readings.reduce((highest, item) => item.aqi > highest.aqi ? item : highest, readings[0]);
  const pollutantCounts = readings.reduce<Record<string, number>>((counts, item) => {
    counts[item.dominantPollutant] = (counts[item.dominantPollutant] ?? 0) + 1;
    return counts;
  }, {});
  const [dominantPollutant, count] = Object.entries(pollutantCounts)
    .sort((a, b) => b[1] - a[1])[0] ?? ["AQI", 0];

  return {
    regionalAqi,
    peakAqi: peak.aqi,
    peakStation: peak.station,
    category: peak.category,
    color: getAqiColor(regionalAqi),
    stationCount: readings.length,
    dominantPollutant,
    dominantShare: `${Math.round((count / readings.length) * 100)}% stations`,
  };
}

// function openStationPopup(
//   map: maplibregl.Map,
//   coordinates: [number, number],
//   props: StationProperties,
//   prefersReducedMotion: boolean,
// ) {
//   const accent = getAqiColor(props.aqi);
//   const updated = props.updatedAt ? formatUpdate(props.updatedAt) : "Time unavailable";
//   const html = `
//     <p class="aqi-popup-kicker">${escapeHtml(props.dominantPollutant)} dominant</p>
//     <p class="aqi-popup-title">${escapeHtml(props.station)}</p>
//     <div class="aqi-popup-value">
//       <strong>AQI ${props.aqi}</strong>
//       <span>${escapeHtml(props.category)}</span>
//     </div>
//     <p class="aqi-popup-detail">${escapeHtml(updated)} · CPCB station feed</p>
//   `;
//   const popup = new maplibregl.Popup({ offset: 16, closeButton: true, maxWidth: "260px" })
//     .setLngLat(coordinates)
//     .setHTML(html)
//     .addTo(map);
//   const popupElement = popup.getElement();
//   popupElement.style.setProperty("--aqi-accent", accent);
//   if (prefersReducedMotion) return;

//   const content = popupElement.querySelector<HTMLElement>(".maplibregl-popup-content");
//   const timeline = gsap.timeline();
//   timeline
//     .fromTo(popupElement, { autoAlpha: 0, y: 9, scale: 0.93 }, {
//       autoAlpha: 1,
//       y: 0,
//       scale: 1,
//       duration: 0.3,
//       ease: "back.out(1.3)",
//     })
//     .fromTo(
//       content?.querySelectorAll(".aqi-popup-kicker, .aqi-popup-title, .aqi-popup-value, .aqi-popup-detail") ?? [],
//       { autoAlpha: 0, y: 5 },
//       { autoAlpha: 1, y: 0, duration: 0.24, stagger: 0.035, ease: "power2.out" },
//       "-=0.17",
//     );

//   const closeButton = popupElement.querySelector<HTMLButtonElement>(".maplibregl-popup-close-button");
//   closeButton?.addEventListener("click", (closeEvent) => {
//     closeEvent.preventDefault();
//     closeEvent.stopImmediatePropagation();
//     gsap.to(popupElement, {
//       autoAlpha: 0,
//       y: 5,
//       scale: 0.96,
//       duration: 0.18,
//       ease: "power2.in",
//       onComplete: () => popup.remove(),
//     });
//   }, { capture: true, once: true });
// }

function formatUpdate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.valueOf())
    ? value
    : new Intl.DateTimeFormat("en-IN", { hour: "numeric", minute: "2-digit" }).format(date);
}

function escapeHtml(value: unknown): string {
  return String(value).replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  }[character] ?? character));
}
