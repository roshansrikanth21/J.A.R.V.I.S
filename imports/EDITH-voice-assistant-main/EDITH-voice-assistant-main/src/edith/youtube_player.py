# edith_modules/youtube_player.py

import pywhatkit as kit
from text_to_speech import speak_offline


def play_youtube_video(query: str):
    try:
        speak_offline(f"Playing {query} on YouTube.")
        print(f"🔍 Searching and playing: {query}")
        kit.playonyt(query)
    except Exception as e:
        speak_offline("Unable to play the video right now.")
        print(f"❌ YouTube Error: {e}")
