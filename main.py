from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
import requests
import logging
import os
from urllib.parse import urlparse
import yfinance as yf
from ddgs import DDGS
import uvicorn
import certifi

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"
    )
}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.get("/finance")
def get_finance(symbol: str = Query(..., description="Ticker symbol (e.g. AAPL, BTC-USD)")):
    logger.info(f"Received finance request for: {symbol}")
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        price = info.get('last_price')
        currency = info.get('currency', 'USD')
        
        meta = ticker.info
        name = meta.get('longName', symbol)
        
        return JSONResponse({
            "symbol": symbol,
            "name": name,
            "price": round(price, 2) if price else "N/A",
            "currency": currency
        })
    except Exception as e:
        logger.error(f"Error fetching finance data: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/search")
def search(q: str = Query(..., description="Search query")):
    logger.info(f"Received search request for: {q}")
    with DDGS() as ddgs:
        results = [r for r in ddgs.text(q, max_results=5)]
    return JSONResponse({"query": q, "results": results})

@app.get("/image_search")
def image_search(q: str = Query(..., description="Image search query")):
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.images(q, max_results=3)]
        return JSONResponse({"query": q, "results": results})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/news")
def get_news(q: str = Query(..., description="News topic")):
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.news(q, max_results=5)]
        return JSONResponse({"query": q, "results": results})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/weather")
def get_weather(location: str = Query(..., description="Location (e.g. London, New York)")):
    api_key = os.getenv("WEATHER_API_KEY")
    if not api_key:
        return JSONResponse({"error": "Weather API key not configured"}, status_code=500)
    
    try:
        # Use weatherapi.com
        url = f"http://api.weatherapi.com/v1/current.json?key={api_key}&q={location}&aqi=no"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        
        current = data['current']
        loc_data = data['location']
        
        return JSONResponse({
            "location": f"{loc_data['name']}, {loc_data['region']}, {loc_data['country']}",
            "condition": current['condition']['text'],
            "temp": f"{current['temp_c']}°C",
            "temp_f": f"{current['temp_f']}°F",
            "feels_like": f"{current['feelslike_c']}°C",
            "feels_like_f": f"{current['feelslike_f']}°F",
            "humidity": f"{current['humidity']}%",
            "wind": f"{current['wind_kph']} km/h",
            "last_updated": current['last_updated']
        })
    except Exception as e:
        logger.error(f"Error fetching weather from WeatherAPI: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/reddit")
def get_reddit(url: str = Query(..., description="Reddit URL")):
    try:
        if ".json" not in url:
            parsed = urlparse(url)
            url = f"https://{parsed.netloc}{parsed.path}.json"
            if parsed.query:
                url += f"?{parsed.query}"
        
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()
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

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
