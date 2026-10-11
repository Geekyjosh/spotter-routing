import { useEffect, useRef } from "react";
import * as maplibregl from "maplibre-gl";
import type { RouteResponse } from "../../lib/api";

type Props = {
  data: RouteResponse | null;
};

const ROUTE_COLORS = ["#0891b2", "#2563eb", "#64748b"];
const RECOMMENDED_ROUTE_COLOR = "#087F8C";
function riskColor(level: string) {
  switch (level) {
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

export default function RouteMap({ data }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

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

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !data) return;

    const markers: maplibregl.Marker[] = [];
    const layerIds: string[] = [];
    const sourceIds: string[] = [];

    const drawRoutes = () => {
      const bounds = new maplibregl.LngLatBounds();

      data.routes.forEach((route, index) => {
        const isRecommended =
          route.id === data.recommendation?.recommended_route_id;
        const sourceId = `route-source-${index}`;
        const layerId = `route-layer-${index}`;

        sourceIds.push(sourceId);
        layerIds.push(layerId);

        if (map.getLayer(layerId)) {
          map.removeLayer(layerId);
        }

        if (map.getSource(sourceId)) {
          map.removeSource(sourceId);
        }

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
              ? RECOMMENDED_ROUTE_COLOR
              : ROUTE_COLORS[index % ROUTE_COLORS.length],
            "line-width": isRecommended ? 8 : 4,
            "line-opacity": isRecommended ? 1 : 0.45,
          },
        });

        route.geometry.coordinates.forEach((coordinate) => {
          bounds.extend([coordinate[0], coordinate[1]]);
        });

        route.checkpoints.forEach((checkpoint) => {
          const color = riskColor(checkpoint.risk?.level ?? "unknown");

          const popup = new maplibregl.Popup({
            offset: 12,
          });

          const weather = checkpoint.weather;
          const risk = checkpoint.risk;

          const container = document.createElement("div");
          container.style.minWidth = "180px";

          const heading = document.createElement("strong");
          heading.textContent = `${route.name} — Checkpoint ${checkpoint.index + 1}`;
          container.appendChild(heading);

          const details = [
            `Distance: ${checkpoint.distance_miles} miles`,
            `Risk: ${risk?.level ?? "unknown"}`,
            `Risk score: ${risk?.score ?? "N/A"}`,
            weather
              ? `Wind gusts: ${weather.wind_gusts_mph ?? "N/A"} mph`
              : "Weather unavailable",
            weather ? `Rainfall: ${weather.rain_inches ?? "N/A"} in` : "",
          ].filter(Boolean);

          details.forEach((detail) => {
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

          markers.push(marker);
        });
        const recommendedIndex = data.routes.findIndex(
          (route) => route.id === data.recommendation?.recommended_route_id,
        );

        if (recommendedIndex >= 0) {
          const recommendedLayerId = `route-layer-${recommendedIndex}`;

          if (map.getLayer(recommendedLayerId)) {
            map.moveLayer(recommendedLayerId);
          }
        }
      });

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

        markers.push(marker);
      });

      if (!bounds.isEmpty()) {
        map.fitBounds(bounds, {
          padding: 60,
          maxZoom: 12,
        });
      }
    };

    if (map.isStyleLoaded()) {
      drawRoutes();
    } else {
      map.once("load", drawRoutes);
    }

    return () => {
      map.off("load", drawRoutes);

      markers.forEach((marker) => marker.remove());

      layerIds.forEach((layerId) => {
        if (map.getLayer(layerId)) {
          map.removeLayer(layerId);
        }
      });

      sourceIds.forEach((sourceId) => {
        if (map.getSource(sourceId)) {
          map.removeSource(sourceId);
        }
      });
    };
  }, [data]);

  return <div ref={containerRef} className="h-full min-h-[420px] w-full" />;
}
