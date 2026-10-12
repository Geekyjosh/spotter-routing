import { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import {
  get48HourForecast,
  type HourlyWeatherForecast,
  type RouteResponse,
} from "../../lib/api";
import type * as GeoJSON from "geojson";
type Props = {
  data: RouteResponse | null;
};

type ForecastPoint = {
  coordinates: number[];
  forecasts: HourlyWeatherForecast[];
};

const ROUTE_COLORS = ["#0891b2", "#2563eb", "#64748b"];
const RECOMMENDED_COLOR = "#087F8C";

const HEAT_SOURCE = "weather-risk-heat-source";
const HEAT_LAYER = "weather-risk-heat-layer";

function riskColor(level: string) {
  switch (level) {
    case "no_travel":
      return "#7f1d1d";
    case "severe":
      return "#991b1b";
    case "high":
      return "#dc2626";
    case "moderate":
      return "#d97706";
    case "low":
      return "#16a34a";
    default:
      return "#64748b";
  }
}

function getForecastRisk(forecast: HourlyWeatherForecast, loadWeight: number) {
  const wind = Math.max(
    forecast.wind_speed_mph ?? 0,
    forecast.wind_gusts_mph ?? 0,
  );

  const rain = forecast.rain_inches_per_hour ?? 0;
  const snow = forecast.snow_inches_per_hour ?? 0;

  if (
    wind >= 55 ||
    (wind >= 45 && loadWeight > 30000) ||
    rain > 1 ||
    snow > 3
  ) {
    return "no_travel";
  }

  if (
    wind >= 45 ||
    (wind >= 35 && loadWeight > 40000) ||
    rain >= 0.5 ||
    snow >= 2
  ) {
    return "severe";
  }

  if (wind >= 35 || rain >= 0.25 || snow >= 1) {
    return "high";
  }

  if (wind >= 25 || rain >= 0.1 || snow >= 0.5) {
    return "moderate";
  }

  return "low";
}

function riskIntensity(level: string) {
  switch (level) {
    case "no_travel":
      return 1;
    case "severe":
      return 0.85;
    case "high":
      return 0.65;
    case "moderate":
      return 0.4;
    default:
      return 0.15;
  }
}

function nearestForecast(
  forecasts: HourlyWeatherForecast[],
  targetTime: number,
) {
  if (!forecasts.length) return null;

  return forecasts.reduce((nearest, current) => {
    const nearestDifference = Math.abs(
      new Date(nearest.forecast_time).getTime() - targetTime,
    );

    const currentDifference = Math.abs(
      new Date(current.forecast_time).getTime() - targetTime,
    );

    return currentDifference < nearestDifference ? current : nearest;
  });
}

export default function RouteMap({ data }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

  const routeMarkersRef = useRef<maplibregl.Marker[]>([]);
  const routeLayersRef = useRef<string[]>([]);
  const routeSourcesRef = useRef<string[]>([]);

  const [forecastHour, setForecastHour] = useState(0);
  const [showHeatmap, setShowHeatmap] = useState(true);
  const [forecastPoints, setForecastPoints] = useState<ForecastPoint[]>([]);
  const [forecastLoading, setForecastLoading] = useState(false);
  const [forecastError, setForecastError] = useState("");
  const [mapReady, setMapReady] = useState(false);
  const [forecastBaseTime, setForecastBaseTime] = useState<number | null>(null);

  const recommendedRoute =
    data?.routes.find(
      (route) => route.id === data.recommendation?.recommended_route_id,
    ) ?? data?.routes[0];

  // Initialize the map once.
  useEffect(() => {
    if (!containerRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          "osm-tiles": {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution:
              '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
          },
        },
        layers: [
          {
            id: "osm-background",
            type: "raster",
            source: "osm-tiles",
          },
        ],
      },
      center: [-74.5, 40.4],
      zoom: 8,
    });

    map.addControl(new maplibregl.NavigationControl(), "top-right");

    mapRef.current = map;

    const handleLoad = () => setMapReady(true);

    map.on("load", handleLoad);

    return () => {
      map.off("load", handleLoad);
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Draw routes and checkpoint markers.
  useEffect(() => {
    const map = mapRef.current;

    if (!map || !mapReady) return;

    routeMarkersRef.current.forEach((marker) => marker.remove());
    routeMarkersRef.current = [];

    routeLayersRef.current.forEach((id) => {
      if (map.getLayer(id)) map.removeLayer(id);
    });

    routeSourcesRef.current.forEach((id) => {
      if (map.getSource(id)) map.removeSource(id);
    });

    routeLayersRef.current = [];
    routeSourcesRef.current = [];

    if (!data) return;

    const bounds = new maplibregl.LngLatBounds();

    data.routes.forEach((route, index) => {
      const sourceId = `route-source-${index}`;
      const layerId = `route-layer-${index}`;

      const isRecommended =
        route.id === data.recommendation?.recommended_route_id;

      map.addSource(sourceId, {
        type: "geojson",
        data: {
          type: "Feature",
          properties: {},
          geometry: route.geometry,
        },
      });

      map.addLayer({
        id: layerId,
        type: "line",
        source: sourceId,
        layout: {
          "line-join": "round",
          "line-cap": "round",
        },
        paint: {
          "line-color": isRecommended
            ? RECOMMENDED_COLOR
            : ROUTE_COLORS[index % ROUTE_COLORS.length],
          "line-width": isRecommended ? 8 : 4,
          "line-opacity": isRecommended ? 1 : 0.55,
        },
      });

      routeLayersRef.current.push(layerId);
      routeSourcesRef.current.push(sourceId);

      route.geometry.coordinates.forEach((point) => {
        bounds.extend([point[0], point[1]]);
      });

      route.checkpoints.forEach((checkpoint) => {
        const severity =
          checkpoint.risk?.severity ?? checkpoint.risk?.level ?? "unknown";

        const color = riskColor(severity);
        const weather = checkpoint.weather;

        const popup = new maplibregl.Popup({
          offset: 12,
        });

        const container = document.createElement("div");

        const heading = document.createElement("strong");
        heading.textContent = `${route.name} — Checkpoint ${checkpoint.index + 1}`;

        container.appendChild(heading);

        const details = [
          `Distance: ${checkpoint.distance_miles} miles`,
          `Arrival: ${new Date(checkpoint.estimated_arrival).toLocaleString()}`,
          `Risk: ${severity.replaceAll("_", " ")}`,
          `Risk score: ${checkpoint.risk?.score ?? "N/A"}`,
          weather
            ? `Wind: ${weather.wind_speed_mph ?? "N/A"} mph`
            : "Weather unavailable",
          weather ? `Gusts: ${weather.wind_gusts_mph ?? "N/A"} mph` : "",
        ];

        details.filter(Boolean).forEach((detail) => {
          const paragraph = document.createElement("p");
          paragraph.textContent = detail;
          paragraph.style.margin = "4px 0";
          container.appendChild(paragraph);
        });

        popup.setDOMContent(container);

        const marker = new maplibregl.Marker({
          color,
          scale: 0.65,
        })
          .setLngLat([checkpoint.coordinates[0], checkpoint.coordinates[1]])
          .setPopup(popup)
          .addTo(map);

        routeMarkersRef.current.push(marker);
      });
    });

    const recommendedIndex = data.routes.findIndex(
      (route) => route.id === data.recommendation?.recommended_route_id,
    );

    if (recommendedIndex >= 0) {
      const layerId = `route-layer-${recommendedIndex}`;

      if (map.getLayer(layerId)) {
        map.moveLayer(layerId);
      }
    }

    [
      {
        point: data.origin,
        color: "#16a34a",
        label: "Origin",
      },
      {
        point: data.destination,
        color: "#dc2626",
        label: "Destination",
      },
    ].forEach(({ point, color, label }) => {
      const marker = new maplibregl.Marker({ color })
        .setLngLat([point.coordinates[0], point.coordinates[1]])
        .setPopup(new maplibregl.Popup().setText(`${label}: ${point.label}`))
        .addTo(map);

      routeMarkersRef.current.push(marker);
    });

    if (!bounds.isEmpty()) {
      map.fitBounds(bounds, {
        padding: 60,
        maxZoom: 12,
      });
    }
  }, [data, mapReady]);

  // Load forecasts along the recommended route.
  useEffect(() => {
    let cancelled = false;

    setForecastPoints([]);
    setForecastError("");
    setForecastHour(0);
    setForecastBaseTime(null);

    if (!recommendedRoute) {
      setForecastLoading(false);
      return;
    }

    const checkpoints = recommendedRoute.checkpoints;

    async function loadForecasts() {
      setForecastLoading(true);

      const results = await Promise.allSettled(
        checkpoints.map(async (checkpoint) => {
          const [longitude, latitude] = checkpoint.coordinates;

          const response = await get48HourForecast(latitude, longitude);

          return {
            coordinates: checkpoint.coordinates,
            forecasts: response.forecasts,
          };
        }),
      );

      if (cancelled) return;

      const available = results
        .filter(
          (result): result is PromiseFulfilledResult<ForecastPoint> =>
            result.status === "fulfilled",
        )
        .map((result) => result.value)
        .filter((point) => point.forecasts.length > 0);

      setForecastPoints(available);

      if (available.length) {
        // Anchor the timeline to the current hour.
        // Forecasts remain sampled at provider intervals.
        const now = Date.now();
        const currentHour = Math.floor(now / 3600000) * 3600000;

        setForecastBaseTime(currentHour);
      } else {
        setForecastError(
          "Forecast overlay unavailable. Route planning remains available.",
        );
      }

      setForecastLoading(false);
    }

    void loadForecasts();

    return () => {
      cancelled = true;
    };
  }, [recommendedRoute]);

  // Render a real MapLibre heatmap using GeoJSON points.
  useEffect(() => {
    const map = mapRef.current;

    if (!map || !mapReady) return;

    const targetTime =
      forecastBaseTime === null
        ? null
        : forecastBaseTime + forecastHour * 60 * 60 * 1000;

    const features: GeoJSON.Feature<
      GeoJSON.Point,
      { intensity: number; risk: string }
    >[] = [];

    if (showHeatmap && targetTime !== null && forecastPoints.length) {
      forecastPoints.forEach((point) => {
        const forecast = nearestForecast(point.forecasts, targetTime);

        if (!forecast) return;

        const forecastTime = new Date(forecast.forecast_time).getTime();

        if (Math.abs(forecastTime - targetTime) > 3 * 60 * 60 * 1000) {
          return;
        }

        const risk = getForecastRisk(forecast, data?.load_weight_lbs ?? 0);

        features.push({
          type: "Feature",
          properties: {
            intensity: riskIntensity(risk),
            risk,
          },
          geometry: {
            type: "Point",
            coordinates: [point.coordinates[0], point.coordinates[1]],
          },
        });
      });
    }

    const collection: GeoJSON.FeatureCollection<
      GeoJSON.Point,
      { intensity: number; risk: string }
    > = {
      type: "FeatureCollection",
      features,
    };

    const existingSource = map.getSource(HEAT_SOURCE) as
      | maplibregl.GeoJSONSource
      | undefined;

    if (existingSource) {
      existingSource.setData(collection);
    } else {
      map.addSource(HEAT_SOURCE, {
        type: "geojson",
        data: collection,
      });
    }

    if (!map.getLayer(HEAT_LAYER)) {
      const firstRouteLayer = routeLayersRef.current.find((id) =>
        Boolean(map.getLayer(id)),
      );

      map.addLayer(
        {
          id: HEAT_LAYER,
          type: "heatmap",
          source: HEAT_SOURCE,
          maxzoom: 16,
          paint: {
            "heatmap-weight": ["get", "intensity"],
            "heatmap-intensity": [
              "interpolate",
              ["linear"],
              ["zoom"],
              4,
              0.7,
              10,
              1.5,
            ],
            "heatmap-radius": [
              "interpolate",
              ["linear"],
              ["zoom"],
              4,
              16,
              8,
              35,
              12,
              55,
            ],
            "heatmap-opacity": 0.7,
            "heatmap-color": [
              "interpolate",
              ["linear"],
              ["heatmap-density"],
              0,
              "rgba(0,0,0,0)",
              0.1,
              "#bbf7d0",
              0.25,
              "#22c55e",
              0.4,
              "#facc15",
              0.6,
              "#f97316",
              0.8,
              "#dc2626",
              1,
              "#7f1d1d",
            ],
          },
        },
        firstRouteLayer,
      );
    }

    // Keep the heatmap behind route lines.
    const firstRouteLayer = routeLayersRef.current.find((id) =>
      Boolean(map.getLayer(id)),
    );

    if (firstRouteLayer && map.getLayer(HEAT_LAYER)) {
      map.moveLayer(HEAT_LAYER, firstRouteLayer);
    }
  }, [
    forecastPoints,
    forecastHour,
    forecastBaseTime,
    showHeatmap,
    mapReady,
    data,
  ]);

  const selectedTime =
    forecastBaseTime === null
      ? null
      : new Date(forecastBaseTime + forecastHour * 60 * 60 * 1000);

  return (
    <div className="relative h-full min-h-[420px] w-full">
      <div ref={containerRef} className="h-full min-h-[420px] w-full" />

      {data && (
        <div className="absolute bottom-4 left-4 right-4 z-10 rounded-md border border-[#DCE3E7] bg-white p-3 shadow-md sm:right-auto sm:w-[350px]">
          <div className="mb-2 flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-[#172B35]">
                Weather Forecast Timeline
              </p>
              <p className="text-xs text-[#647480]">0–48 hour forecast</p>
            </div>

            <label className="flex items-center gap-2 text-xs text-[#52616B]">
              <input
                type="checkbox"
                checked={showHeatmap}
                onChange={(event) => setShowHeatmap(event.target.checked)}
              />
              Heatmap
            </label>
          </div>

          <input
            type="range"
            min={0}
            max={48}
            step={3}
            value={forecastHour}
            disabled={forecastLoading || !forecastPoints.length}
            onChange={(event) => setForecastHour(Number(event.target.value))}
            className="w-full accent-[#087F8C]"
            aria-label="Forecast time offset"
          />

          <div className="mt-1 flex justify-between text-xs text-[#647480]">
            <span>0h</span>
            <span>12h</span>
            <span>24h</span>
            <span>36h</span>
            <span>48h</span>
          </div>

          <p className="mt-2 text-xs font-medium text-[#172B35]">
            {forecastLoading
              ? "Loading weather forecasts..."
              : selectedTime
                ? `Selected: ${selectedTime.toLocaleString()}`
                : "Forecast unavailable"}
          </p>

          {forecastPoints.length > 0 && (
            <p className="mt-1 text-xs text-[#647480]">
              Weather risk heatmap along {recommendedRoute?.name ?? "the route"}
              . Forecasts update every 3 hours.
            </p>
          )}

          {forecastError && (
            <p className="mt-2 text-xs text-amber-700">{forecastError}</p>
          )}
        </div>
      )}
    </div>
  );
}
