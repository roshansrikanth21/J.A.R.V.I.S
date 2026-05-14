from jarvis.modules.voice import VoiceSystem
from jarvis.modules.brain import Brain
from jarvis.modules.memory import MemorySystem
from jarvis.modules.actions import ActionEngine
from jarvis.modules.vision import VisionSystem
from jarvis.tools.system_tools import GitHubTools
import threading
import time
import asyncio

class JarvisEngine:
    def __init__(self, config):
        self.config = config
        
        # Initialize modules
        self.memory = MemorySystem(config)
        self.voice = VoiceSystem(config)
        self.vision = VisionSystem(config)
        self.actions = ActionEngine(config)
        self.brain = Brain(config, self.memory)
        self.github_tools = GitHubTools(self.voice)
        self.agent_tools = self._build_agent_tools()
        
        self.is_running = False
        self.listening_enabled = True
        self.event_queue = asyncio.Queue()
        self.loop = None
        self.tasks = [] # Track real-time tasks
        self.agent_trace = []

    def emit_event(self, event_type, message):
        """Emits a normalized WebSocket event payload to the async queue."""
        if event_type != "audio_level":
            print(f"[{event_type.upper()}] {message}")
        if not (self.loop and self.event_queue):
            return

        payload = {"type": event_type, "message": message}

        # Normalize backend event types to the UI contract.
        if event_type == "status":
            payload = {
                "type": "state",
                "status": "speaking" if str(message).lower().startswith(("processing:", "speaking:")) else "listening",
                "text": message,
                "message": message,
            }
        elif event_type == "transcript":
            payload = {"type": "transcription", "text": message, "message": message}
        elif event_type == "response":
            payload = {"type": "llm_response", "text": message, "message": message}
        elif event_type == "audio_level":
            payload = {"type": "audio_level", "level": message}
        elif event_type == "tasks_update":
            payload = {"type": "tasks", "tasks": self.get_tasks()}
        elif event_type == "agent_tool":
            payload = {"type": "agent_tool", "step": message}
        elif event_type == "agent_event":
            payload = {"type": "agent_event", "event": message}

        asyncio.run_coroutine_threadsafe(self.event_queue.put(payload), self.loop)

    def process_text_command(self, command_text):
        """Processes a text command manually (e.g. from UI)"""
        self.emit_event("status", f"Processing: {command_text}")
        
        # Track as an active task
        self.add_task(f"Exec: {command_text}", eta="now")
        if self.tasks:
            self.tasks[0]["status"] = "active"
            self.emit_event("tasks_update", "Task activated")

        intent = self.brain.parse_intent(command_text)
        action = intent.get("action", "chat")
        
        self.emit_event("intent", str(intent))
        
        response_text = ""
        if action == "open_app":
            app_name = intent.get("args", {}).get("app_name", "")
            result = self.actions.open_app(app_name)
            response_text = f"I have {result}"
            
        elif action == "paste_prompt":
            prompt_name = intent.get("args", {}).get("prompt_name", "")
            result = self.actions.paste_prompt_file(prompt_name)
            response_text = result
            
        elif action == "vision":
            self.emit_event("status", "Looking at screen...")
            analysis = self.vision.ask_about_screen(command_text)
            response_text = self.brain.ask(f"The screen shows: {analysis}. The user asked: {command_text}")
            
        elif action == "send_whatsapp":
            args = intent.get("args", {})
            result = self.github_tools.send_whatsapp(args.get("phone", ""), args.get("message", ""))
            response_text = result
            
        elif action == "play_youtube":
            query = intent.get("args", {}).get("query", "")
            result = self.github_tools.play_youtube(query)
            response_text = result
            
        elif action == "get_news":
            self.emit_event("status", "Fetching news...")
            result = self.github_tools.get_news()
            if isinstance(result, dict) and result.get("type") == "news_data":
                self.emit_event("news_data", result)
                # Ask brain to summarize
                titles = [a["title"] for a in result["articles"]]
                summary_prompt = f"The following are the top news headlines: {titles}. Briefly summarize the most important one in one sentence to tell the user."
                response_text = self.brain.ask(summary_prompt)
            else:
                response_text = result
            
        elif action == "system_control":
            command = intent.get("args", {}).get("command", "")
            result = self.github_tools.control_system(command)
            response_text = result
            
        else:
            response_text = self.brain.run_agent(
                command_text,
                tools=self.agent_tools,
                on_step=self._record_agent_step,
            )
            
        self.emit_event("response", response_text)
        self.memory.remember(f"User: {command_text}\nJARVIS: {response_text}")
        
        # Mark current task as done
        if len(self.tasks) > 0 and self.tasks[0]["status"] == "active":
            done_task = self.tasks.pop(0)
            done_task["status"] = "done"
            done_task["at"] = time.strftime("%H:%M")
            self.tasks.append(done_task)
            self.emit_event("tasks_update", "Task completed")

        # Speak the response in a separate thread so it doesn't block the UI.
        threading.Thread(target=self._speak_response, args=(response_text,), daemon=True).start()
        
        return response_text

    def _speak_response(self, response_text):
        self.emit_event("status", "Speaking: response audio")
        try:
            self.voice.speak(response_text)
        finally:
            self.emit_event("status", "idle")
            
    def stop_speaking(self):
        """Immediately interrupt JARVIS."""
        self.voice.stop()
        self.emit_event("status", "idle")

    def get_tasks(self):
        """Returns the task list formatted for the UI."""
        return self.tasks[-10:] # Return last 10 tasks

    def _build_agent_tools(self):
        """Combines reasoning tools with safe PC/action tools."""
        tools = self.brain.default_tools()
        configured_apps = ", ".join(sorted(self.config.get("apps", {}).keys())) or "none"

        tools.update(
            {
                "open_app": {
                    "description": f"Open a configured desktop app. Available app names: {configured_apps}.",
                    "args_schema": {"app_name": "string"},
                    "handler": lambda args: self.actions.open_app(args.get("app_name", "")),
                },
                "paste_prompt": {
                    "description": "Paste a prompt file from the prompts directory into the active window.",
                    "args_schema": {"prompt_name": "string without .txt"},
                    "handler": lambda args: self.actions.paste_prompt_file(args.get("prompt_name", "")),
                },
                "look_at_screen": {
                    "description": "Capture and analyze the current screen when visual context is needed.",
                    "args_schema": {"question": "string"},
                    "handler": lambda args: self.vision.ask_about_screen(
                        args.get("question", "What is on the screen right now?")
                    ),
                },
                "play_youtube": {
                    "description": "Open YouTube and play a requested video or search query.",
                    "args_schema": {"query": "string"},
                    "handler": lambda args: self.github_tools.play_youtube(args.get("query", "")),
                },
                "get_news": {
                    "description": "Fetch the latest top news headlines.",
                    "args_schema": {},
                    "handler": lambda args: self.github_tools.get_news(),
                },
                "search_web": {
                    "description": "Search the internet for up-to-date information, news, vulnerabilities, concepts, or general facts.",
                    "args_schema": {"query": "string"},
                    "handler": lambda args: self.github_tools.search_web(args.get("query", "")),
                },
            }
        )
        return tools

    def _record_agent_step(self, step):
        self.agent_trace.append(step)
        self.agent_trace = self.agent_trace[-25:]
        
        # New structured event
        self.emit_event("agent_event", step)
        
        # Maintain backwards compatibility or UI updates
        event_type = step.get("type", "")
        if event_type == "AGENT_THOUGHT":
            self.emit_event("status", f"Thinking: {step.get('text', '')[:120]}")
        elif event_type == "AGENT_TOOL_CALL":
            self.emit_event("status", f"Calling tool: {step.get('action')}")
        elif event_type == "AGENT_TOOL_RESULT":
            self.emit_event("status", f"Tool result: {step.get('observation', '')[:120]}")
        elif event_type == "AGENT_PLAN_UPDATE":
            self.emit_event("status", f"Plan updated: {step.get('status')}")
        else:
            # Fallback for old style
            self.emit_event("agent_tool", step)
            if "action" in step and "observation" in step:
                self.emit_event("status", f"Tool: {step.get('action')} -> {step.get('observation', '')[:120]}")

    def get_agent_status(self):
        """Returns UI-facing agent capability and runtime state."""
        return {
            "brain": {
                "primary_llm": self.brain.primary_llm,
                "local_model": self.brain.local_model,
                "max_agent_steps": self.brain.max_agent_steps,
                "use_llm_intent_router": self.brain.use_llm_intent_router,
            },
            "memory": self.memory.stats() if self.memory else {"available": False, "count": 0},
            "tools": self.brain.tool_manifest(self.agent_tools),
            "tasks": self.get_tasks(),
            "trace": self.agent_trace,
            "safety": {
                "bounded_steps": True,
                "power_actions_in_agent_loop": False,
                "tool_protocol": "json",
                "human_confirmation_required_for_power": True,
            },
        }

    def add_task(self, title, eta=""):
        """Adds a new task to the queue."""
        task = {
            "id": int(time.time()),
            "t": title,
            "eta": eta,
            "status": "queued",
            "at": time.strftime("%H:%M")
        }
        self.tasks.insert(0, task)
        self.emit_event("tasks_update", "Task added")

    def _voice_loop(self):
        """The main blocking voice loop running in a background thread."""
        self.emit_event("status", "System Initialized and Ready. Listening for Wake Word...")
        
        while self.is_running:
            try:
                if not self.listening_enabled:
                    time.sleep(0.2)
                    continue

                # 1. Listen for Wake Word
                self.voice.listen_for_wake_word(on_level=lambda level: self.emit_event("audio_level", level))
                self.emit_event("status", "Wake Word detected! Listening...")
                
                # 2. Record command
                audio_path = self.voice.record_audio()
                if not audio_path:
                    self.emit_event("status", "Waiting for Wake Word...")
                    continue
                    
                # 3. Transcribe
                self.emit_event("status", "Transcribing...")
                command_text = self.voice.transcribe(audio_path)
                if not command_text:
                    self.emit_event("status", "Waiting for Wake Word...")
                    continue
                    
                self.emit_event("transcript", command_text)
                
                # 4. Process the command
                self.process_text_command(command_text)
                
                self.emit_event("status", "Waiting for Wake Word...")
            except Exception as e:
                self.emit_event("error", str(e))
                time.sleep(1)

    def start_background_loop(self, loop):
        """Starts the voice detection loop in a background thread."""
        self.loop = loop
        self.is_running = True
        self.thread = threading.Thread(target=self._voice_loop, daemon=True)
        self.thread.start()

    def set_listening(self, enabled: bool):
        self.listening_enabled = enabled
        state = "Listening enabled." if enabled else "Listening paused."
        self.emit_event("status", state)

    def update_voice_settings(self, system_cfg=None, voice_cfg=None):
        """Updates voice-related runtime settings."""
        if system_cfg:
            self.config.setdefault("system", {}).update(system_cfg)
        if voice_cfg:
            self.config.setdefault("voice", {}).update(voice_cfg)
        self.voice.apply_runtime_settings(system_cfg=system_cfg, voice_cfg=voice_cfg)
        self.emit_event("status", "Voice settings updated.")

    def stop(self):
        self.is_running = False
        
    def run(self):
        """Original blocking run method."""
        self.is_running = True
        self._voice_loop()
