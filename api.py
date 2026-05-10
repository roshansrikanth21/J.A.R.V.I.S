import os
import yaml
import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from jarvis.engine import JarvisEngine
import uvicorn

app = FastAPI(title="J.A.R.V.I.S. Web OS")

# We will mount the built React UI at the end so it doesn't shadow API routes.

# Initialize Engine globally
if not os.path.exists("config.yaml"):
    print("[ERROR] config.yaml not found! Creating default...")
    default_config = {
        "system": {"name": "JARVIS", "wake_word": "jarvis", "picovoice_key": ""},
        "voice": {"stt_model": "base", "stt_device": "cpu", "stt_compute_type": "int8", "tts_model_path": "en_US-lessac-high.onnx"},
        "brain": {"primary_llm": "local", "local_model": "llama3.1:8b-instruct-q4_K_M"},
        "memory": {"db_path": "./memory/chroma_db", "embedding_model": "all-MiniLM-L6-v2"},
        "apps": {}
    }
    with open("config.yaml", "w") as f:
        yaml.dump(default_config, f)

with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

# Engine initialization
engine = JarvisEngine(config)

# Connected WebSocket clients
active_connections = []

@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_running_loop()
    engine.start_background_loop(loop)
    
    # Background task to broadcast queue messages
    asyncio.create_task(broadcast_events())

async def broadcast_events():
    while True:
        event = await engine.event_queue.get()
        disconnected = []
        for connection in active_connections:
            try:
                await connection.send_json(event)
            except WebSocketDisconnect:
                disconnected.append(connection)
            except Exception as e:
                print(f"WS Error: {e}")
                disconnected.append(connection)
        
        for d in disconnected:
            if d in active_connections:
                active_connections.remove(d)

# HTML routes are now handled by the StaticFiles mount.
class CommandRequest(BaseModel):
    command: str

class VoiceSettingsUpdate(BaseModel):
    input_device_index: int | None = None
    enable_clap_wake: bool
    enable_keyword_wake: bool
    clap_threshold: int
    clap_count_required: int
    clap_window_s: float
    clap_cooldown_s: float

@app.post("/api/command")
async def api_command(req: CommandRequest):
    # This might block if process_text_command is blocking and slow, 
    # but currently brain parsing is relatively fast.
    response = engine.process_text_command(req.command)
    return {"response": response}

@app.get("/api/audio/devices")
async def audio_devices():
    return {"devices": engine.voice.list_input_devices()}

@app.get("/api/settings/voice")
async def get_voice_settings():
    voice_cfg = config.get("voice", {})
    return {
        "settings": {
            "input_device_index": voice_cfg.get("input_device_index"),
            "enable_clap_wake": bool(voice_cfg.get("enable_clap_wake", True)),
            "enable_keyword_wake": bool(voice_cfg.get("enable_keyword_wake", True)),
            "clap_threshold": int(voice_cfg.get("clap_threshold", 12000)),
            "clap_count_required": int(voice_cfg.get("clap_count_required", 2)),
            "clap_window_s": float(voice_cfg.get("clap_window_s", 1.2)),
            "clap_cooldown_s": float(voice_cfg.get("clap_cooldown_s", 0.25)),
        }
    }

@app.put("/api/settings/voice")
async def update_voice_settings(payload: VoiceSettingsUpdate):
    updated_voice = {
        "input_device_index": payload.input_device_index,
        "enable_clap_wake": payload.enable_clap_wake,
        "enable_keyword_wake": payload.enable_keyword_wake,
        "clap_threshold": payload.clap_threshold,
        "clap_count_required": payload.clap_count_required,
        "clap_window_s": payload.clap_window_s,
        "clap_cooldown_s": payload.clap_cooldown_s,
    }
    config.setdefault("voice", {}).update(updated_voice)
    with open("config.yaml", "w", encoding="utf-8") as config_file:
        yaml.safe_dump(config, config_file, sort_keys=False)

    engine.update_voice_settings(voice_cfg=updated_voice)
    return {"ok": True, "settings": updated_voice}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except Exception:
                data = {"action": raw}

            action = data.get("action")
            if action == "start_listening":
                engine.set_listening(True)
                await websocket.send_json({"type": "state", "status": "listening", "text": "Listening enabled."})
            elif action == "stop_listening":
                engine.set_listening(False)
                await websocket.send_json({"type": "state", "status": "idle", "text": "Listening paused."})
            elif action == "command":
                command = data.get("text", "").strip()
                if command:
                    response = engine.process_text_command(command)
                    await websocket.send_json({"type": "llm_response", "text": response})
    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)

# Mount the React UI
if os.path.exists("ui/dist"):
    app.mount("/", StaticFiles(directory="ui/dist", html=True), name="ui")
else:
    @app.get("/")
    async def fallback():
        return {"error": "UI not built. Run 'npm run build' in the ui/ directory."}

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
