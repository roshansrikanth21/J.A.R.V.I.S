# edith_modules/translator.py

from deep_translator import GoogleTranslator
from text_to_speech import speak_offline


def translate_text(text: str, target_lang: str = 'te') -> str:
    """
    Translates the given text to the target language using GoogleTranslator from deep-translator.
    Default target language is Telugu ('te').

    Args:
        text (str): Text to translate.
        target_lang (str): Language code to translate to.

    Returns:
        str: Translated text.
    """
    try:
        translated = GoogleTranslator(
            source='auto', target=target_lang).translate(text)
        print(f"🔤 Translated Text: {translated}")
        speak_offline(f"The translated text is: {translated}")
        return translated
    except Exception as e:
        print(f"❌ Translation error: {e}")
        speak_offline("Sorry, I couldn't translate that.")
        return "Translation failed"
