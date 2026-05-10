# edith_modules/system_control.py

import os
import platform
import subprocess
from .text_to_speech import speak_offline  # ✅ Ensure relative import


def restart():
    system_platform = platform.system()
    if system_platform == "Windows":
        os.system("shutdown /r /t 1")
    elif system_platform in ("Linux", "Darwin"):
        os.system("sudo reboot")
    else:
        speak_offline("Restart is not supported on this operating system.")


def logout():
    system_platform = platform.system()
    speak_offline("Logging out.")
    if system_platform == "Windows":
        os.system("shutdown -l")
    elif system_platform == "Linux":
        os.system("gnome-session-quit --logout --no-prompt")
    elif system_platform == "Darwin":
        subprocess.call([
            "osascript", "-e",
            'tell application "System Events" to log out'
        ])
    else:
        speak_offline("Logout is not supported on this operating system.")
