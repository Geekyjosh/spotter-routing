import axios from "axios";

export const api = axios.create({
  baseURL: "/api",
  timeout: 60000,
});

export async function checkApiHealth() {
  const response = await api.get("/health/");
  return response.data;
}

export type RouteRequest = {
  origin: string;
  destination: string;
  departureTime: string;
  loadWeight: number;
  checkpointInterval: 10 | 25 | 50;
};

export type CheckpointWeather = {
  forecast_time: string;
  temperature_f: number | null;
  precipitation_inches: number | null;
  rain_inches: number | null;
  snowfall_cm: number | null;
  wind_speed_mph: number | null;
  wind_gusts_mph: number | null;
  weather_code: number | null;
};

export type CheckpointRisk = {
  score: number | null;
  level: "low" | "moderate" | "high" | "unknown";
  factors: string[];
};

export type RouteCheckpoint = {
  index: number;
  coordinates: number[];
  distance_miles: number;
  estimated_arrival: string;
  weather: CheckpointWeather | null;
  weather_status: "available" | "unavailable";
  weather_error?: string;
  risk: CheckpointRisk;
};

export type RouteRiskSummary = {
  average_score: number | null;
  maximum_score: number | null;
  known_checkpoints: number;
  unknown_checkpoints: number;
  assessment_complete: boolean;
};

export type GeneratedRoute = {
  id: string;
  name: string;
  distance_miles: number;
  duration_minutes: number;
  geometry: {
    type: "LineString";
    coordinates: number[][];
  };
  checkpoints: RouteCheckpoint[];
  checkpoint_count: number;
  weather_checkpoints_available: number;
  weather_checkpoints_unavailable: number;
  risk_summary: RouteRiskSummary;
};

export type RouteRecommendation = {
  status: "complete" | "provisional" | "unavailable";
  recommended_route_id: string | null;
  recommended_route_name?: string;
  average_risk_score?: number;
  maximum_risk_score?: number;
  estimated_duration_minutes?: number;
  reason: string;
  evaluated_route_count?: number;
  excluded_route_count?: number;
  truck_restrictions_verified?: boolean;
};

export type RouteResponse = {
  origin: {
    label: string;
    coordinates: number[];
  };
  destination: {
    label: string;
    coordinates: number[];
  };
  routes: GeneratedRoute[];
  route_count: number;
  departure_time: string;
  load_weight_lbs: number;
  checkpoint_interval_miles: number;
  routing_provider: string;
  truck_restrictions_verified: boolean;
  weather_analysis_status: string;
  recommendation_status: string;
  recommendation: RouteRecommendation;
};

export async function generateRoutes(payload: RouteRequest) {
  const response = await api.post<RouteResponse>("/routes/", payload);

  return response.data;
}

export interface HourlyWeatherForecast {
  forecast_time: string;
  temperature_f: number | null;
  precipitation_inches: number | null;
  rain_inches: number | null;
  snowfall_cm: number | null;
  wind_speed_mph: number | null;
  wind_gusts_mph: number | null;
  weather_code: number | null;
}

export interface WeatherForecastResponse {
  latitude: number;
  longitude: number;
  forecast_hours: number;
  forecasts: HourlyWeatherForecast[];
}

export async function get48HourForecast(
  latitude: number,
  longitude: number,
): Promise<WeatherForecastResponse> {
  const response = await api.get<WeatherForecastResponse>(
    "/weather/forecast/",
    {
      params: {
        latitude,
        longitude,
      },
    },
  );

  return response.data;
}
