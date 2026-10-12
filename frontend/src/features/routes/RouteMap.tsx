import { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import {
  get48HourForecast,
  type HourlyWeatherForecast,
  type RouteResponse,
} from "../../lib/api";

type Props = {
  data: RouteResponse | null;
};

type ForecastPoint = {
  coordinates: number[];
  forecasts: HourlyWeatherForecast[];
};

const ROUTE_COLORS = ["#0891b2", "#2563eb", "#64748b"];
const RECOMMENDED_COLOR = "#087F8C";

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

  // OpenWeatherMap forecast precipitation is a
  // three-hour accumulation, not an hourly rate.
  const rain = (forecast.rain_inches ?? 0) / 3;

  // Approximate snowfall depth rate from the
  // provider's reported 3-hour snow quantity.
  const snow = (forecast.snowfall_cm ?? 0) / 2.54 / 3;

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
  const heatMarkersRef = useRef<maplibregl.Marker[]>([]);
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

  // Create the map once.
  useEffect(() => {
    if (!containerRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: "https://tiles.openfreemap.org/styles/liberty",
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

  // Draw the three routes and checkpoint markers.
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
        const color = riskColor(checkpoint.risk?.level ?? "unknown");

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
          `Risk: ${checkpoint.risk?.level ?? "unknown"}`,
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

  // Fetch the next 48 hours of forecasts at
  // checkpoints along the recommended route.
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
        const earliestForecast = Math.min(
          ...available.flatMap((point) =>
            point.forecasts.map((forecast) =>
              new Date(forecast.forecast_time).getTime(),
            ),
          ),
        );

        setForecastBaseTime(earliestForecast);
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

  // Draw a colored weather-risk overlay around
  // each sampled forecast checkpoint.
  useEffect(() => {
    const map = mapRef.current;

    heatMarkersRef.current.forEach((marker) => marker.remove());
    heatMarkersRef.current = [];

    if (
      !map ||
      !mapReady ||
      !showHeatmap ||
      !forecastPoints.length ||
      forecastBaseTime === null
    ) {
      return;
    }

    const targetTime = forecastBaseTime + forecastHour * 60 * 60 * 1000;

    forecastPoints.forEach((point) => {
      const forecast = nearestForecast(point.forecasts, targetTime);

      if (!forecast) return;

      const forecastTime = new Date(forecast.forecast_time).getTime();

      // Do not show stale forecasts as if they
      // represented the selected hour.
      if (Math.abs(forecastTime - targetTime) > 3 * 60 * 60 * 1000) {
        return;
      }

      const risk = getForecastRisk(forecast, data?.load_weight_lbs ?? 0);

      const color = riskColor(risk);

      const element = document.createElement("div");

      element.style.width = "105px";
      element.style.height = "105px";
      element.style.borderRadius = "50%";
      element.style.backgroundColor = color;
      element.style.opacity = "0.23";
      element.style.border = `2px solid ${color}`;
      element.style.pointerEvents = "none";

      const marker = new maplibregl.Marker({
        element,
        anchor: "center",
      })
        .setLngLat([point.coordinates[0], point.coordinates[1]])
        .addTo(map);

      heatMarkersRef.current.push(marker);
    });

    return () => {
      heatMarkersRef.current.forEach((marker) => marker.remove());
      heatMarkersRef.current = [];
    };
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
              Overlay
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
              Showing sampled weather risk along{" "}
              {recommendedRoute?.name ?? "the route"}. Forecasts update every 3
              hours.
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
