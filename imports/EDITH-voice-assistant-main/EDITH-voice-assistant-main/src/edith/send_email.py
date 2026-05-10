# edith_modules/send_email.py

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from .text_to_speech import speak_offline  # ✅ Correct relative import


def send_email(recipient, subject, body):
    try:
        sender_email = "ranjithguggilla668@gmail.com"
        # ⚠️ Consider using environment variable or secrets manager
        sender_password = "404galtinotfound"

        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = recipient
        message["Subject"] = subject

        message.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient, message.as_string())
        server.quit()

        speak_offline("Email sent successfully.")
    except Exception as e:
        speak_offline("Failed to send the email.")
        print(f"Error: {e}")
