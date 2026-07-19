import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from weather_models import HourlyWeather, WeatherSnapshot


OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

DEFAULT_LOCATION_NAME = "Springe"
DEFAULT_LATITUDE = 52.208
DEFAULT_LONGITUDE = 9.554
DEFAULT_TIMEZONE = "Europe/Berlin"

REQUEST_TIMEOUT_SECONDS = 10


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None

        return float(value)

    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None

        return int(value)

    except (TypeError, ValueError):
        return None


def _list_value(values: Any, index: int = 0) -> Any:
    """
    Safely obtains one value from an API list.
    """

    if not isinstance(values, list):
        return None

    if index < 0 or index >= len(values):
        return None

    return values[index]


def _build_hourly_forecast(hourly_data: Dict[str, Any]) -> List[HourlyWeather]:
    times = hourly_data.get("time") or []

    if not isinstance(times, list):
        return []

    hourly_forecast: List[HourlyWeather] = []

    for index, forecast_time in enumerate(times):
        hourly_forecast.append(
            HourlyWeather(
                time=str(forecast_time),
                temperature_c=_safe_float(
                    _list_value(hourly_data.get("temperature_2m"), index)
                ),
                apparent_temperature_c=_safe_float(
                    _list_value(
                        hourly_data.get("apparent_temperature"),
                        index,
                    )
                ),
                humidity_percent=_safe_float(
                    _list_value(
                        hourly_data.get("relative_humidity_2m"),
                        index,
                    )
                ),
                precipitation_probability_percent=_safe_float(
                    _list_value(
                        hourly_data.get("precipitation_probability"),
                        index,
                    )
                ),
                precipitation_mm=_safe_float(
                    _list_value(hourly_data.get("precipitation"), index)
                ),
                weather_code=_safe_int(
                    _list_value(hourly_data.get("weather_code"), index)
                ),
                wind_speed_kmh=_safe_float(
                    _list_value(hourly_data.get("wind_speed_10m"), index)
                ),
                wind_gusts_kmh=_safe_float(
                    _list_value(hourly_data.get("wind_gusts_10m"), index)
                ),
                uv_index=_safe_float(
                    _list_value(hourly_data.get("uv_index"), index)
                ),
            )
        )

    return hourly_forecast


def _unavailable_snapshot(
    location_name: str,
    latitude: float,
    longitude: float,
    timezone_name: str,
    error: str,
) -> WeatherSnapshot:
    """
    Creates a safe failure result instead of allowing weather to crash Phoenix.
    """

    return WeatherSnapshot(
        status="Unavailable",
        location_name=location_name,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone_name,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        error=error,
    )


def fetch_weather(
    location_name: str = DEFAULT_LOCATION_NAME,
    latitude: float = DEFAULT_LATITUDE,
    longitude: float = DEFAULT_LONGITUDE,
    timezone_name: str = DEFAULT_TIMEZONE,
    forecast_days: int = 2,
) -> WeatherSnapshot:
    """
    Fetches and normalises current, hourly and daily weather data.

    This function never deliberately raises an API/network exception.
    It returns a WeatherSnapshot with status='Unavailable' if the request fails.
    """

    safe_forecast_days = max(1, min(int(forecast_days), 7))

    parameters = {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": timezone_name,
        "forecast_days": safe_forecast_days,
        "temperature_unit": "celsius",
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
        "current": ",".join(
            [
                "temperature_2m",
                "relative_humidity_2m",
                "apparent_temperature",
                "precipitation",
                "weather_code",
                "wind_speed_10m",
                "wind_gusts_10m",
            ]
        ),
        "hourly": ",".join(
            [
                "temperature_2m",
                "relative_humidity_2m",
                "apparent_temperature",
                "precipitation_probability",
                "precipitation",
                "weather_code",
                "wind_speed_10m",
                "wind_gusts_10m",
                "uv_index",
            ]
        ),
        "daily": ",".join(
            [
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_probability_max",
                "precipitation_sum",
                "wind_speed_10m_max",
                "wind_gusts_10m_max",
                "uv_index_max",
                "sunrise",
                "sunset",
            ]
        ),
    }

    url = f"{OPEN_METEO_FORECAST_URL}?{urlencode(parameters)}"

    request = Request(
        url,
        headers={
            "User-Agent": "ProjectPhoenix/1.0",
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(
            request,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as response:
            response_text = response.read().decode("utf-8")
            payload = json.loads(response_text)

    except HTTPError as exc:
        return _unavailable_snapshot(
            location_name,
            latitude,
            longitude,
            timezone_name,
            f"Weather service returned HTTP {exc.code}.",
        )

    except URLError as exc:
        return _unavailable_snapshot(
            location_name,
            latitude,
            longitude,
            timezone_name,
            f"Weather service could not be reached: {exc.reason}",
        )

    except TimeoutError:
        return _unavailable_snapshot(
            location_name,
            latitude,
            longitude,
            timezone_name,
            "Weather request timed out.",
        )

    except json.JSONDecodeError:
        return _unavailable_snapshot(
            location_name,
            latitude,
            longitude,
            timezone_name,
            "Weather service returned invalid JSON.",
        )

    except Exception as exc:
        return _unavailable_snapshot(
            location_name,
            latitude,
            longitude,
            timezone_name,
            f"Unexpected weather error: {exc}",
        )

    if not isinstance(payload, dict):
        return _unavailable_snapshot(
            location_name,
            latitude,
            longitude,
            timezone_name,
            "Weather service returned an unexpected response.",
        )

    if payload.get("error"):
        return _unavailable_snapshot(
            location_name,
            latitude,
            longitude,
            timezone_name,
            str(payload.get("reason") or "Weather API error."),
        )

    current = payload.get("current") or {}
    hourly = payload.get("hourly") or {}
    daily = payload.get("daily") or {}

    return WeatherSnapshot(
        status="Available",
        location_name=location_name,
        latitude=_safe_float(payload.get("latitude")) or latitude,
        longitude=_safe_float(payload.get("longitude")) or longitude,
        timezone=str(payload.get("timezone") or timezone_name),
        fetched_at=datetime.now(timezone.utc).isoformat(),

        current_time=current.get("time"),
        current_temperature_c=_safe_float(
            current.get("temperature_2m")
        ),
        current_apparent_temperature_c=_safe_float(
            current.get("apparent_temperature")
        ),
        current_humidity_percent=_safe_float(
            current.get("relative_humidity_2m")
        ),
        current_precipitation_mm=_safe_float(
            current.get("precipitation")
        ),
        current_weather_code=_safe_int(
            current.get("weather_code")
        ),
        current_wind_speed_kmh=_safe_float(
            current.get("wind_speed_10m")
        ),
        current_wind_gusts_kmh=_safe_float(
            current.get("wind_gusts_10m")
        ),

        daily_min_temperature_c=_safe_float(
            _list_value(daily.get("temperature_2m_min"))
        ),
        daily_max_temperature_c=_safe_float(
            _list_value(daily.get("temperature_2m_max"))
        ),
        daily_max_precipitation_probability_percent=_safe_float(
            _list_value(
                daily.get("precipitation_probability_max")
            )
        ),
        daily_precipitation_sum_mm=_safe_float(
            _list_value(daily.get("precipitation_sum"))
        ),
        daily_max_wind_speed_kmh=_safe_float(
            _list_value(daily.get("wind_speed_10m_max"))
        ),
        daily_max_wind_gusts_kmh=_safe_float(
            _list_value(daily.get("wind_gusts_10m_max"))
        ),
        daily_max_uv_index=_safe_float(
            _list_value(daily.get("uv_index_max"))
        ),
        sunrise=_list_value(daily.get("sunrise")),
        sunset=_list_value(daily.get("sunset")),

        hourly=_build_hourly_forecast(hourly),
    )