# edith_modules/task_manager.py

import os
import platform
# ✅ Ensure this import path matches your project structure
from .text_to_speech import speak_offline


def open_task_manager():
    system_platform = platform.system()

    if system_platform == "Windows":
        speak_offline("Opening Task Manager.")
        os.system("taskmgr")

    elif system_platform == "Darwin":  # macOS
        speak_offline("Opening Activity Monitor.")
        os.system("open -a 'Activity Monitor'")

    elif system_platform == "Linux":
        speak_offline("Opening System Monitor.")
        # Optional: Customize for KDE/XFCE/LXDE etc.
        os.system("gnome-system-monitor &")

    else:
        speak_offline("Unsupported operating system for task manager.")
