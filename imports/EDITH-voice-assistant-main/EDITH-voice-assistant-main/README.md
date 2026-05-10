# EDITH – Virtual Voice Assistant (Python)

[![CI](https://img.shields.io/github/actions/workflow/status/ranjithguggilla/edith-voice-assistant/ci.yml?branch=main)](./actions)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Python](https://img.shields.io/badge/Python-3.9%2B-blue)

EDITH is a modular Python voice assistant. It listens to voice commands and performs tasks like:
- Task manager
- Text-to-speech
- Translator
- Speech-to-text
- Weather
- Open websites
- WhatsApp message sender
- Wikipedia search
- YouTube player
- App manager
- Email sender
- Location finder
- News headlines
- Open websites (alt)
- Password generator
- Email sender (alt)
- System control (apps/processes)

> This repo packages a full undergrad project into a professional structure with CI, docs, and tests. A modernization roadmap is included in `docs/`.

## Quickstart
```bash
git clone https://github.com/<your-username>/edith-voice-assistant.git
cd edith-voice-assistant
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
python src/edith/main.py
```

## Notes
- Some modules may require OS-specific dependencies (e.g., SAPI5 on Windows for TTS).
- Do not commit secrets. Use environment variables for tokens/passwords.
