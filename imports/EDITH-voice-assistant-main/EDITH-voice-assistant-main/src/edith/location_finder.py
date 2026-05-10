# edith_modules/location_finder.py

from edith_modules.text_to_speech import speak_offline  # ✅ Corrected import
import geocoder


def get_location():
    try:
        location = geocoder.ip('me')
        if location.ok:
            city = location.city or "Unknown city"
            state = location.state or "Unknown state"
            country = location.country or "Unknown country"
            location_str = f"You are in {city}, {state}, {country}."
            speak_offline(location_str)
            return location_str
        else:
            error_msg = "Could not determine your location."
            speak_offline(error_msg)
            return error_msg

    except Exception as e:
        error_msg = f"An error occurred while retrieving your location: {e}"
        speak_offline(error_msg)
        return error_msg
