import argparse
import sys

from edith_modules import (
    open_websites, app_manager, email_sender, location_finder, news,
    password_generator, send_email, system_control, task_manager,
    text_to_speech, translator, voice_recognition, weather,
    web_opener, whatsapp_sender, wiki_search, youtube_player
)


def main():
    parser = argparse.ArgumentParser(
        description="EDITH – Your Virtual Assistant"
    )
    parser.add_argument(
        "--task", help="Task for EDITH (e.g., 'weather', 'news', 'open')", type=str
    )
    parser.add_argument(
        "--query", help="Optional query for the task", type=str
    )
    args = parser.parse_args()

    if args.task:
        dispatch_task(args.task.lower(), args.query)
    else:
        run_voice_mode()


def dispatch_task(task: str, query: str = ""):
    try:
        if task == "open":
            open_websites.open_website(query)
        elif task == "app":
            app_manager.launch_app(query)
        elif task == "email":
            send_email.send(query)
        elif task == "location":
            location_finder.find_location(query)
        elif task == "news":
            news.get_latest_news()
        elif task == "password":
            password_generator.generate_password()
        elif task == "system":
            system_control.control_system(query)
        elif task == "task":
            task_manager.run_task(query)
        elif task == "tts":
            text_to_speech.speak(query)
        elif task == "translate":
            translator.translate_text(query)
        elif task == "weather":
            weather.get_weather(query)
        elif task == "wiki":
            wiki_search.search_wikipedia(query)
        elif task == "youtube":
            youtube_player.play_youtube(query)
        elif task == "whatsapp":
            whatsapp_sender.send_whatsapp(query)
        elif task == "web":
            web_opener.search_web(query)
        else:
            print(f"❓ Unknown task: {task}")
    except Exception as e:
        print(f"⚠️ Error executing task '{task}': {e}")


def run_voice_mode():
    print("🎙️ Voice mode activated... Speak your command.")
    try:
        voice_command = voice_recognition.listen()
        dispatch_task(voice_command['task'], voice_command.get('query', ''))
    except Exception as e:
        print(f"❌ Voice mode error: {e}")


if __name__ == "__main__":
    main()
