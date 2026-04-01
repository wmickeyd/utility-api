from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
import aiohttp
import asyncio
import logging
import os
import time
from urllib.parse import urlparse
import yfinance as yf
from ddgs import DDGS
import uvicorn

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()


class TTLCache:
    """Simple in-memory cache with per-entry TTL (seconds)."""

    def __init__(self):
        self._store: dict = {}

    def get(self, key: str):
        entry = self._store.get(key)
        if entry and time.monotonic() < entry["expires_at"]:
            return entry["value"]
        return None

    def set(self, key: str, value, ttl: int):
        self._store[key] = {"value": value, "expires_at": time.monotonic() + ttl}

    def invalidate(self, key: str):
        self._store.pop(key, None)


cache = TTLCache()

FINANCE_TTL = 300    # 5 minutes
WEATHER_TTL = 600    # 10 minutes
NEWS_TTL    = 900    # 15 minutes
DEFINE_TTL  = 3600   # 60 minutes

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"
    )
}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/finance")
async def get_finance(symbol: str = Query(..., description="Ticker symbol (e.g. AAPL, BTC-USD)")):
    logger.info(f"Received finance request for: {symbol}")

    cached = cache.get(f"finance:{symbol.upper()}")
    if cached:
        logger.info(f"Cache hit for finance:{symbol}")
        return JSONResponse(cached)

    # 1. Try Alpha Vantage if key is provided
    av_key = os.getenv("ALPHA_VANTAGE_KEY")
    if av_key:
        try:
            url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={av_key}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                    data = await r.json()
                    if "Global Quote" in data and data["Global Quote"]:
                        quote = data["Global Quote"]
                        payload = {
                            "symbol": symbol,
                            "name": symbol,
                            "price": round(float(quote["05. price"]), 2),
                            "currency": "USD",
                            "source": "Alpha Vantage"
                        }
                        cache.set(f"finance:{symbol.upper()}", payload, FINANCE_TTL)
                        return JSONResponse(payload)
        except Exception as e:
            logger.error(f"Alpha Vantage error: {e}")

    # 2. yfinance fallback (blocking library — run in thread)
    def _fetch_yfinance():
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1d")
        if not hist.empty:
            price = hist['Close'].iloc[-1]
        else:
            price = ticker.fast_info.get('last_price')

        currency = "USD"
        name = symbol
        try:
            info = ticker.info
            currency = info.get('currency', 'USD')
            name = info.get('longName', symbol)
        except Exception:
            pass

        return price, currency, name

    try:
        price, currency, name = await asyncio.to_thread(_fetch_yfinance)

        if not price or str(price) == "nan":
            return JSONResponse({"error": f"Could not find price for {symbol}"}, status_code=404)

        payload = {
            "symbol": symbol,
            "name": name,
            "price": round(float(price), 2),
            "currency": currency,
            "source": "yfinance (history)"
        }
        cache.set(f"finance:{symbol.upper()}", payload, FINANCE_TTL)
        return JSONResponse(payload)
    except Exception as e:
        logger.error(f"Error fetching finance data: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/search")
async def search(q: str = Query(..., description="Search query")):
    logger.info(f"Received search request for: {q}")
    try:
        def _ddgs_search():
            with DDGS() as ddgs:
                return [r for r in ddgs.text(q, max_results=5)]

        results = await asyncio.to_thread(_ddgs_search)
        return JSONResponse({"query": q, "results": results})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/image_search")
async def image_search(q: str = Query(..., description="Image search query")):
    try:
        def _ddgs_images():
            with DDGS() as ddgs:
                return [r for r in ddgs.images(q, max_results=3)]

        results = await asyncio.to_thread(_ddgs_images)
        return JSONResponse({"query": q, "results": results})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/news")
async def get_news(q: str = Query(..., description="News topic")):
    cached = cache.get(f"news:{q.lower()}")
    if cached:
        logger.info(f"Cache hit for news:{q}")
        return JSONResponse(cached)

    try:
        def _ddgs_news():
            with DDGS() as ddgs:
                return [r for r in ddgs.news(q, max_results=5)]

        results = await asyncio.to_thread(_ddgs_news)
        payload = {"query": q, "results": results}
        cache.set(f"news:{q.lower()}", payload, NEWS_TTL)
        return JSONResponse(payload)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/weather")
async def get_weather(location: str = Query(..., description="Location (e.g. London, New York)")):
    api_key = os.getenv("WEATHER_API_KEY")
    if not api_key:
        return JSONResponse({"error": "Weather API key not configured"}, status_code=500)

    cached = cache.get(f"weather:{location.lower()}")
    if cached:
        logger.info(f"Cache hit for weather:{location}")
        return JSONResponse(cached)

    try:
        url = f"http://api.weatherapi.com/v1/current.json?key={api_key}&q={location}&aqi=no"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                r.raise_for_status()
                data = await r.json()

        current = data['current']
        loc_data = data['location']

        payload = {
            "location": f"{loc_data['name']}, {loc_data['region']}, {loc_data['country']}",
            "condition": current['condition']['text'],
            "temp": f"{current['temp_c']}°C",
            "temp_f": f"{current['temp_f']}°F",
            "feels_like": f"{current['feelslike_c']}°C",
            "feels_like_f": f"{current['feelslike_f']}°F",
            "humidity": f"{current['humidity']}%",
            "wind": f"{current['wind_kph']} km/h",
            "last_updated": current['last_updated']
        }
        cache.set(f"weather:{location.lower()}", payload, WEATHER_TTL)
        return JSONResponse(payload)
    except Exception as e:
        logger.error(f"Error fetching weather from WeatherAPI: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/reddit")
async def get_reddit(url: str = Query(..., description="Reddit URL")):
    try:
        if ".json" not in url:
            parsed = urlparse(url)
            url = f"https://{parsed.netloc}{parsed.path}.json"
            if parsed.query:
                url += f"?{parsed.query}"

        async with aiohttp.ClientSession(headers=HEADERS) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                r.raise_for_status()
                data = await r.json()

        post_data = data[0]['data']['children'][0]['data']
        comments = []
        for child in data[1]['data']['children'][:5]:
            if child['kind'] == 't1':
                comments.append({"author": child['data'].get('author'), "body": child['data'].get('body')})

        return JSONResponse({
            "title": post_data.get('title'),
            "content": post_data.get('selftext', '')[:2000],
            "comments": comments
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/define")
async def define(word: str = Query(..., description="Word to define")):
    cached = cache.get(f"define:{word.lower()}")
    if cached:
        logger.info(f"Cache hit for define:{word}")
        return JSONResponse(cached)

    try:
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 404:
                    return JSONResponse({"error": f"Word '{word}' not found."}, status_code=404)
                r.raise_for_status()
                data = await r.json()

        entry = data[0]
        definition = entry['meanings'][0]['definitions'][0]['definition']
        part_of_speech = entry['meanings'][0]['partOfSpeech']

        payload = {
            "word": word,
            "phonetic": entry.get('phonetic', ''),
            "part_of_speech": part_of_speech,
            "definition": definition
        }
        cache.set(f"define:{word.lower()}", payload, DEFINE_TTL)
        return JSONResponse(payload)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
