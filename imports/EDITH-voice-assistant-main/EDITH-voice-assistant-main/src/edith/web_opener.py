# edith_modules/web_opener.py

import webbrowser
from text_to_speech import speak_offline

# Predefined websites (add more if needed)
COMMON_SITES = {
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "linkedin": "https://www.linkedin.com",
    "github": "https://github.com",
    "gmail": "https://mail.google.com",
    "twitter": "https://twitter.com",
    "stackoverflow": "https://stackoverflow.com"
}


def open_website(command: str):
    try:
        for site in COMMON_SITES:
            if site in command:
                speak_offline(f"Opening {site}")
                webbrowser.open(COMMON_SITES[site])
                return

        # If not predefined, treat it as a general URL search
        query = command.replace("open", "").strip()
        url = f"https://{query}.com"
        speak_offline(f"Trying to open {query}")
        webbrowser.open(url)

    except Exception as e:
        speak_offline("I couldn't open that website.")
        print(f"❌ Website Open Error: {e}")
