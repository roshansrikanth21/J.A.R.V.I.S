import base64
import io
try:
    import mss
    from PIL import Image
    import anthropic
except ImportError:
    pass

class VisionSystem:
    def __init__(self, config):
        self.config = config.get("brain", {})

    def capture_screen(self):
        """Captures the primary monitor and returns base64 encoded JPEG."""
        try:
            with mss.mss() as sct:
                # monitor 1 is usually the primary monitor
                monitor = sct.monitors[1]
                screenshot = sct.grab(monitor)
                
                # Convert to PIL Image
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                
                # Resize if needed to save tokens/memory, max 1080p
                img.thumbnail((1920, 1080))
                
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=85)
                return base64.b64encode(buffer.getvalue()).decode('utf-8')
        except Exception as e:
            print(f"[ERROR] Screen capture failed: {e}")
            return None

    def ask_about_screen(self, question="What is on the screen right now?"):
        """Takes a screenshot and sends it to Claude Vision API (or local LLaVA if configured)."""
        b64_image = self.capture_screen()
        if not b64_image:
            return "I could not capture the screen."

        api_key = self.config.get("anthropic_api_key")
        if not api_key or api_key == "YOUR_ANTHROPIC_KEY":
            return "Vision requires Anthropic API key in config."

        print("[JARVIS] Analyzing screen...")
        try:
            client = anthropic.Anthropic(api_key=api_key)
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
                                "data": b64_image
                            }
                        },
                        {
                            "type": "text", 
                            "text": question
                        }
                    ]
                }]
            )
            return response.content[0].text
        except Exception as e:
            return f"Vision analysis failed: {str(e)}"
