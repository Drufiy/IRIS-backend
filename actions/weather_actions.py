"""Weather information — current conditions, forecast, alerts."""

import asyncio
import httpx
from loguru import logger
from utils.config import load_config


async def get_weather(city: str = None, units: str = "metric") -> dict:
    """
    Get current weather for a city.

    Args:
        city: City name (e.g., "New York"). If None, uses config default.
        units: "metric" (°C), "imperial" (°F), or "standard" (Kelvin)

    Returns:
        {"status": "ok"/"error", "result": formatted weather string}
    """
    try:
        config = load_config("configs/settings.yaml").get("weather", {})
        api_key = config.get("openweather_api_key")

        if not api_key:
            return {
                "status": "error",
                "result": "Weather API key not configured. Add openweather_api_key to configs/settings.yaml"
            }

        if not city:
            city = config.get("default_city", "London")

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            _fetch_weather_sync,
            city,
            api_key,
            units
        )

        logger.info(f"Weather fetched for {city}")
        return {
            "status": "ok",
            "result": result
        }

    except Exception as e:
        logger.error(f"get_weather error: {e}")
        return {"status": "error", "result": str(e)}


async def get_forecast(city: str = None, days: int = 3) -> dict:
    """
    Get weather forecast for a city.

    Args:
        city: City name. If None, uses config default.
        days: Number of days (1-5)

    Returns:
        {"status": "ok"/"error", "result": forecast string}
    """
    try:
        if days < 1 or days > 5:
            days = 3

        config = load_config("configs/settings.yaml").get("weather", {})
        api_key = config.get("openweather_api_key")

        if not api_key:
            return {
                "status": "error",
                "result": "Weather API key not configured. Add openweather_api_key to configs/settings.yaml"
            }

        if not city:
            city = config.get("default_city", "London")

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            _fetch_forecast_sync,
            city,
            api_key,
            days
        )

        logger.info(f"Forecast fetched for {city}")
        return {
            "status": "ok",
            "result": result
        }

    except Exception as e:
        logger.error(f"get_forecast error: {e}")
        return {"status": "error", "result": str(e)}


def _fetch_weather_sync(city: str, api_key: str, units: str) -> str:
    """Blocking weather fetch. Run in executor."""
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units={units}"
        response = httpx.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("cod") != 200:
            return f"Weather data not available for {city}"

        main = data.get("main", {})
        weather = data.get("weather", [{}])[0]
        wind = data.get("wind", {})

        unit_symbol = "°C" if units == "metric" else "°F" if units == "imperial" else "K"
        description = weather.get("main", "Unknown")
        temp = main.get("temp", "N/A")
        feels_like = main.get("feels_like", "N/A")
        humidity = main.get("humidity", "N/A")
        wind_speed = wind.get("speed", "N/A")

        return (
            f"Weather in {city}: {description}, "
            f"{temp}{unit_symbol} (feels like {feels_like}{unit_symbol}), "
            f"Humidity {humidity}%, Wind {wind_speed} m/s"
        )

    except httpx.HTTPError as e:
        logger.error(f"OpenWeather API error: {e}")
        return f"Could not fetch weather for {city}"


def _fetch_forecast_sync(city: str, api_key: str, days: int) -> str:
    """Blocking forecast fetch. Run in executor."""
    try:
        url = f"https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={api_key}&units=metric&cnt={days * 8}"
        response = httpx.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("cod") != "200":
            return f"Forecast not available for {city}"

        forecasts = data.get("list", [])
        if not forecasts:
            return f"No forecast data available for {city}"

        output = [f"Forecast for {city} (next {days} days):"]

        for i, forecast in enumerate(forecasts[::8][:days]):  # Every 8th entry (24h)
            main = forecast.get("main", {})
            weather = forecast.get("weather", [{}])[0]
            description = weather.get("main", "Unknown")
            temp = main.get("temp", "N/A")
            dt = forecast.get("dt_txt", "N/A")

            output.append(f"  {dt}: {description}, {temp}°C")

        return "\n".join(output)

    except httpx.HTTPError as e:
        logger.error(f"OpenWeather API error: {e}")
        return f"Could not fetch forecast for {city}"
