import os
import psutil
from edith_modules.text_to_speech import speak_offline  # Corrected import path


def list_apps():
    """List running applications."""
    apps = set()
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            name = proc.info['name']
            if name:
                apps.add(name)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return sorted(apps)


def kill_app(app_name: str):
    """Kill an application by name."""
    killed = False
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] and app_name.lower() in proc.info['name'].lower():
                proc.kill()
                killed = True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return killed


def open_app(app_path: str):
    """Open an application using its path."""
    try:
        # For macOS. Use 'start' on Windows or 'xdg-open' on Linux
        os.system(f"open '{app_path}'")
        return True
    except Exception as e:
        print(f"Error opening app: {e}")
        return False


def announce_app_list():
    """Announce all running apps using text-to-speech."""
    apps = list_apps()
    if not apps:
        speak_offline("No running applications found.")
    else:
        speak_offline("Currently running applications are:")
        for app in apps:
            speak_offline(app)
