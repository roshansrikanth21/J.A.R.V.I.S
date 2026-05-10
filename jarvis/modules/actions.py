import os
import subprocess
try:
    import pyautogui
    import pyperclip
except ImportError:
    pass

class ActionEngine:
    def __init__(self, config):
        self.app_map = config.get("apps", {})
        
        # Failsafe for pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.1

    def open_app(self, app_name):
        """Opens an application mapped in the config."""
        app_name_lower = app_name.lower()
        if app_name_lower in self.app_map:
            path = self.app_map[app_name_lower]
            try:
                subprocess.Popen([path])
                return f"Opened {app_name}."
            except Exception as e:
                return f"Failed to open {app_name}: {e}"
        else:
            return f"App {app_name} is not mapped in config.yaml."

    def type_text(self, text, interval=0.02):
        """Types text out via virtual keyboard."""
        try:
            pyautogui.write(text, interval=interval)
            return "Text typed successfully."
        except Exception as e:
            return f"Typing failed: {e}"

    def paste_prompt_file(self, prompt_name):
        """Reads a .txt from /prompts and pastes it into the active window."""
        path = os.path.join(os.getcwd(), "prompts", f"{prompt_name}.txt")
        if not os.path.exists(path):
            return f"Prompt {prompt_name} not found."
            
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            pyperclip.copy(content)
            # Send Ctrl+V
            pyautogui.hotkey('ctrl', 'v')
            return f"Pasted prompt: {prompt_name}."
        except Exception as e:
            return f"Failed to paste: {e}"

    def hotkey(self, keys):
        """Sends a combination of keys, e.g. ['ctrl', 'c']."""
        try:
            pyautogui.hotkey(*keys)
            return f"Executed hotkey: {keys}"
        except Exception as e:
            return f"Hotkey failed: {e}"
            
    def click(self):
        try:
            pyautogui.click()
            return "Clicked."
        except Exception as e:
            return str(e)
