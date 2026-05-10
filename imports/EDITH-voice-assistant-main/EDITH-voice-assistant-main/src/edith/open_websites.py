# edith_modules/open_websites.py

import webbrowser
# ✅ Add this line for voice feedback
from edith_modules.text_to_speech import speak_offline

# Define a dictionary of voice commands and URLs
website_map = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "stackoverflow": "https://stackoverflow.com",
    "linkedin": "https://www.linkedin.com",
    "github": "https://www.github.com"
}


def open_website(command: str):
    for keyword, url in website_map.items():
        if keyword in command.lower():
            speak_offline(f"Opening {keyword}")
            webbrowser.open(url)
            return True
    speak_offline("Website not recognized.")
    return False
