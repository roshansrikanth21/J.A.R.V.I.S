import os
import datetime
import requests
import platform
import subprocess
try:
    import pywhatkit
except ImportError:
    pass

class GitHubTools:
    def __init__(self, voice_system=None):
        self.voice = voice_system
        self.news_api_key = "695fe037cec349668377d018eca858a3" # Extracted from github repo

    def play_youtube(self, query):
        """Plays a youtube video based on a search query using pywhatkit."""
        try:
            if self.voice:
                self.voice.speak(f"Playing {query} on YouTube.")
            pywhatkit.playonyt(query)
            return f"Successfully opened YouTube to play: {query}"
        except Exception as e:
            return f"YouTube Error: {e}"

    def send_whatsapp(self, phone_number, message):
        """Schedules a whatsapp message 2 minutes from now."""
        try:
            now = datetime.datetime.now()
            hour = now.hour
            minute = now.minute + 2
            if minute >= 60:
                hour = (hour + 1) % 24
                minute %= 60

            if self.voice:
                self.voice.speak(f"Scheduling WhatsApp message to {phone_number} at {hour}:{minute:02d}.")
            
            pywhatkit.sendwhatmsg(phone_number, message, hour, minute)
            return f"Message scheduled to {phone_number}."
        except Exception as e:
            return f"WhatsApp Send Error: {e}"

    def get_news(self):
        """Fetches top 5 US news headlines."""
        try:
            url = f"https://newsapi.org/v2/top-headlines?country=us&apiKey={self.news_api_key}"
            response = requests.get(url)
            data = response.json()

            if data.get("status") == "ok":
                articles = data["articles"][:5]
                news_texts = [f"{i+1}. {article['title']}" for i, article in enumerate(articles)]
                combined_news = "\n".join(news_texts)
                return f"Top 5 News Headlines:\n{combined_news}"
            else:
                return "Failed to fetch news from the API."
        except Exception as e:
            return f"News fetch error: {e}"

    def control_system(self, action):
        """Restarts, Logs out, or Sleeps the system."""
        system_platform = platform.system()
        action = action.lower()
        
        try:
            if system_platform == "Windows":
                if action == "restart":
                    os.system("shutdown /r /t 1")
                elif action == "logout":
                    os.system("shutdown -l")
                elif action == "shutdown":
                    os.system("shutdown /s /t 1")
                else:
                    return f"Unknown system action: {action}"
                return f"Executing system {action}..."
            else:
                return "System control tools only fully configured for Windows in this implementation."
        except Exception as e:
            return f"System control error: {e}"
