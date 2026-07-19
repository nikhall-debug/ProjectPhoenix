from datetime import datetime
from typing import Iterable, List, Optional

from weather_models import (
    HourlyWeather,
    WeatherIntelligence,
    WeatherSnapshot,
)


def _normalise_environment(value: Optional[str]) -> str:
    """
    Normalises the selected training environment.

    Phoenix assumes indoor cycling unless the user explicitly selects
    Outdoor or Not sure.
    """

    if not value:
        return "Indoor"

    normalised = str(value).strip().lower()

    if normalised == "outdoor":
        return "Outdoor"

    if normalised in {
        "not sure",
        "unsure",
        "either",
        "unknown",
    }:
        return "Not sure"

    return "Indoor"


def _heat_risk(
    temperature_c: Optional[float],
    apparent_temperature_c: Optional[float],
    humidity_percent: Optional[float],
) -> str:
    """
    Estimates heat-related training risk.

    The supplied temperature, apparent temperature, and humidity should
    represent the same forecast hour wherever possible.
    """

    temperatures = [
        value
        for value in (
            temperature_c,
            apparent_temperature_c,
        )
        if value is not None
    ]

    if not temperatures:
        return "Unknown"

    effective_temperature = max(temperatures)

    if effective_temperature >= 32:
        return "High"

    if effective_temperature >= 27:
        if (
            humidity_percent is not None
            and humidity_percent >= 70
        ):
            return "High"

        return "Moderate"

    if effective_temperature >= 22:
        return "Low"

    return "Minimal"


def _rain_risk(
    probability_percent: Optional[float],
    precipitation_mm: Optional[float],
) -> str:
    """
    Estimates rain risk from precipitation probability and amount.
    """

    probability = probability_percent or 0.0
    precipitation = precipitation_mm or 0.0

    if probability >= 70 or precipitation >= 5:
        return "High"

    if probability >= 40 or precipitation >= 2:
        return "Moderate"

    if probability >= 20 or precipitation > 0:
        return "Low"

    return "Minimal"


def _wind_risk(
    wind_speed_kmh: Optional[float],
    wind_gusts_kmh: Optional[float],
) -> str:
    """
    Estimates cycling wind risk from sustained wind and gusts.
    """

    wind = wind_speed_kmh or 0.0
    gusts = wind_gusts_kmh or 0.0

    if wind >= 35 or gusts >= 55:
        return "High"

    if wind >= 25 or gusts >= 40:
        return "Moderate"

    if wind >= 15 or gusts >= 28:
        return "Low"

    return "Minimal"


def _uv_risk(uv_index: Optional[float]) -> str:
    """
    Converts UV index into a simple Phoenix risk level.
    """

    if uv_index is None:
        return "Unknown"

    if uv_index >= 8:
        return "High"

    if uv_index >= 6:
        return "Moderate"

    if uv_index >= 3:
        return "Low"

    return "Minimal"


def _parse_datetime(
    time_value: Optional[str],
) -> Optional[datetime]:
    """
    Parses an Open-Meteo local ISO datetime.
    """

    if not time_value:
        return None

    try:
        return datetime.fromisoformat(time_value)

    except (TypeError, ValueError):
        return None


def _parse_hour(time_value: Optional[str]) -> Optional[int]:
    parsed = _parse_datetime(time_value)

    if parsed is None:
        return None

    return parsed.hour


def _today_hours(
    snapshot: WeatherSnapshot,
) -> List[HourlyWeather]:
    """
    Returns forecast points for the snapshot's current local date.

    Open-Meteo returns local timestamps because Phoenix supplies the
    Europe/Berlin timezone in the API request.
    """

    if not snapshot.hourly:
        return []

    current_datetime = _parse_datetime(snapshot.current_time)

    if current_datetime is not None:
        current_date = current_datetime.date()
    else:
        current_date = datetime.now().date()

    result: List[HourlyWeather] = []

    for item in snapshot.hourly:
        item_datetime = _parse_datetime(item.time)

        if item_datetime is None:
            continue

        if item_datetime.date() == current_date:
            result.append(item)

    return result


def _remaining_today_hours(
    snapshot: WeatherSnapshot,
) -> List[HourlyWeather]:
    """
    Returns only forecast hours at or after the snapshot's current time.

    This prevents Phoenix from recommending a riding window that has
    already passed.
    """

    today_hours = _today_hours(snapshot)
    current_datetime = _parse_datetime(snapshot.current_time)

    if current_datetime is None:
        return today_hours

    result: List[HourlyWeather] = []

    for item in today_hours:
        item_datetime = _parse_datetime(item.time)

        if item_datetime is None:
            continue

        if item_datetime >= current_datetime:
            result.append(item)

    return result


def _thunderstorm_hours(
    hours: Iterable[HourlyWeather],
) -> List[int]:
    """
    Returns hours containing an Open-Meteo thunderstorm code.

    Open-Meteo weather codes:
        95 = thunderstorm
        96 = thunderstorm with slight hail
        99 = thunderstorm with heavy hail
    """

    thunderstorm_codes = {95, 96, 99}
    result: List[int] = []

    for item in hours:
        if item.weather_code not in thunderstorm_codes:
            continue

        hour = _parse_hour(item.time)

        if hour is not None:
            result.append(hour)

    return sorted(set(result))


def _hour_heat_risk(item: HourlyWeather) -> str:
    """
    Calculates heat risk using values from one matching forecast hour.
    """

    return _heat_risk(
        item.temperature_c,
        item.apparent_temperature_c,
        item.humidity_percent,
    )


def _hour_rain_risk(item: HourlyWeather) -> str:
    return _rain_risk(
        item.precipitation_probability_percent,
        item.precipitation_mm,
    )


def _hour_wind_risk(item: HourlyWeather) -> str:
    return _wind_risk(
        item.wind_speed_kmh,
        item.wind_gusts_kmh,
    )


def _hour_is_thunderstorm(item: HourlyWeather) -> bool:
    return item.weather_code in {95, 96, 99}


def _hour_score(item: HourlyWeather) -> float:
    """
    Produces a transparent outdoor-cycling suitability score.

    Lower scores represent better riding conditions.
    """

    score = 0.0

    temperature = item.apparent_temperature_c

    if temperature is None:
        temperature = item.temperature_c

    if temperature is not None:
        if temperature < 5:
            score += 5
        elif temperature < 10:
            score += 2
        elif temperature <= 22:
            score += 0
        elif temperature <= 27:
            score += 1
        elif temperature <= 31:
            score += 3
        else:
            score += 6

    rain_probability = (
        item.precipitation_probability_percent or 0.0
    )
    precipitation = item.precipitation_mm or 0.0

    score += rain_probability / 20
    score += precipitation * 2

    wind = item.wind_speed_kmh or 0.0
    gusts = item.wind_gusts_kmh or 0.0

    if wind >= 35:
        score += 7
    elif wind >= 25:
        score += 4
    elif wind >= 15:
        score += 1

    if gusts >= 55:
        score += 8
    elif gusts >= 40:
        score += 5
    elif gusts >= 28:
        score += 2

    uv_index = item.uv_index or 0.0

    if uv_index >= 8:
        score += 2
    elif uv_index >= 6:
        score += 1

    # Thunderstorms should effectively disqualify an hour.
    if _hour_is_thunderstorm(item):
        score += 100

    return score


def _find_best_window(
    hours: Iterable[HourlyWeather],
    earliest_hour: int = 7,
    latest_hour: int = 20,
    window_length: int = 3,
) -> Optional[str]:
    """
    Finds the best continuous outdoor cycling window.

    Thunderstorm hours are excluded. The first Phoenix version uses a
    simple and explainable scoring system rather than an opaque model.
    """

    candidates: List[HourlyWeather] = []

    for item in hours:
        hour = _parse_hour(item.time)

        if hour is None:
            continue

        if hour < earliest_hour or hour > latest_hour:
            continue

        if _hour_is_thunderstorm(item):
            continue

        candidates.append(item)

    if not candidates:
        return None

    if len(candidates) < window_length:
        best_item = min(candidates, key=_hour_score)
        best_hour = _parse_hour(best_item.time)

        if best_hour is None:
            return None

        end_hour = min(best_hour + 1, 24)

        return (
            f"{best_hour:02d}:00–"
            f"{end_hour:02d}:00"
        )

    best_start: Optional[int] = None
    best_score: Optional[float] = None

    for start_index in range(
        0,
        len(candidates) - window_length + 1,
    ):
        window = candidates[
            start_index:start_index + window_length
        ]

        parsed_hours = [
            _parse_hour(item.time)
            for item in window
        ]

        if any(hour is None for hour in parsed_hours):
            continue

        numeric_hours = [
            int(hour)
            for hour in parsed_hours
            if hour is not None
        ]

        if len(numeric_hours) != window_length:
            continue

        # Reject windows that skip an hour because of missing data or a
        # thunderstorm forecast point.
        if any(
            numeric_hours[index + 1]
            - numeric_hours[index]
            != 1
            for index in range(
                len(numeric_hours) - 1
            )
        ):
            continue

        score = sum(
            _hour_score(item)
            for item in window
        )

        if best_score is None or score < best_score:
            best_score = score
            best_start = numeric_hours[0]

    if best_start is None:
        return None

    end_hour = min(
        best_start + window_length,
        24,
    )

    return (
        f"{best_start:02d}:00–"
        f"{end_hour:02d}:00"
    )


def _worst_risk(
    risks: Iterable[str],
) -> str:
    """
    Returns the highest Phoenix risk level present.
    """

    order = {
        "Unknown": -1,
        "Minimal": 0,
        "Low": 1,
        "Moderate": 2,
        "High": 3,
    }

    risk_list = list(risks)

    if not risk_list:
        return "Unknown"

    return max(
        risk_list,
        key=lambda value: order.get(value, -1),
    )


def _forecast_period_risks(
    hours: Iterable[HourlyWeather],
) -> tuple[str, str, str, str]:
    """
    Calculates risks using matching hourly forecast values.

    This prevents Phoenix from combining, for example, afternoon maximum
    temperature with early-morning humidity.
    """

    hour_list = list(hours)

    if not hour_list:
        return (
            "Unknown",
            "Unknown",
            "Unknown",
            "Unknown",
        )

    heat_risk = _worst_risk(
        _hour_heat_risk(item)
        for item in hour_list
    )

    rain_risk = _worst_risk(
        _hour_rain_risk(item)
        for item in hour_list
    )

    wind_risk = _worst_risk(
        _hour_wind_risk(item)
        for item in hour_list
    )

    uv_risk = _worst_risk(
        _uv_risk(item.uv_index)
        for item in hour_list
    )

    return (
        heat_risk,
        rain_risk,
        wind_risk,
        uv_risk,
    )


def _outdoor_suitability(
    heat_risk: str,
    rain_risk: str,
    wind_risk: str,
    thunderstorm_hours: Iterable[int],
) -> str:
    """
    Converts forecast risks into an overall outdoor-cycling rating.
    """

    if list(thunderstorm_hours):
        return "Limited"

    risks = {
        heat_risk,
        rain_risk,
        wind_risk,
    }

    if "High" in risks:
        return "Poor"

    moderate_count = sum(
        risk == "Moderate"
        for risk in risks
    )

    if moderate_count >= 2:
        return "Limited"

    if moderate_count == 1:
        return "Fair"

    low_count = sum(
        risk == "Low"
        for risk in risks
    )

    if low_count >= 2:
        return "Good"

    return "Excellent"


def _hydration_guidance(
    heat_risk: str,
    environment: str,
) -> str:
    if heat_risk == "High":
        return (
            "Begin well hydrated and plan regular fluids. "
            "For a longer ride, include electrolytes."
        )

    if heat_risk == "Moderate":
        return (
            "Take fluids from the start and consider electrolytes "
            "for rides longer than about an hour."
        )

    if environment == "Indoor":
        return (
            "Keep a bottle within reach. Indoor riding can produce "
            "more sweat than the outdoor temperature suggests."
        )

    return "Normal ride hydration should be sufficient."


def _cooling_guidance(
    heat_risk: str,
    environment: str,
) -> str:
    if environment == "Indoor":
        if heat_risk in {
            "High",
            "Moderate",
        }:
            return (
                "Use strong airflow, ideally two fans, and avoid "
                "allowing the room to become warm and stagnant."
            )

        return (
            "Use a fan from the start rather than waiting until "
            "you feel hot."
        )

    if heat_risk == "High":
        return (
            "Ride early or move the session indoors. Reduce intensity "
            "if heat strain rises."
        )

    if heat_risk == "Moderate":
        return (
            "Prefer the cooler part of the day and use a lighter jersey."
        )

    return "No special cooling measures appear necessary."


def _clothing_guidance(
    min_temperature_c: Optional[float],
    max_temperature_c: Optional[float],
    rain_risk: str,
) -> str:
    reference_temperature = max_temperature_c

    if reference_temperature is None:
        reference_temperature = min_temperature_c

    if reference_temperature is None:
        return "Use clothing appropriate to how conditions feel."

    if reference_temperature < 8:
        clothing = (
            "Cold-weather cycling layers are advisable."
        )

    elif reference_temperature < 13:
        clothing = (
            "Use a light jacket or gilet, with arm warmers "
            "if needed."
        )

    elif reference_temperature < 18:
        clothing = (
            "A short-sleeve jersey with a packable gilet "
            "should work."
        )

    elif reference_temperature < 26:
        clothing = (
            "Normal summer cycling clothing should be suitable."
        )

    else:
        clothing = (
            "Use light, breathable clothing and prioritise cooling."
        )

    if rain_risk in {
        "Moderate",
        "High",
    }:
        clothing += " Carry a light rain layer."

    return clothing


def _unavailable_intelligence(
    snapshot: Optional[WeatherSnapshot],
    environment: str,
    weather_relevant: bool,
) -> WeatherIntelligence:
    """
    Returns a safe result when the weather service cannot be used.
    """

    error_message = None

    if snapshot is not None:
        error_message = snapshot.error

    warnings = [
        "Weather information is currently unavailable."
    ]

    if error_message:
        warnings.append(error_message)

    return WeatherIntelligence(
        status="Unavailable",
        training_environment=environment,
        outdoor_suitability="Unknown",
        heat_risk="Unknown",
        rain_risk="Unknown",
        wind_risk="Unknown",
        uv_risk="Unknown",
        best_window=None,
        hydration_guidance=(
            "Use your normal hydration plan and adjust to the "
            "conditions you experience."
        ),
        cooling_guidance=(
            "Use a fan for indoor riding and adjust airflow as needed."
        ),
        clothing_guidance=(
            "Check local conditions before an outdoor session."
        ),
        summary=(
            "Phoenix could not retrieve weather information, but "
            "the rest of the training advice remains available."
        ),
        recommendation=(
            "Proceed using your health and recovery recommendation. "
            "Check the weather separately if riding outdoors."
        ),
        reasons=[],
        warnings=warnings,
        confidence=0,
        weather_relevant=weather_relevant,
        source_available=False,
    )


def build_weather_intelligence(
    snapshot: Optional[WeatherSnapshot],
    training_environment: str = "Indoor",
    activity_type: str = "Cycling",
) -> WeatherIntelligence:
    """
    Interprets weather for today's planned activity.

    Weather influences how a workout should be performed. It must not
    override health, recovery, medical, or safety constraints.
    """

    environment = _normalise_environment(
        training_environment
    )

    activity = str(
        activity_type or ""
    ).strip().lower()

    weather_relevant = (
        activity == "cycling"
        and environment in {
            "Outdoor",
            "Not sure",
        }
    )

    if (
        snapshot is None
        or snapshot.status != "Available"
    ):
        return _unavailable_intelligence(
            snapshot,
            environment,
            weather_relevant,
        )

    today_hours = _today_hours(snapshot)
    remaining_hours = _remaining_today_hours(snapshot)

    # Prefer the remaining forecast so Phoenix does not base advice on
    # weather that has already passed.
    assessment_hours = (
        remaining_hours
        or today_hours
    )

    (
        heat_risk,
        rain_risk,
        wind_risk,
        uv_risk,
    ) = _forecast_period_risks(
        assessment_hours
    )

    thunderstorm_hours = _thunderstorm_hours(
        assessment_hours
    )

    suitability = _outdoor_suitability(
        heat_risk,
        rain_risk,
        wind_risk,
        thunderstorm_hours,
    )

    best_window = _find_best_window(
        assessment_hours
    )

    reasons: List[str] = []
    warnings: List[str] = []

    if snapshot.current_temperature_c is not None:
        reasons.append(
            "The current temperature is approximately "
            f"{snapshot.current_temperature_c:.0f} °C."
        )

    if snapshot.daily_min_temperature_c is not None:
        reasons.append(
            "Today’s minimum is approximately "
            f"{snapshot.daily_min_temperature_c:.0f} °C."
        )

    if snapshot.daily_max_temperature_c is not None:
        reasons.append(
            "Today’s maximum is approximately "
            f"{snapshot.daily_max_temperature_c:.0f} °C."
        )

    if (
        snapshot
        .daily_max_precipitation_probability_percent
        is not None
    ):
        reasons.append(
            "Maximum rain probability is approximately "
            f"{snapshot.daily_max_precipitation_probability_percent:.0f}%."
        )

    if snapshot.daily_max_wind_gusts_kmh is not None:
        reasons.append(
            "Maximum forecast gusts are approximately "
            f"{snapshot.daily_max_wind_gusts_kmh:.0f} km/h."
        )

    if best_window:
        reasons.append(
            "The best remaining outdoor window is approximately "
            f"{best_window}."
        )

    if heat_risk == "High":
        warnings.append(
            "Heat may meaningfully increase physiological strain."
        )

    elif heat_risk == "Moderate":
        warnings.append(
            "Warm conditions may increase hydration and cooling needs."
        )

    if rain_risk == "High":
        warnings.append(
            "Rain may make an outdoor ride uncomfortable or unsafe."
        )

    elif rain_risk == "Moderate":
        warnings.append(
            "There is a meaningful chance of rain during the "
            "remaining forecast period."
        )

    if wind_risk == "High":
        warnings.append(
            "Strong winds or gusts may affect bike handling."
        )

    elif wind_risk == "Moderate":
        warnings.append(
            "Wind or gusts may influence route choice and effort."
        )

    if uv_risk == "High":
        warnings.append(
            "UV exposure is high; use sun protection."
        )

    elif uv_risk == "Moderate":
        warnings.append(
            "UV exposure is elevated; sun protection is advisable."
        )

    if thunderstorm_hours:
        formatted_hours = ", ".join(
            f"{hour:02d}:00"
            for hour in thunderstorm_hours
        )

        warnings.append(
            "Thunderstorms are forecast around "
            f"{formatted_hours}; avoid outdoor riding near those times."
        )

        reasons.append(
            "The hourly forecast includes a possible thunderstorm "
            f"around {formatted_hours}."
        )

    hydration = _hydration_guidance(
        heat_risk,
        environment,
    )

    cooling = _cooling_guidance(
        heat_risk,
        environment,
    )

    clothing = _clothing_guidance(
        snapshot.daily_min_temperature_c,
        snapshot.daily_max_temperature_c,
        rain_risk,
    )

    if activity != "cycling":
        summary = (
            "Weather is available, but it is not currently a major "
            "factor in today’s selected activity."
        )

        recommendation = (
            "Use the normal Phoenix health and recovery advice."
        )

        weather_relevant = False

    elif environment == "Indoor":
        summary = (
            "You are planning to train indoors, so outdoor weather "
            "will not determine the workout."
        )

        if heat_risk in {
            "High",
            "Moderate",
        }:
            recommendation = (
                "Complete the planned indoor workout, but prioritise "
                "airflow, cooling and hydration."
            )

        else:
            recommendation = (
                "Complete the planned indoor workout and use a fan "
                "from the beginning."
            )

        weather_relevant = False

    elif environment == "Outdoor":
        weather_relevant = True

        if suitability == "Excellent":
            summary = (
                "Conditions look excellent for outdoor cycling today."
            )

        elif suitability == "Good":
            summary = (
                "Conditions look good for outdoor cycling, with only "
                "minor weather considerations."
            )

        elif suitability == "Fair":
            summary = (
                "Outdoor cycling is reasonable, but conditions should "
                "influence timing or route choice."
            )

        elif suitability == "Limited":
            summary = (
                "Outdoor cycling may be possible, but conditions are "
                "not consistently suitable."
            )

        else:
            summary = (
                "Conditions look poor for outdoor cycling during the "
                "remaining forecast period."
            )

        if suitability in {
            "Excellent",
            "Good",
        }:
            recommendation = (
                "An outdoor ride is weather-compatible today."
            )

            if best_window:
                recommendation += (
                    " The best remaining forecast window is "
                    f"around {best_window}."
                )

        elif suitability == "Fair":
            recommendation = (
                "Outdoor riding remains possible, but use the best "
                "weather window and choose the route carefully."
            )

            if best_window:
                recommendation += (
                    f" Aim for around {best_window}."
                )

        elif suitability == "Limited":
            recommendation = (
                "Consider training indoors unless you can ride within "
                "the better forecast window and avoid the main hazards."
            )

            if best_window:
                recommendation += (
                    " The best remaining option appears to be "
                    f"{best_window}."
                )

        else:
            recommendation = (
                "Move the session indoors or substantially change the "
                "outdoor route, timing or intensity."
            )

            if best_window:
                recommendation += (
                    " If riding outside, the least difficult remaining "
                    f"window appears to be {best_window}."
                )

    else:
        # "Not sure"
        weather_relevant = True

        if suitability in {
            "Excellent",
            "Good",
        }:
            summary = (
                "Outdoor conditions are favourable, although your "
                "usual indoor option remains available."
            )

            recommendation = (
                "Either environment is suitable. Phoenix can recommend "
                "outdoors today if you would enjoy the conditions."
            )

            if best_window:
                recommendation += (
                    " The best remaining outdoor window is "
                    f"{best_window}."
                )

        elif suitability == "Fair":
            summary = (
                "Both indoor and outdoor training remain possible, "
                "but outdoor timing matters."
            )

            recommendation = (
                "Choose outdoors only if the better weather window "
                "fits your day; otherwise train indoors."
            )

            if best_window:
                recommendation += (
                    f" The better outdoor window is {best_window}."
                )

        else:
            summary = (
                "Indoor training appears more predictable than outdoor "
                "cycling today."
            )

            recommendation = (
                "Choose indoors unless you particularly want an outdoor "
                "ride and can adapt the timing or route."
            )

            if best_window:
                recommendation += (
                    " The least difficult outdoor window appears to "
                    f"be {best_window}."
                )

    available_signal_count = sum(
        value is not None
        for value in (
            snapshot.current_temperature_c,
            snapshot.current_apparent_temperature_c,
            snapshot.current_humidity_percent,
            snapshot.daily_min_temperature_c,
            snapshot.daily_max_temperature_c,
            snapshot.daily_max_precipitation_probability_percent,
            snapshot.daily_max_wind_speed_kmh,
            snapshot.daily_max_wind_gusts_kmh,
            snapshot.daily_max_uv_index,
        )
    )

    confidence = min(
        100,
        30 + available_signal_count * 7,
    )

    if not assessment_hours:
        confidence = min(
            confidence,
            50,
        )

    return WeatherIntelligence(
        status="Available",
        training_environment=environment,
        outdoor_suitability=suitability,
        heat_risk=heat_risk,
        rain_risk=rain_risk,
        wind_risk=wind_risk,
        uv_risk=uv_risk,
        best_window=best_window,
        hydration_guidance=hydration,
        cooling_guidance=cooling,
        clothing_guidance=clothing,
        summary=summary,
        recommendation=recommendation,
        reasons=reasons,
        warnings=warnings,
        confidence=confidence,
        weather_relevant=weather_relevant,
        source_available=True,
    )