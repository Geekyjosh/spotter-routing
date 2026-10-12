# Spotter Routing

A weather-aware truck routing application built with React, TypeScript, and Django.

The idea behind this project is simple: the shortest route isn't always the safest route, especially when you're driving a truck through bad weather.

Spotter Routing compares alternative driving routes, checks forecast conditions along each route, and recommends a route based on weather risk, distance, and estimated travel time.

**Live demo:** https://spotter-routing.vercel.app/

**Backend:** https://spotter-routing-dyd7.onrender.com/

## How it works

The user enters an origin, destination, departure time, and truck load weight. They can also choose how frequently weather should be checked along the journey (every 10, 25, or 50 miles).

The backend uses OSRM to calculate driving routes and OpenWeatherMap to retrieve weather forecasts for checkpoints along those routes.

Instead of checking only the current weather, the application estimates when the truck will reach each checkpoint and uses the forecast closest to that time.

Each checkpoint receives a risk classification based on wind, rainfall, snowfall, and load weight.

The routes are then compared using:

1. Severe or no-travel miles
2. High-risk miles
3. Average weather risk
4. Estimated driving time

Weather safety takes priority over journey duration.

## Tech stack

**Frontend:** React, TypeScript, Vite, Tailwind CSS, MapLibre GL JS

**Backend:** Python, Django, Django REST Framework

**APIs and services:**

- OSRM for route calculations
- OpenStreetMap Nominatim for geocoding
- OpenWeatherMap for weather forecasts
- OpenFreeMap for map rendering

The frontend is hosted on Vercel, while the Django API runs on Render.

## Running locally

Clone the repository:

```bash
git clone https://github.com/Geekyjosh/spotter-routing.git
cd spotter-routing
```

### Backend

```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
```

Set your `OPENWEATHER_API_KEY` environment variable, then run:

```bash
python manage.py migrate
python manage.py runserver
```

### Frontend

Open another terminal:

```bash
cd frontend
npm install
```

Create `frontend/.env.local`:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api
```

Start the frontend:

```bash
npm run dev
```

## Weather visualization

The map shows the available routes, checkpoints, and their weather-risk classifications.

I also added a 48-hour forecast slider so users can see how the weather risk along the recommended route changes over time.

OpenWeatherMap provides forecast data in three-hour intervals, so the timeline uses those available forecast periods rather than claiming minute-by-minute accuracy.

## Testing

I wrote Django tests covering the main risk thresholds, load-weight rules, route recommendations, and risk mileage calculations.

Run the tests with:

```bash
cd backend
python manage.py test weather
```

The latest local run passed all 25 tests.

## Trade-offs and limitations

There are a few things I'd approach differently in a production version.

**Truck-specific routing:** OSRM provides general road routes. It doesn't account for truck height restrictions, axle limits, or roads where commercial vehicles are prohibited. A dedicated truck-routing provider would be necessary before using this for real dispatch decisions.

**Forecast precision:** OpenWeatherMap provides three-hour forecast intervals. I use the nearest forecast to the estimated checkpoint arrival time, but that is still an approximation.

**Weather coverage:** The risk overlay is based on sampled locations along the route, not a continuous weather radar layer. Risk mileage is also estimated from checkpoint segments.

**Route alternatives:** OSRM doesn't always return three distinct alternatives, so the backend also attempts waypoint-based alternatives.

**Hosting:** The backend runs on Render, so the first request may take longer when the service has been inactive.

## What I'd improve next

With more time, I'd focus on adding truck-specific routing, improving the accuracy of weather-risk mileage, caching forecast requests, and testing the application against more routes and severe-weather scenarios.

I'd also like to add a clearer breakdown of why one route was recommended over another.

## Author

Olaoluwa Joshua Daramola

[GitHub](https://github.com/Geekyjosh) · [Portfolio](https://josh-darams.vercel.app/)
