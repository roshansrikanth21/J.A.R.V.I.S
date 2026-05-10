# edith_modules/weather.py

import requests
from text_to_speech import speak_offline


def get_weather(city_name: str, api_key: str):
    try:
        base_url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            'q': city_name,
            'appid': api_key,
            'units': 'metric'
        }

        response = requests.get(base_url, params=params)
        data = response.json()

        if data.get("cod") != 200:
            speak_offline(
                "Sorry, I couldn't find the weather for that location.")
            return

        weather = data["weather"][0]["description"]
        temp = data["main"]["temp"]
        humidity = data["main"]["humidity"]
        wind_speed = data["wind"]["speed"]

        forecast = (
            f"Weather in {city_name.title()} is {weather}. "
            f"Temperature: {temp}°C. Humidity: {humidity}%. "
            f"Wind Speed: {wind_speed} meters per second."
        )

        print(f"🌤️ {forecast}")
        speak_offline(forecast)

    except Exception as e:
        speak_offline("Something went wrong while fetching the weather.")
        print(f"❌ Error: {e}")
