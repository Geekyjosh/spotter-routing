import CheckpointWeather from "./features/weather/CheckpointWeather";
import { useEffect, useState } from "react";
import {
  Truck,
  CloudSun,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  MapPinned,
  Route,
  ShieldCheck,
  Wind,
} from "lucide-react";
import { checkApiHealth, generateRoutes, type RouteResponse } from "./lib/api";
import RoutePlanner, {
  type RouteFormData,
} from "./features/routes/RoutePlanner";
import RouteMap from "./features/routes/RouteMap";
type ApiStatus = "checking" | "connected" | "offline";
const ROUTE_COLORS = ["#0891b2", "#2563eb", "#64748b"];
function getRiskLevel(score: number | null) {
  if (score === null) return "Unknown";
  if (score >= 70) return "High";
  if (score >= 35) return "Moderate";
  return "Low";
}
function getRiskStyle(score: number | null) {
  if (score === null) {
    return "bg-slate-100 text-slate-600";
  }
  if (score >= 70) {
    return "bg-red-100 text-red-700";
  }
  if (score >= 35) {
    return "bg-amber-100 text-amber-700";
  }
  return "bg-green-100 text-green-700";
}
export default function App() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");
  const [tripDetails, setTripDetails] = useState<RouteFormData | null>(null);
  const [routeData, setRouteData] = useState<RouteResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    checkApiHealth()
      .then((data) => {
        if (active) {
          setApiStatus(data.status === "ok" ? "connected" : "offline");
        }
      })
      .catch(() => {
        if (active) setApiStatus("offline");
      });
    return () => {
      active = false;
    };
  }, []);
  async function handleRouteSubmit(data: RouteFormData) {
    setTripDetails(data);
    setRouteData(null);
    setError("");
    setLoading(true);
    try {
      const response = await generateRoutes(data);
      setRouteData(response);
    } catch (err: unknown) {
      let message = "Unable to generate routes. Please try again.";
      if (typeof err === "object" && err !== null && "response" in err) {
        const axiosError = err as {
          response?: {
            data?: {
              error?: string;
            };
          };
        };
        message = axiosError.response?.data?.error || message;
      }
      setError(message);
    } finally {
      setLoading(false);
    }
  }
  const recommendation = routeData?.recommendation;
  const recommendedRoute = routeData?.routes.find(
    (route) => route.id === recommendation?.recommended_route_id,
  );
  return (
    <div className="min-h-screen bg-[#F4F6F8] text-[#172B35]">
      <header className="border-b border-[#DCE3E7] bg-[#0B2530]">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <Truck size={27} className="text-white" />
            <span className="text-xl font-bold text-white">
              Spotter Routing
            </span>
          </div>
          <span className="hidden text-sm text-[#DCE8EB] sm:block">
            Weather-Aware Truck Routing
          </span>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-6 py-7">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold">Route Planning Dashboard</h1>
            <p className="mt-1 text-sm text-[#52616B]">
              Compare routes and evaluate weather conditions before departure.
            </p>
          </div>
          <div className="flex items-center gap-2 rounded-md border border-[#DCE3E7] bg-white px-3 py-2 text-sm">
            {apiStatus === "connected" ? (
              <>
                <CheckCircle2 size={17} className="text-green-700" />
                <span>Backend connected</span>
              </>
            ) : apiStatus === "offline" ? (
              <>
                <AlertCircle size={17} className="text-red-700" />
                <span>Backend unavailable</span>
              </>
            ) : (
              <span className="text-[#52616B]">Checking connection...</span>
            )}
          </div>
        </div>
        <div className="grid items-start gap-5 lg:grid-cols-[360px_minmax(0,1fr)]">
          <RoutePlanner onSubmit={handleRouteSubmit} loading={loading} />
          <div className="min-w-0 space-y-5">
            {error && (
              <div className="flex items-start gap-3 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                <AlertCircle size={19} />
                <span>{error}</span>
              </div>
            )}
            <section className="overflow-hidden rounded-md border border-[#DCE3E7] bg-white">
              <div className="flex items-center justify-between border-b border-[#E3E8EC] px-5 py-4">
                <h2 className="flex items-center gap-2 font-semibold">
                  <MapPinned size={20} className="text-[#087F8C]" />
                  Route Map
                </h2>
                <span className="text-xs text-[#647480]">
                  {routeData
                    ? `${routeData.route_count} routes found`
                    : loading
                      ? "Generating routes..."
                      : "Interactive map"}
                </span>
              </div>
              <div className="relative h-[480px]">
                <RouteMap data={routeData} />
                {!routeData && (
                  <div className="pointer-events-none absolute bottom-4 left-4 right-4 rounded-md border border-[#DCE3E7] bg-white p-4 text-center shadow-sm">
                    <p className="text-sm font-medium">
                      {loading
                        ? "Calculating routes and analyzing weather..."
                        : "Enter your trip details and click Generate Routes."}
                    </p>
                  </div>
                )}
              </div>
              {routeData && (
                <div className="flex flex-wrap gap-4 border-t border-[#E3E8EC] px-5 py-3 text-xs text-[#52616B]">
                  <span className="flex items-center gap-2">
                    <span className="h-3 w-3 rounded-full bg-green-600" />
                    Low risk
                  </span>
                  <span className="flex items-center gap-2">
                    <span className="h-3 w-3 rounded-full bg-amber-500" />
                    Moderate risk
                  </span>
                  <span className="flex items-center gap-2">
                    <span className="h-3 w-3 rounded-full bg-red-600" />
                    High risk
                  </span>
                  <span className="flex items-center gap-2">
                    <span className="h-3 w-3 rounded-full bg-slate-500" />
                    Unknown
                  </span>
                </div>
              )}
            </section>
            {routeData && recommendation && (
              <section className="rounded-md border border-[#DCE3E7] bg-white">
                <div className="border-b border-[#E3E8EC] px-5 py-4">
                  <h2 className="flex items-center gap-2 font-semibold">
                    <ShieldCheck size={20} className="text-[#087F8C]" />
                    Weather-Based Route Recommendation
                  </h2>
                </div>
                <div className="p-5">
                  {recommendedRoute ? (
                    <>
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className="text-xs font-medium uppercase tracking-wide text-[#647480]">
                            Preferred Route
                          </p>
                          <h3 className="mt-1 text-xl font-bold">
                            {recommendedRoute.name}
                          </h3>
                        </div>
                        <span className="rounded-md border border-[#B8D7DB] bg-[#E8F5F6] px-3 py-2 text-xs font-semibold text-[#075E68]">
                          {recommendation.status === "complete"
                            ? "Complete comparison"
                            : "Provisional recommendation"}
                        </span>
                      </div>
                      <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-3">
                        <div>
                          <p className="text-xs text-[#647480]">Average Risk</p>
                          <p className="mt-1 text-lg font-bold">
                            {recommendation.average_risk_score ?? "N/A"}
                            <span className="text-sm font-normal text-[#647480]">
                              /100
                            </span>
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-[#647480]">Maximum Risk</p>
                          <p className="mt-1 text-lg font-bold">
                            {recommendation.maximum_risk_score ?? "N/A"}
                            <span className="text-sm font-normal text-[#647480]">
                              /100
                            </span>
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-[#647480]">
                            Estimated Time
                          </p>
                          <p className="mt-1 text-lg font-bold">
                            {Math.round(recommendedRoute.duration_minutes)} min
                          </p>
                        </div>
                      </div>
                      <p className="mt-4 text-sm leading-6 text-[#52616B]">
                        {recommendation.reason}
                      </p>
                    </>
                  ) : (
                    <div className="flex items-start gap-3 text-sm">
                      <AlertTriangle
                        size={20}
                        className="shrink-0 text-amber-600"
                      />
                      <p>{recommendation.reason}</p>
                    </div>
                  )}
                  {!routeData.truck_restrictions_verified && (
                    <div className="mt-5 flex items-start gap-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                      <AlertTriangle size={18} className="mt-0.5 shrink-0" />
                      <p>
                        Truck-specific road restrictions have not been verified.
                        Weather scores are illustrative and should not be used
                        as the sole basis for driving decisions.
                      </p>
                    </div>
                  )}
                </div>
              </section>
            )}
            {routeData && (
              <section className="rounded-md border border-[#DCE3E7] bg-white">
                <div className="border-b border-[#E3E8EC] px-5 py-4">
                  <h2 className="flex items-center gap-2 font-semibold">
                    <Route size={20} className="text-[#087F8C]" />
                    Available Routes
                  </h2>
                  <p className="mt-1 text-xs text-[#647480]">
                    Weather risks are estimated from forecast checkpoints. Truck
                    restrictions remain unverified.
                  </p>
                </div>
                <div className="grid gap-3 p-5 sm:grid-cols-2">
                  {routeData.routes.map((route, index) => {
                    const isRecommended =
                      route.id === recommendation?.recommended_route_id;
                    const risk = route.risk_summary;
                    const riskLevel = getRiskLevel(risk.maximum_score);
                    return (
                      <div
                        key={route.id}
                        className={`rounded-md border p-4 ${
                          isRecommended
                            ? "border-[#087F8C] bg-[#F2FAFA]"
                            : "border-[#DCE3E7] bg-white"
                        }`}
                      >
                        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span
                              className="h-3 w-3 rounded-full"
                              style={{
                                backgroundColor:
                                  ROUTE_COLORS[index % ROUTE_COLORS.length],
                              }}
                            />
                            <h3 className="font-semibold">{route.name}</h3>
                          </div>
                          {isRecommended && (
                            <span className="rounded bg-[#087F8C] px-2 py-1 text-xs font-medium text-white">
                              Preferred
                            </span>
                          )}
                        </div>
                        <div className="grid grid-cols-2 gap-4 text-sm">
                          <div>
                            <p className="text-[#647480]">Distance</p>
                            <p className="mt-1 font-semibold">
                              {route.distance_miles.toLocaleString()} miles
                            </p>
                          </div>
                          <div>
                            <p className="text-[#647480]">Estimated Time</p>
                            <p className="mt-1 font-semibold">
                              {Math.round(route.duration_minutes)} min
                            </p>
                          </div>
                          <div>
                            <p className="text-[#647480]">Average Risk</p>
                            <p className="mt-1 font-semibold">
                              {risk.average_score ?? "N/A"}
                              /100
                            </p>
                          </div>
                          <div>
                            <p className="text-[#647480]">Maximum Risk</p>
                            <span
                              className={`mt-1 inline-block rounded px-2 py-1 text-xs font-semibold ${getRiskStyle(
                                risk.maximum_score,
                              )}`}
                            >
                              {riskLevel} ({risk.maximum_score ?? "N/A"})
                            </span>
                          </div>
                        </div>
                        <div className="mt-4 border-t border-[#E3E8EC] pt-3">
                          <div className="flex items-center gap-2 text-xs text-[#52616B]">
                            <Wind size={15} />
                            <span>
                              Weather coverage:{" "}
                              {route.weather_checkpoints_available}/
                              {route.checkpoint_count} checkpoints
                            </span>
                          </div>
                          {!risk.assessment_complete && (
                            <p className="mt-2 text-xs font-medium text-amber-700">
                              Incomplete forecast coverage — route risk may be
                              underestimated.
                            </p>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>
            )}
            {routeData && (
              <CheckpointWeather
                key={`${routeData.departure_time}-${routeData.origin.label}-${routeData.destination.label}`}
                data={routeData}
              />
            )}
            <section className="rounded-md border border-[#DCE3E7] bg-white">
              <div className="border-b border-[#E3E8EC] px-5 py-4">
                <h2 className="flex items-center gap-2 font-semibold">
                  <CloudSun size={20} className="text-[#087F8C]" />
                  Trip Details
                </h2>
              </div>
              <div className="p-5">
                {tripDetails ? (
                  <dl className="grid gap-4 text-sm sm:grid-cols-2">
                    <div>
                      <dt className="text-[#647480]">Origin</dt>
                      <dd className="mt-1 font-semibold">
                        {tripDetails.origin}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-[#647480]">Destination</dt>
                      <dd className="mt-1 font-semibold">
                        {tripDetails.destination}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-[#647480]">Load Weight</dt>
                      <dd className="mt-1 font-semibold">
                        {tripDetails.loadWeight.toLocaleString()} lbs
                      </dd>
                    </div>
                    <div>
                      <dt className="text-[#647480]">Checkpoint Interval</dt>
                      <dd className="mt-1 font-semibold">
                        Every {tripDetails.checkpointInterval} miles
                      </dd>
                    </div>
                    <div className="sm:col-span-2">
                      <dt className="text-[#647480]">Departure Date & Time</dt>
                      <dd className="mt-1 font-semibold">
                        {new Date(tripDetails.departureTime).toLocaleString()}
                      </dd>
                    </div>
                  </dl>
                ) : (
                  <p className="text-sm text-[#647480]">
                    Your trip information will appear here after submitting the
                    route form.
                  </p>
                )}
              </div>
            </section>
          </div>
        </div>
      </main>
    </div>
  );
}
