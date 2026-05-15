import base64
import io
import time
try:
    import mss
    from PIL import Image
    import requests as _requests
except ImportError:
    pass

try:
    import anthropic as _anthropic
except ImportError:
    _anthropic = None

try:
    import pytesseract
    _TESSERACT_AVAILABLE = True
except ImportError:
    _TESSERACT_AVAILABLE = False


class VisionSystem:
    def __init__(self, config):
        self.config = config.get("brain", {})
        self.top_config = config  # keep root config for tesseract path etc.

        # Allow configuring Tesseract binary path
        tesseract_cmd = config.get("tesseract_cmd", None)
        if tesseract_cmd and _TESSERACT_AVAILABLE:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    # ------------------------------------------------------------------
    # Screen capture
    # ------------------------------------------------------------------

    def capture_screen(self):
        """Captures the primary monitor and returns (PIL.Image, base64 JPEG str)."""
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                screenshot = sct.grab(monitor)
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                img.thumbnail((1920, 1080))

                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=85)
                b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
                return img, b64
        except Exception as e:
            print(f"[ERROR] Screen capture failed: {e}")
            return None, None

    # ------------------------------------------------------------------
    # OCR fast-path (no VRAM)
    # ------------------------------------------------------------------

    def ocr_screen(self):
        """Fast text extraction from screen using Tesseract OCR (CPU, no VRAM)."""
        if not _TESSERACT_AVAILABLE:
            return "Tesseract is not installed. Run: pip install pytesseract"
        img, _ = self.capture_screen()
        if img is None:
            return "Screen capture failed."
        try:
            text = pytesseract.image_to_string(img)
            return text.strip() or "(No text detected on screen)"
        except Exception as e:
            return f"OCR failed: {e}"

    # ------------------------------------------------------------------
    # LLaVA vision via Ollama (local, GPU)
    # ------------------------------------------------------------------

    def _ask_llava(self, b64_image, question):
        """Sends a screenshot to the local LLaVA model via Ollama."""
        server_url = self.config.get("ollama_server", "http://localhost:11434")
        generate_url = f"{server_url}/api/generate"
        
        print(f"[JARVIS] Analyzing screen with local LLaVA at {server_url}...")
        try:
            # First, a quick connectivity check if we haven't already
            response = _requests.post(
                generate_url,
                json={
                    "model": "llava:7b",
                    "prompt": question,
                    "images": [b64_image],
                    "stream": False,
                },
                timeout=90,
            )
            if response.status_code == 200:
                return response.json().get("response", "")
            elif response.status_code == 404:
                return "The vision model 'llava:7b' was not found in Ollama. Please run 'ollama pull llava' in your terminal."
            return f"Ollama error {response.status_code}: {response.text[:200]}"
        except _requests.exceptions.ConnectionError:
            return "Could not connect to Ollama. Please ensure Ollama is running (ollama serve) and accessible at " + server_url
        except Exception as e:
            return f"Local vision analysis failed: {e}"

    # ------------------------------------------------------------------
    # Claude Vision API fallback
    # ------------------------------------------------------------------

    def _ask_claude_vision(self, b64_image, question):
        """Fallback: sends screenshot to Claude Vision API."""
        if _anthropic is None:
            return "anthropic package not installed."
        api_key = self.config.get("anthropic_api_key")
        if not api_key or api_key == "YOUR_ANTHROPIC_KEY":
            return "Vision requires Anthropic API key in config (or local LLaVA)."
        print("[JARVIS] Analyzing screen with Claude Vision...")
        try:
            client = _anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model=self.config.get("cloud_model", "claude-3-5-sonnet-20240620"),
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": b64_image,
                            },
                        },
                        {"type": "text", "text": question},
                    ],
                }],
            )
            return response.content[0].text
        except Exception as e:
            return f"Claude vision failed: {e}"

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def ask_about_screen(self, question="What is on the screen right now?"):
        """Takes a screenshot and analyses it.

        Routing:
          primary_llm == 'local'  ->  LLaVA via Ollama (VRAM-aware)
          primary_llm == 'cloud'  ->  Claude Vision API
        """
        try:
            img, b64_image = self.capture_screen()
        except Exception as e:
            logger.error(f"Vision capture exception: {e}")
            return f"I encountered an error while trying to capture the screen: {e}"

        if not b64_image:
            return "I could not capture the screen. Please ensure the app has screen recording permissions."

        primary_llm = self.config.get("primary_llm", "local")

        if primary_llm == "local":
            res = self._ask_llava(b64_image, question)
            if "model not found" in res.lower() or "not found" in res.lower():
                return "The local vision model 'llava:7b' is not installed in Ollama. Please run 'ollama pull llava' in your terminal."
            return res
        else:
            return self._ask_claude_vision(b64_image, question)
