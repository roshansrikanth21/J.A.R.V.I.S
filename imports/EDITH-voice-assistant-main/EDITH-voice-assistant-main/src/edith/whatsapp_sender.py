# edith_modules/whatsapp_sender.py

import pywhatkit
import datetime
from text_to_speech import speak_offline


def send_whatsapp_message(phone_number, message):
    try:
        now = datetime.datetime.now()
        hour = now.hour
        minute = now.minute + 2  # Send after 2 minutes from current time

        if minute >= 60:
            hour += 1
            minute %= 60

        pywhatkit.sendwhatmsg(phone_number, message, hour, minute)
        speak_offline(f"Message scheduled to {phone_number}")
    except Exception as e:
        speak_offline("I couldn't send the WhatsApp message.")
        print(f"❌ WhatsApp Send Error: {e}")
