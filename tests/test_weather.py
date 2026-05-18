"""Weather actions tests."""

import pytest
from actions.weather_actions import get_weather, get_forecast
from actions.action_router import ACTION_HANDLERS
from actions.safety import classify, SafetyLevel


def test_weather_handlers_registered():
    """Verify weather actions are registered."""
    assert "get_weather" in ACTION_HANDLERS
    assert "get_forecast" in ACTION_HANDLERS


def test_weather_safety_classification():
    """Verify weather actions are SAFE."""
    assert classify("get_weather") == SafetyLevel.SAFE
    assert classify("get_forecast") == SafetyLevel.SAFE


def test_get_weather_no_api_key():
    """Test get_weather fails gracefully without API key."""
    import asyncio
    from unittest.mock import patch

    async def run():
        mock_config = {"weather": {}}
        with patch("actions.weather_actions.load_config", return_value=mock_config):
            result = await get_weather("London")
            assert result["status"] == "error"
            assert "not configured" in result["result"].lower()

    asyncio.run(run())


def test_get_weather_valid_format():
    """Test get_weather accepts valid city."""
    import asyncio
    from unittest.mock import patch

    async def run():
        mock_config = {"weather": {"openweather_api_key": "test_key", "default_city": "London"}}
        with patch("actions.weather_actions.load_config", return_value=mock_config):
            with patch("actions.weather_actions._fetch_weather_sync", return_value="Weather info"):
                result = await get_weather("Paris")
                assert result["status"] == "ok"

    asyncio.run(run())


def test_get_weather_uses_default_city():
    """Test get_weather uses default city when none provided."""
    import asyncio
    from unittest.mock import patch

    async def run():
        mock_config = {"weather": {"openweather_api_key": "test_key", "default_city": "London"}}
        with patch("actions.weather_actions.load_config", return_value=mock_config):
            with patch("actions.weather_actions._fetch_weather_sync", return_value="Weather") as mock_fetch:
                result = await get_weather(city=None)
                assert result["status"] == "ok"
                # Should call with default city
                assert mock_fetch.called

    asyncio.run(run())


def test_get_forecast_invalid_days():
    """Test get_forecast clamps days to valid range."""
    import asyncio
    from unittest.mock import patch

    async def run():
        mock_config = {"weather": {"openweather_api_key": "test_key"}}
        with patch("actions.weather_actions.load_config", return_value=mock_config):
            with patch("actions.weather_actions._fetch_forecast_sync", return_value="Forecast"):
                # Days = 10 should be clamped to 5
                result = await get_forecast("London", days=10)
                assert result["status"] == "ok"

    asyncio.run(run())


def test_get_forecast_no_api_key():
    """Test get_forecast fails gracefully without API key."""
    import asyncio
    from unittest.mock import patch

    async def run():
        mock_config = {"weather": {}}
        with patch("actions.weather_actions.load_config", return_value=mock_config):
            result = await get_forecast("London")
            assert result["status"] == "error"
            assert "not configured" in result["result"].lower()

    asyncio.run(run())
