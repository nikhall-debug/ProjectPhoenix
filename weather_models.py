from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class HourlyWeather:
    """
    One hourly weather forecast point.
    """

    time: str
    temperature_c: Optional[float] = None
    apparent_temperature_c: Optional[float] = None
    humidity_percent: Optional[float] = None
    precipitation_probability_percent: Optional[float] = None
    precipitation_mm: Optional[float] = None
    weather_code: Optional[int] = None
    wind_speed_kmh: Optional[float] = None
    wind_gusts_kmh: Optional[float] = None
    uv_index: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class WeatherSnapshot:
    """
    Normalised weather data returned by the Open-Meteo integration.
    """

    status: str
    location_name: str
    latitude: float
    longitude: float
    timezone: str
    fetched_at: str

    current_time: Optional[str] = None
    current_temperature_c: Optional[float] = None
    current_apparent_temperature_c: Optional[float] = None
    current_humidity_percent: Optional[float] = None
    current_precipitation_mm: Optional[float] = None
    current_weather_code: Optional[int] = None
    current_wind_speed_kmh: Optional[float] = None
    current_wind_gusts_kmh: Optional[float] = None

    daily_min_temperature_c: Optional[float] = None
    daily_max_temperature_c: Optional[float] = None
    daily_max_precipitation_probability_percent: Optional[float] = None
    daily_precipitation_sum_mm: Optional[float] = None
    daily_max_wind_speed_kmh: Optional[float] = None
    daily_max_wind_gusts_kmh: Optional[float] = None
    daily_max_uv_index: Optional[float] = None
    sunrise: Optional[str] = None
    sunset: Optional[str] = None

    hourly: List[HourlyWeather] = field(default_factory=list)

    source: str = "Open-Meteo"
    source_url: str = "https://open-meteo.com/"
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["hourly"] = [item.to_dict() for item in self.hourly]
        return result


@dataclass
class WeatherIntelligence:
    """
    Phoenix interpretation of weather in relation to planned training.
    """

    status: str
    training_environment: str
    outdoor_suitability: str

    heat_risk: str
    rain_risk: str
    wind_risk: str
    uv_risk: str

    best_window: Optional[str]
    hydration_guidance: str
    cooling_guidance: str
    clothing_guidance: str

    summary: str
    recommendation: str
    reasons: List[str]
    warnings: List[str]

    confidence: int
    weather_relevant: bool
    source_available: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)