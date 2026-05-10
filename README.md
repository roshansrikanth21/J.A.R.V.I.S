# J.A.R.V.I.S. Companion AI

A fully offline-capable, highly modular AI assistant built for Windows. It features wake word detection, local STT (faster-whisper), local LLM (Ollama), local TTS (Piper), PC control (PyAutoGUI), and vector memory (ChromaDB).

## Setup Instructions

### 1. Prerequisites
- Python 3.11+
- [Ollama](https://ollama.com/) installed
- [Build Tools for Visual Studio](https://visualstudio.microsoft.com/visual-cpp-build-tools/) (Needed to compile PyAudio and ChromaDB dependencies)

### 2. Download Dependencies
Open PowerShell as Administrator:
```powershell
# Create virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

### 3. Model Setup
1. **Ollama**: Pull the Llama 3.1 model.
   ```powershell
   ollama run llama3.1:8b-instruct-q4_K_M
   ```
2. **Picovoice (Wake Word)**: 
   - Sign up at [Picovoice Console](https://console.picovoice.ai/).
   - Copy your Access Key and paste it in `config.yaml`.
   - Train a custom wake word ("Hey Jarvis") for Windows and put the `.ppn` file in this directory. Update `config.yaml` with the filename.
3. **Clap Wake (Optional, works without Picovoice key)**:
   - JARVIS can now wake on a clap pattern as an alternate trigger.
   - Default is **double-clap** (`clap_count_required: 2`).
   - Tune these in `config.yaml` under `voice`:
     - `enable_clap_wake`
     - `clap_threshold`
     - `clap_window_s`
     - `clap_cooldown_s`
4. **Piper (TTS)**:
   - Download the Piper Windows executable and model (`en_US-lessac-high.onnx` and `.json`) from [Piper's GitHub](https://github.com/rhasspy/piper).
   - Update `config.yaml` with the path to the `.onnx` model.

### 4. Running J.A.R.V.I.S
```powershell
python main.py
```
Wait for the system to say "System Initialized", then say "Hey Jarvis".
