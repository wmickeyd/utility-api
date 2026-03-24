# Utility API

A FastAPI-based service providing various utility endpoints for search, financial data, weather, and web content extraction.

## Features & Endpoints

- **`/search`**: General text search using DuckDuckGo.
- **`/finance`**: Real-time stock and cryptocurrency price data using `yfinance` and optional Alpha Vantage integration.
- **`/weather`**: Current weather conditions for a given location (requires WeatherAPI key).
- **`/reddit`**: Extract post content and top comments from any Reddit URL.
- **`/news`**: Latest news search via DuckDuckGo.
- **`/image_search`**: Image search capabilities.

## Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configuration**:
   Set the following environment variables if needed:
   - `WEATHER_API_KEY`: Required for `/weather` endpoint.
   - `ALPHA_VANTAGE_KEY`: Optional; used as a primary source for stock data.

3. **Run the API**:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8001 --reload
   ```
   Or:
   ```bash
   python main.py
   ```

## API Documentation

Once running, the interactive API documentation is available at:
- Swagger UI: `http://localhost:8001/docs`
- Redoc: `http://localhost:8001/redoc`
