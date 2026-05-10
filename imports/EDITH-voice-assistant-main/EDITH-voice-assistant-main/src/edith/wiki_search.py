# edith_modules/wiki_search.py

import wikipedia
from text_to_speech import speak_offline


def search_wikipedia(command: str):
    try:
        if "wikipedia" in command:
            topic = command.replace("wikipedia", "").strip()
            speak_offline(f"Searching Wikipedia for {topic}")
            summary = wikipedia.summary(topic, sentences=2)
            print(f"📚 Wikipedia Summary:\n{summary}")
            speak_offline(summary)
            return summary
    except wikipedia.DisambiguationError as e:
        speak_offline("Topic is too broad, please be more specific.")
        print(f"Disambiguation Error: {e.options}")
    except wikipedia.exceptions.PageError:
        speak_offline("I couldn't find anything on that topic.")
    except Exception as ex:
        speak_offline("Something went wrong while searching.")
        print(f"❌ Error: {ex}")
    return None
