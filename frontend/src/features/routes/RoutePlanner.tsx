import { useState, type FormEvent } from "react";
import { MapPin, CalendarClock, Truck, Route } from "lucide-react";

export type RouteFormData = {
  origin: string;
  destination: string;
  departureTime: string;
  loadWeight: number;
  checkpointInterval: number;
};

type Props = {
  onSubmit: (data: RouteFormData) => void | Promise<void>;
  loading?: boolean;
};

export default function RoutePlanner({ onSubmit, loading = false }: Props) {
  const [origin, setOrigin] = useState("New York, NY");
  const [destination, setDestination] = useState("Philadelphia, PA");
  const [departureTime, setDepartureTime] = useState("2026-10-12T09:00");
  const [loadWeight, setLoadWeight] = useState(25000);
  const [checkpointInterval, setCheckpointInterval] = useState(25);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!origin.trim() || !destination.trim() || !departureTime) return;

    onSubmit({
      origin: origin.trim(),
      destination: destination.trim(),
      departureTime: new Date(departureTime).toISOString(),
      loadWeight,
      checkpointInterval,
    });
  }

  const inputClass =
    "mt-2 w-full rounded-md border border-[#CBD5DB] bg-white px-3 py-3 text-sm text-[#172B35] outline-none focus:border-[#087F8C]";

  return (
    <section className="rounded-md border border-[#DCE3E7] bg-white">
      <div className="border-b border-[#E3E8EC] px-5 py-4">
        <h2 className="flex items-center gap-2 font-semibold text-[#172B35]">
          <Route size={20} className="text-[#087F8C]" />
          Plan Your Route
        </h2>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5 p-5">
        <label className="block text-sm font-medium">
          <span className="flex items-center gap-2">
            <MapPin size={16} /> Origin
          </span>
          <input
            className={inputClass}
            value={origin}
            onChange={(e) => setOrigin(e.target.value)}
            required
          />
        </label>

        <label className="block text-sm font-medium">
          <span className="flex items-center gap-2">
            <MapPin size={16} /> Destination
          </span>
          <input
            className={inputClass}
            value={destination}
            onChange={(e) => setDestination(e.target.value)}
            required
          />
        </label>

        <label className="block text-sm font-medium">
          <span className="flex items-center gap-2">
            <CalendarClock size={16} /> Departure Date & Time
          </span>
          <input
            type="datetime-local"
            className={inputClass}
            value={departureTime}
            onChange={(e) => setDepartureTime(e.target.value)}
            required
          />
        </label>

        <label className="block text-sm font-medium">
          <span className="flex items-center gap-2">
            <Truck size={16} /> Load Weight (lbs)
          </span>
          <input
            type="number"
            min={1}
            className={inputClass}
            value={loadWeight}
            onChange={(e) => setLoadWeight(Number(e.target.value))}
            required
          />
        </label>

        <label className="block text-sm font-medium">
          Checkpoint Interval
          <select
            className={inputClass}
            value={checkpointInterval}
            onChange={(e) => setCheckpointInterval(Number(e.target.value))}
          >
            <option value={10}>Every 10 miles</option>
            <option value={25}>Every 25 miles</option>
            <option value={50}>Every 50 miles</option>
          </select>
        </label>

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-md bg-[#087F8C] px-4 py-3 font-semibold text-white hover:bg-[#066B75] disabled:opacity-60"
        >
          {loading ? "Generating Routes..." : "Generate Routes"}
        </button>
      </form>
    </section>
  );
}
