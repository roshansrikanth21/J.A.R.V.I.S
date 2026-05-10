import smtplib
import ssl
from email.message import EmailMessage
from edith_modules.text_to_speech import speak_offline  # ✅ Corrected import


def send_email(receiver_email, subject, body):
    try:
        sender_email = "your_email@example.com"  # Replace with actual email
        sender_password = "your_app_password"    # Use App Password for Gmail

        message = EmailMessage()
        message["From"] = sender_email
        message["To"] = receiver_email
        message["Subject"] = subject
        message.set_content(body)

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(sender_email, sender_password)
            server.send_message(message)

        print("✅ Email sent successfully.")
        speak_offline("Email sent successfully.")

    except Exception as e:
        print(f"❌ Error: {e}")
        speak_offline("Failed to send the email.")