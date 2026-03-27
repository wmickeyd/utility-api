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
    
    # 1. Try Alpha Vantage if key is provided
    av_key = os.getenv("ALPHA_VANTAGE_KEY")
    if av_key:
        try:
            url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={av_key}"
            r = requests.get(url, timeout=10)
            data = r.json()
            if "Global Quote" in data and data["Global Quote"]:
                quote = data["Global Quote"]
                return JSONResponse({
                    "symbol": symbol,
                    "name": symbol, # Alpha Vantage Global Quote doesn't give long name
                    "price": round(float(quote["05. price"]), 2),
                    "currency": "USD",
                    "source": "Alpha Vantage"
                })
        except Exception as e:
            logger.error(f"Alpha Vantage error: {e}")

    # 2. Improved yfinance fallback
    try:
        ticker = yf.Ticker(symbol)
        
        # Use history for better accuracy than fast_info
        hist = ticker.history(period="1d")
        if not hist.empty:
            price = hist['Close'].iloc[-1]
        else:
            # Fallback to fast_info if history fails
            info = ticker.fast_info
            price = info.get('last_price')
            
        currency = "USD"
        try:
            currency = ticker.info.get('currency', 'USD')
        except: pass
        
        name = symbol
        try:
            name = ticker.info.get('longName', symbol)
        except: pass
        
        if not price or str(price) == "nan":
            return JSONResponse({"error": f"Could not find price for {symbol}"}, status_code=404)

        return JSONResponse({
            "symbol": symbol,
            "name": name,
            "price": round(float(price), 2),
            "currency": currency,
            "source": "yfinance (history)"
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

@app.get("/define")
def define(word: str = Query(..., description="Word to define")):
    try:
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
        r = requests.get(url, timeout=10)
        if r.status_code == 404:
            return JSONResponse({"error": f"Word '{word}' not found."}, status_code=404)
        r.raise_for_status()
        data = r.json()[0]
        
        definition = data['meanings'][0]['definitions'][0]['definition']
        part_of_speech = data['meanings'][0]['partOfSpeech']
        
        return JSONResponse({
            "word": word,
            "phonetic": data.get('phonetic', ''),
            "part_of_speech": part_of_speech,
            "definition": definition
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
