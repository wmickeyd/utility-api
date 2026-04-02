# Utility API

A lightweight async FastAPI service that provides real-time data endpoints for the Kelor agent ecosystem. Called directly by the `agent-orchestrator` as tool backends.

## Endpoints

### Search & Discovery

| Endpoint | Description |
|---|---|
| `GET /search?q=<query>` | DuckDuckGo web search, returns top 5 results |
| `GET /image_search?q=<query>` | DuckDuckGo image search, returns top 3 results |
| `GET /news?q=<query>` | DuckDuckGo news search, returns top 5 headlines |
| `GET /reddit?url=<url>` | Reddit thread content and top 5 comments |

### Financial Data

`GET /finance?symbol=<symbol>`

Returns current price for a stock or cryptocurrency ticker. Tries Alpha Vantage first (if `ALPHA_VANTAGE_KEY` is set), falls back to `yfinance`.

```json
{
  "symbol": "AAPL",
  "name": "Apple Inc.",
  "price": 213.49,
  "currency": "USD",
  "source": "yfinance (history)"
}
```

### Weather

`GET /weather?location=<location>`

Current conditions via WeatherAPI.com. Requires `WEATHER_API_KEY`.

```json
{
  "location": "London, City of London, United Kingdom",
  "condition": "Partly Cloudy",
  "temp": "14.0°C",
  "feels_like": "13.1°C",
  "humidity": "72%",
  "wind": "19.4 km/h"
}
```

### YouTube Transcripts

`GET /youtube?url=<url>`

Fetches the auto-generated or manual transcript for a YouTube video (up to 8000 characters). Used by the agent to summarise video content.

```json
{
  "url": "https://youtu.be/dQw4w9WgXcQ",
  "transcript": "We're no strangers to love..."
}
```

### Dictionary

`GET /define?word=<word>`

Definition from the Free Dictionary API.

### Health

`GET /health` — returns `{"status": "healthy"}`

## Caching

Responses are cached in-memory to avoid redundant external API calls. Cache is per-process and resets on restart.

| Endpoint | TTL |
|---|---|
| `/finance` | 5 minutes |
| `/weather` | 10 minutes |
| `/news` | 15 minutes |
| `/define` | 60 minutes |
| `/youtube` | 60 minutes |
| `/search`, `/image_search`, `/reddit` | No cache (always fresh) |

## Tech Stack

- **Python 3.12+**
- **FastAPI** + **uvicorn**
- **aiohttp** — async HTTP for weather, finance, reddit, and dictionary requests
- **ddgs** — DuckDuckGo search (search, images, news); run in thread pool via `asyncio.to_thread`
- **yfinance** — stock/crypto fallback; run in thread pool via `asyncio.to_thread`
- **youtube-transcript-api** — YouTube transcript fetching; run in thread pool

## Setup

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `WEATHER_API_KEY` | Yes (for `/weather`) | WeatherAPI.com API key |
| `ALPHA_VANTAGE_KEY` | No | Alpha Vantage key; used as primary finance source if set |

### Running Locally

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

Or:

```bash
python main.py
```

Interactive API docs available at `http://localhost:8001/docs`.

### Kubernetes

Deployed to the `utility-dev` namespace via ArgoCD.

```bash
kubectl apply -k gitops/utility-api/overlays/dev
```

## Deployment Notes

- Container image built for `linux/arm64` (M1 Mac Mini cluster)
- Pushed to `ghcr.io/wmickeyd/utility-api` on every push to `main`
- ArgoCD detects the manifest update and redeploys automatically
