"""AMap weather tool built on the shared Web Service client."""

from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

from app.tools.amap import AMapAPIError, _observed_at, _request, _text, geocode


class WeatherArgs(BaseModel):
    """Weather lookup arguments using a city name or six-digit adcode."""

    city: str = Field(min_length=1, max_length=50)
    extensions: Literal["base", "all"] = "all"


async def query_weather(
    city: str,
    extensions: Literal["base", "all"] = "all",
    *,
    client: httpx.AsyncClient | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Return current or forecast weather with source and observation time."""
    adcode = city
    if not (city.isdigit() and len(city) == 6):
        place = await geocode(city, client=client, api_key=api_key)
        adcode = place.get("adcode")
        if not adcode:
            raise AMapAPIError(f"高德地图没有返回城市 adcode：{city}")
    payload = await _request(
        "/v3/weather/weatherInfo",
        {"city": adcode, "extensions": extensions, "output": "JSON"},
        client=client,
        api_key=api_key,
    )

    if extensions == "base":
        rows = payload.get("lives") or []
        weather = rows[0] if rows else {}
        result: dict[str, Any] = {
            "province": _text(weather.get("province")),
            "city": _text(weather.get("city")) or city,
            "weather": _text(weather.get("weather")),
            "temperature_c": _text(weather.get("temperature")),
            "wind_direction": _text(weather.get("winddirection")),
            "wind_power": _text(weather.get("windpower")),
            "humidity_percent": _text(weather.get("humidity")),
            "report_time": _text(weather.get("reporttime")),
        }
    else:
        rows = payload.get("forecasts") or []
        forecast = rows[0] if rows else {}
        result = {
            "province": _text(forecast.get("province")),
            "city": _text(forecast.get("city")) or city,
            "report_time": _text(forecast.get("reporttime")),
            "casts": [
                {
                    "date": _text(cast.get("date")),
                    "day_weather": _text(cast.get("dayweather")),
                    "night_weather": _text(cast.get("nightweather")),
                    "day_temperature_c": _text(cast.get("daytemp")),
                    "night_temperature_c": _text(cast.get("nighttemp")),
                    "day_wind": _text(cast.get("daywind")),
                    "day_power": _text(cast.get("daypower")),
                }
                for cast in (forecast.get("casts") or [])[:4]
            ],
        }
    return {
        "query": city,
        "adcode": adcode,
        **result,
        "source": "amap.weather",
        "observed_at": _observed_at(),
    }
