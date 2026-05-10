# edith_modules/news.py

import requests
from edith_modules.text_to_speech import speak_offline  # ✅ Corrected import


def get_latest_news():
    try:
        url = "https://newsapi.org/v2/top-headlines?country=us&apiKey=695fe037cec349668377d018eca858a3"
        response = requests.get(url)
        data = response.json()

        if data["status"] == "ok":
            articles = data["articles"][:5]
            news_texts = [f"{i+1}. {article['title']}" for i,
                          article in enumerate(articles)]
            combined_news = "\n".join(news_texts)

            speak_offline("Here are the top 5 news headlines.")
            speak_offline(combined_news)
            return combined_news
        else:
            speak_offline("Failed to fetch news.")
            return "Failed to fetch news."

    except Exception as e:
        error_msg = f"An error occurred while fetching news: {e}"
        speak_offline(error_msg)
        return error_msg
