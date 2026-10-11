import { useState } from "react";
import {
  CloudSun,
  MapPin,
  Wind,
  Droplets,
  Thermometer,
  Snowflake,
  AlertTriangle,
} from "lucide-react";

import type { RouteResponse } from "../../lib/api";

type Props = {
  data: RouteResponse;
};

function riskStyles(level: string) {
  if (level === "high") return "bg-red-100 text-red-700";
  if (level === "moderate") return "bg-amber-100 text-amber-700";
  if (level === "low") return "bg-green-100 text-green-700";
  return "bg-slate-100 text-slate-600";
}

function formatValue(value: number | null | undefined, unit: string) {
  return value == null ? "N/A" : `${value} ${unit}`;
}

export default function CheckpointWeather({ data }: Props) {
  const [selectedRouteId, setSelectedRouteId] = useState(
    data.recommendation?.recommended_route_id ?? data.routes[0]?.id ?? "",
  );

  const selectedRoute =
    data.routes.find((route) => route.id === selectedRouteId) ?? data.routes[0];

  if (!selectedRoute) return null;

  return (
    <section className="rounded-md border border-[#DCE3E7] bg-white">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#E3E8EC] px-5 py-4">
        <div>
          <h2 className="flex items-center gap-2 font-semibold text-[#172B35]">
            <CloudSun size={20} className="text-[#087F8C]" />
            Checkpoint Weather Analysis
          </h2>
          <p className="mt-1 text-xs text-[#647480]">
            Forecast conditions along each route at estimated arrival times.
          </p>
        </div>

        <select
          value={selectedRoute.id}
          onChange={(event) => setSelectedRouteId(event.target.value)}
          className="rounded-md border border-[#CBD5DB] bg-white px-3 py-2 text-sm text-[#172B35]"
          aria-label="Select route for weather analysis"
        >
          {data.routes.map((route) => (
            <option key={route.id} value={route.id}>
              {route.name}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-3 p-5">
        <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
          <span className="font-medium text-[#344854]">
            {selectedRoute.checkpoint_count} checkpoints
          </span>
          <span className="text-[#647480]">
            {selectedRoute.weather_checkpoints_available} forecasts available
          </span>
        </div>

        {selectedRoute.checkpoints.map((checkpoint) => {
          const weather = checkpoint.weather;
          const risk = checkpoint.risk;
          const riskLevel = risk?.level ?? "unknown";

          return (
            <div
              key={checkpoint.index}
              className="rounded-md border border-[#DCE3E7] p-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="flex items-center gap-2 text-sm font-semibold text-[#172B35]">
                    <MapPin size={16} className="text-[#087F8C]" />
                    Checkpoint {checkpoint.index + 1}
                  </h3>

                  <p className="mt-1 text-xs text-[#647480]">
                    {checkpoint.distance_miles.toFixed(1)} miles from origin
                  </p>

                  <p className="mt-1 text-xs text-[#647480]">
                    Estimated arrival:{" "}
                    {new Date(checkpoint.estimated_arrival).toLocaleString()}
                  </p>
                </div>

                <span
                  className={`rounded-md px-3 py-1 text-xs font-semibold ${riskStyles(
                    riskLevel,
                  )}`}
                >
                  {riskLevel.toUpperCase()} RISK
                  {risk?.score != null ? ` · ${risk.score}/100` : ""}
                </span>
              </div>

              {weather ? (
                <div className="mt-4 grid grid-cols-2 gap-4 border-t border-[#E3E8EC] pt-4 text-sm sm:grid-cols-4">
                  <div>
                    <p className="flex items-center gap-1 text-xs text-[#647480]">
                      <Thermometer size={14} />
                      Temperature
                    </p>
                    <p className="mt-1 font-semibold">
                      {formatValue(weather.temperature_f, "°F")}
                    </p>
                  </div>

                  <div>
                    <p className="flex items-center gap-1 text-xs text-[#647480]">
                      <Wind size={14} />
                      Wind Speed
                    </p>
                    <p className="mt-1 font-semibold">
                      {formatValue(weather.wind_speed_mph, "mph")}
                    </p>
                    <p className="mt-1 text-xs text-[#647480]">
                      Gusts: {formatValue(weather.wind_gusts_mph, "mph")}
                    </p>
                  </div>

                  <div>
                    <p className="flex items-center gap-1 text-xs text-[#647480]">
                      <Droplets size={14} />
                      Rainfall
                    </p>
                    <p className="mt-1 font-semibold">
                      {formatValue(weather.rain_inches, "in")}
                    </p>
                  </div>

                  <div>
                    <p className="flex items-center gap-1 text-xs text-[#647480]">
                      <Snowflake size={14} />
                      Snowfall
                    </p>
                    <p className="mt-1 font-semibold">
                      {formatValue(weather.snowfall_cm, "cm")}
                    </p>
                  </div>
                </div>
              ) : (
                <div className="mt-4 flex items-start gap-2 border-t border-[#E3E8EC] pt-4 text-sm text-amber-700">
                  <AlertTriangle size={17} className="shrink-0" />
                  Weather forecast unavailable for this checkpoint.
                </div>
              )}

              {risk?.factors && risk.factors.length > 0 && (
                <div className="mt-4 border-t border-[#E3E8EC] pt-3">
                  <p className="text-xs font-semibold text-[#52616B]">
                    Risk Factors
                  </p>

                  <div className="mt-2 flex flex-wrap gap-2">
                    {risk.factors.map((factor, index) => (
                      <span
                        key={`${checkpoint.index}-${index}`}
                        className="rounded-md bg-[#F1F4F6] px-2 py-1 text-xs text-[#344854]"
                      >
                        {factor}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
