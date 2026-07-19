from integrations.weather import fetch_weather
from weather_intelligence import build_weather_intelligence


weather = fetch_weather()

print("=" * 60)
print("RAW WEATHER")
print("=" * 60)
print(weather)

for environment in ["Indoor", "Outdoor", "Not sure"]:

    intelligence = build_weather_intelligence(
        weather,
        training_environment=environment,
        activity_type="Cycling",
    )

    print("\n")
    print("=" * 60)
    print(environment.upper())
    print("=" * 60)

    print("Summary:")
    print(intelligence.summary)

    print("\nRecommendation:")
    print(intelligence.recommendation)

    print("\nSuitability:", intelligence.outdoor_suitability)
    print("Best window:", intelligence.best_window)

    print("\nRisks")
    print("Heat:", intelligence.heat_risk)
    print("Rain:", intelligence.rain_risk)
    print("Wind:", intelligence.wind_risk)
    print("UV:", intelligence.uv_risk)

    print("\nHydration:")
    print(intelligence.hydration_guidance)

    print("\nCooling:")
    print(intelligence.cooling_guidance)

    print("\nClothing:")
    print(intelligence.clothing_guidance)

    print("\nWarnings:")
    for warning in intelligence.warnings:
        print("-", warning)

    print("\nReasons:")
    for reason in intelligence.reasons:
        print("-", reason)

    print("\nConfidence:", intelligence.confidence)