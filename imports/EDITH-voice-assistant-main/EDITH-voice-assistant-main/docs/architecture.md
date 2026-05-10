# Architecture

- `src/edith/main.py` orchestrates voice input -> intent -> action.
- Feature modules are isolated (weather, news, translator, whatsapp, email, etc.).
- Roadmap: async core, plugin registry, cross-platform TTS/STT.
