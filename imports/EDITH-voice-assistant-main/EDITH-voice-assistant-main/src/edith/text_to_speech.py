# edith_modules/text_to_speech.py

import pyttsx3


def speak_offline(text: str) -> None:
    """
    Converts the given text to speech using the pyttsx3 library.
    This works offline.
    """
    try:
        engine = pyttsx3.init()
        engine.setProperty('rate', 175)      # Speed of speech
        engine.setProperty('volume', 1.0)    # Volume level (0.0 to 1.0)
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        print(f"[TTS ERROR] {e}")
