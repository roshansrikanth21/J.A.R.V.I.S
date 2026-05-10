# edith_modules/voice_recognition.py

import speech_recognition as sr


def recognize_speech_from_mic():
    recognizer = sr.Recognizer()
    microphone = sr.Microphone()

    try:
        with microphone as source:
            print("🎙️ Listening...")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.listen(source, timeout=5)

        print("🧠 Recognizing...")
        command = recognizer.recognize_google(audio)
        return command.lower()

    except sr.WaitTimeoutError:
        print("⌛ Listening timed out.")
    except sr.UnknownValueError:
        print("🧩 Sorry, I didn’t understand that.")
    except sr.RequestError:
        print("🚫 Could not request results from Google Speech API.")

    return None
