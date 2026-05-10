# edith_modules/password_generator.py

from .text_to_speech import speak_offline  # ✅ Correct relative import
import random
import string


def generate_password(length=12):
    try:
        characters = string.ascii_letters + string.digits + string.punctuation
        password = ''.join(random.choice(characters) for _ in range(length))
        speak_offline(f"Your generated password is {password}")
        return password
    except Exception as e:
        speak_offline("Failed to generate password.")
        return f"Error: {e}"
