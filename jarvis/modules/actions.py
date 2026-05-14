import os
import subprocess
import time
try:
    import pyautogui
    import pyperclip
except ImportError:
    pass

class ActionEngine:
    def __init__(self, config):
        self.app_map = config.get("apps", {})
        self.prompts_dir = config.get("prompts_dir", os.path.join(os.getcwd(), "prompts"))
        
        # Failsafe for pyautogui
        try:
            pyautogui.FAILSAFE = True
            pyautogui.PAUSE = 0.1
        except Exception:
            pass

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

    def find_prompt_path(self, prompt_name):
        """Searches the full prompts directory tree for a matching .txt file."""
        base = self.prompts_dir
        # Try direct match first
        direct = os.path.join(base, f"{prompt_name}.txt")
        if os.path.exists(direct):
            return direct
        # Walk all sub-folders
        for root, _, files in os.walk(base):
            for fname in files:
                if fname == f"{prompt_name}.txt" or fname == prompt_name:
                    return os.path.join(root, fname)
        return None

    def list_prompts(self):
        """Returns all available prompt names relative to the prompts folder."""
        base = self.prompts_dir
        available = []
        for root, _, files in os.walk(base):
            for f in files:
                if f.endswith(".txt"):
                    rel = os.path.relpath(os.path.join(root, f), base)
                    available.append(rel.replace("\\", "/").replace(".txt", ""))
        return available

    def paste_prompt_file(self, prompt_name, app_title=None):
        """Reads a .txt from /prompts (any sub-folder) and pastes it into the active window.
        
        Args:
            prompt_name: Filename without .txt extension (e.g. 'code_review' or 'analysis/code_review')
            app_title: Optional window title substring to focus before pasting
        """
        path = self.find_prompt_path(prompt_name)
        if not path:
            available = self.list_prompts()
            return f"Prompt '{prompt_name}' not found. Available: {', '.join(available)}"
            
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            pyperclip.copy(content)
            
            # Optionally focus a target window first
            if app_title:
                try:
                    from pywinauto import Desktop
                    wins = Desktop(backend="uia").windows(title_re=f".*{app_title}.*", visible_only=True)
                    if wins:
                        wins[0].set_focus()
                        time.sleep(0.3)
                except Exception:
                    pass  # Non-fatal: paste to current focus
            
            pyautogui.hotkey('ctrl', 'v')
            return f"Pasted prompt '{prompt_name}' successfully."
        except Exception as e:
            return f"Failed to paste: {e}"

    def hotkey(self, keys):
        """Sends a combination of keys, e.g. ['ctrl', 'c']."""
        try:
            pyautogui.hotkey(*keys)
            return f"Executed hotkey: {keys}"
        except Exception as e:
            return f"Hotkey failed: {e}"
            
    def click(self, x=None, y=None):
        """Clicks at position (x, y) or current cursor position if not specified."""
        try:
            if x is not None and y is not None:
                pyautogui.click(x, y)
            else:
                pyautogui.click()
            return "Clicked."
        except Exception as e:
            return str(e)

    def read_clipboard(self):
        """Returns the current clipboard content."""
        try:
            return pyperclip.paste()
        except Exception as e:
            return f"Failed to read clipboard: {e}"

    def close_window(self, title):
        """Closes a window matching the title using pywinauto."""
        try:
            from pywinauto import Desktop
            windows = Desktop(backend="uia").windows(title_re=f".*{title}.*", visible_only=True)
            if windows:
                windows[0].close()
                return f"Closed window matching: {title}"
            return f"No window found matching: {title}"
        except Exception as e:
            return f"Failed to close window: {e}"

    def run_script(self, path):
        """Runs a Python script at the given path."""
        try:
            subprocess.Popen(['python', path])
            return f"Running script: {path}"
        except Exception as e:
            return f"Failed to run script: {e}"
