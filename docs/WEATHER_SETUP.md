# Weather Setup & Usage

IRIS can give you current weather and forecasts via voice.

## Quick Start

### Get Current Weather
```
"What's the weather?"
"What's the weather in Paris?"
"Tell me the weather in Tokyo"
```

Expected response:
```
"Weather in London: Cloudy, 15°C (feels like 12°C), Humidity 72%, Wind 5 m/s"
```

### Get Forecast
```
"Show me the forecast"
"What's the weather forecast for 5 days?"
"Forecast for New York"
```

Expected response:
```
"Forecast for London (next 3 days):
  2026-05-18 12:00: Cloudy, 14°C
  2026-05-19 12:00: Rainy, 12°C
  2026-05-20 12:00: Sunny, 16°C"
```

## Setup (5 minutes)

### 1. Get a Free API Key

1. Go to [openweathermap.org/api](https://openweathermap.org/api)
2. Click "Sign Up"
3. Create a free account
4. Go to API keys section
5. Copy your API key (32-character string)

### 2. Add to Configuration

Edit `configs/settings.yaml`:

```yaml
weather:
  openweather_api_key: "YOUR_API_KEY_HERE"  # Paste your key
  default_city: "London"                     # Your city
```

Example:
```yaml
weather:
  openweather_api_key: "YOUR_32_CHARACTER_API_KEY_HERE"
  default_city: "New York"
```

### 3. Restart IRIS

That's it!

## Usage

### Weather Information Returned

**Current weather includes:**
- Description (Sunny, Cloudy, Rainy, etc.)
- Temperature (°C by default)
- "Feels like" temperature
- Humidity (%)
- Wind speed (m/s)

### Forecast

- Shows 24-hour forecasts for next 3 days
- Can request 1-5 days ahead
- Displays time, condition, and temperature

## Configuration

Edit `configs/settings.yaml`:

```yaml
weather:
  openweather_api_key: "your_key"   # Required: your API key
  default_city: "London"             # Default city for "What's the weather?"
```

### Multiple Cities

```
"What's the weather in Paris?"   # Works for any city
"Forecast for Tokyo"             # Works for any city
"Get weather in Sydney"          # Works for any city
```

## Safety Level

| Action | Level | Approval |
|--------|-------|----------|
| get_weather | SAFE | Auto-execute |
| get_forecast | SAFE | Auto-execute |

Both auto-execute with no approval needed.

## Examples

### Daily Routine
```
Morning:
"What's the weather?"
→ "Weather in London: Cloudy, 15°C..."

"Do I need an umbrella?"
→ Check the response above

Before travel:
"Forecast for Barcelona"
```

### Trip Planning
```
"What's the weather in New York?"
"Forecast for Miami"
"What's the weather in Los Angeles?"
```

## Temperature Units

By default: **Celsius (°C)**

To use Fahrenheit or Kelvin (advanced):
- Modify `weather_actions.py` and change `units` parameter
- Or add config option (future enhancement)

## Limitations

- No historical weather
- No severe weather alerts
- No UV index or air quality
- No radar/maps
- Limited to OpenWeather's 5-day forecast

## Troubleshooting

### "Weather API key not configured"
- Add `openweather_api_key` to `configs/settings.yaml`
- Verify key is copied correctly (no spaces)
- Restart IRIS

### "Could not fetch weather for X"
- City name might be wrong (try full name: "New York" not "NYC")
- Check internet connection
- Verify API key is valid
- Wait a few seconds and retry

### "No forecast data available"
- City might not be in OpenWeather database
- Try a larger city nearby
- Check spelling

## API Limits (Free Tier)

- 1,000 calls/day
- 60 calls/minute
- This is plenty for personal use

## Privacy

- Requests go directly to OpenWeather's servers
- No credentials sent to IRIS system
- Minimal API calls (not abused)

## Free Tier vs Paid

Free tier includes:
- ✅ Current weather
- ✅ 5-day forecast
- ✅ 1000 calls/day
- ✅ Worldwide coverage

Paid tier adds:
- Historical data
- Severe weather alerts
- Air quality

Free tier is sufficient for personal use.

## Examples by Use Case

### Commute Planning
```
"What's the weather?"
"Should I bring an umbrella?"
"Forecast for tomorrow"
```

### Travel
```
"Weather in Barcelona"
"What's the forecast in London"
"Get weather for Tokyo, Seoul, and Hong Kong"
```

### Activity Planning
```
"Is it nice out?" → Check weather
"Forecast for next 3 days" → Plan weekend
```

## Storage

No local storage — all requests are live to OpenWeather API.
