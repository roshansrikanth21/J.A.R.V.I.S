from jarvis.modules.voice import VoiceSystem
from jarvis.modules.brain import Brain
from jarvis.modules.memory.enhanced_memory import JarvisMemoryManager
from jarvis.modules.actions import ActionEngine
from jarvis.modules.vision import VisionSystem
from jarvis.modules.intelligence import JarvisIntelligence
from jarvis.modules.comrade_bridge import ComradeBridge
from jarvis.tools.system_tools import GitHubTools
import threading
import time
import asyncio

class JarvisEngine:
    def __init__(self, config):
        self.config = config
        
        # Initialize modules
        self.memory = JarvisMemoryManager()
        self.voice = VoiceSystem(config)
        self.vision = VisionSystem(config)
        self.comrade = ComradeBridge(config)
        self.intelligence = JarvisIntelligence(config, self.comrade)
        self.actions = ActionEngine(config)
        self.brain = Brain(config, self.memory)
        self.github_tools = GitHubTools(self.voice)
        self.agent_tools = self._build_agent_tools()
        
        # ── Listeners & Background tasks ─────────────────────────────────────
        self.is_running = False
        self.listening_enabled = True
        self.event_queue = asyncio.Queue()
        self.loop = None
        self.tasks = []
        self.agent_trace = []
        self._threads = []
        
        # Start global hotkey listener
        self._start_hotkey_listener()
        # Start proactive monitoring
        self._start_proactive_monitor()

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
            
        elif action == "market_data":
            ticker = intent.get("args", {}).get("ticker", "")
            result = self.intelligence.get_market_price(ticker)
            response_text = f"Market data for {ticker}: {result['price']} {result['currency']}. Recommendation: {result['recommendation']}"
            
        elif action == "social_sentiment":
            topic = intent.get("args", {}).get("topic", "")
            result = self._tool_social_sentiment({"topic": topic})
            response_text = f"Social sentiment for {topic} is {result['sentiment']}. Scanned {result['sources']['reddit_count']} Reddit and {result['sources']['x_count']} X posts."

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
                    "description": "Paste a prompt file into the active window. Optionally focus a specific app first. Available prompts: analysis/code_review, analysis/security_audit, analysis/ctf_strategy, writing/report_template, writing/email_formal, tools/cursor_context.",
                    "args_schema": {"prompt_name": "string (name without .txt)", "app_title": "string (optional window title to focus)"},
                    "handler": lambda args: self.actions.paste_prompt_file(
                        args.get("prompt_name", ""), app_title=args.get("app_title")
                    ),
                },
                "look_at_screen": {
                    "description": "Capture, scan, and analyse the current screen using the vision LLM (LLaVA locally or Claude Vision). Use this for full scene understanding — what app is open, what is on the desk, or what error is shown.",
                    "args_schema": {"question": "string"},
                    "handler": lambda args: self.vision.ask_about_screen(
                        args.get("question", "What is on the screen right now?")
                    ),
                },
                "ocr_screen": {
                    "description": "Fast text extraction from screen using Tesseract OCR. Use this when you just need to read text (code, error messages, URLs) without full scene understanding. Much faster than look_at_screen.",
                    "args_schema": {},
                    "handler": lambda args: self.vision.ocr_screen(),
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
                "read_clipboard": {
                    "description": "Read the current text from the user's system clipboard.",
                    "args_schema": {},
                    "handler": lambda args: self.actions.read_clipboard(),
                },
                "close_window": {
                    "description": "Close an application window on the desktop by specifying part of its title.",
                    "args_schema": {"title": "string"},
                    "handler": lambda args: self.actions.close_window(args.get("title", "")),
                },
                "run_script": {
                    "description": "Run a Python script by path. Use this to execute analytical or automation scripts.",
                    "args_schema": {"path": "string"},
                    "handler": lambda args: self.actions.run_script(args.get("path", "")),
                },
                "market_data": {
                    "description": "Get real-time price and summary for a stock or crypto ticker (e.g. AAPL, TSLA, BTC-USD). Use this for investment analysis.",
                    "args_schema": {"ticker": "string"},
                    "handler": lambda args: self.intelligence.get_market_price(args.get("ticker", "")),
                },
                "social_sentiment": {
                    "description": "Scan X (Twitter) and Reddit for sentiment and news about a specific topic or asset.",
                    "args_schema": {"topic": "string"},
                    "handler": self._tool_social_sentiment,
                },
                "comrade_status": {
                    "description": "Check the status of the COMRADE trading terminal, including connection health and active positions.",
                    "args_schema": {},
                    "handler": lambda args: self.comrade.get_status(),
                },
                "comrade_analysis": {
                    "description": "Request a deep technical analysis or 'Regime Analysis' from COMRADE for a specific ticker (e.g. NIFTY, ^NSEI).",
                    "args_schema": {"ticker": "string"},
                    "handler": lambda args: self.comrade.get_analysis(args.get("ticker", "^NSEI")),
                },
                "comrade_link": {
                    "description": "General bridge to the COMRADE trading terminal. Use this for execution or specific commands not covered by other tools.",
                    "args_schema": {"command": "string", "args": "object"},
                    "handler": lambda args: self.comrade.send_command(args.get("command", ""), args.get("args", {})),
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
            action = step.get('action')
            if action == "sequential_thinking":
                thought = step.get('args', {}).get('thought', '')[:120]
                self.emit_event("status", f"Deep Thinking: {thought}")
            else:
                self.emit_event("status", f"Calling tool: {action}")
        elif event_type == "AGENT_TOOL_RESULT":
            self.emit_event("status", f"Tool result: {step.get('observation', '')[:120]}")
        elif event_type == "AGENT_PLAN_UPDATE":
            self.emit_event("status", f"Plan updated: {step.get('status')}")
        else:
            # Fallback for old style
            self.emit_event("agent_tool", step)
            if "action" in step and "observation" in step:
                self.emit_event("status", f"Tool: {step.get('action')} -> {step.get('observation', '')[:120]}")

    def _tool_social_sentiment(self, args):
        topic = args.get("topic", "")
        reddit = self.intelligence.search_reddit(topic)
        x_posts = self.intelligence.search_x(topic)
        
        all_text = [r['snippet'] for r in reddit] + [x['snippet'] for x in x_posts]
        sentiment = self.intelligence.analyze_sentiment(all_text)
        
        result = {
            "topic": topic,
            "sentiment": sentiment,
            "sources": {
                "reddit_count": len(reddit),
                "x_count": len(x_posts)
            },
            "top_reddit": reddit[0]['title'] if reddit else "None",
            "top_x": x_posts[0]['title'] if x_posts else "None"
        }
        return result

    def _tool_comrade_bridge(self, args):
        command = args.get("command", "")
        return self.comrade.send_command(command)

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
        t = threading.Thread(target=self._voice_loop, daemon=True)
        t.start()
        self._threads.append(t)

    def _start_hotkey_listener(self):
        """Background listener for global hotkeys."""
        try:
            import keyboard
            def on_hotkey():
                print("[HOTKEY] Summoned!")
                # We can't easily trigger the blocking voice loop's wake word logic,
                # so we might need a flag or a direct call.
                # For now, let's just emit a status event.
                self.emit_event("status", "Summoned via hotkey! Listening...")

            keyboard.add_hotkey('ctrl+alt+j', on_hotkey)
            print("[SYSTEM] Hotkey Ctrl+Alt+J registered.")
        except Exception as e:
            print(f"[ERROR] Could not register hotkey: {e}")

    def _start_proactive_monitor(self):
        """Runs background checks for system health and briefings."""
        def monitor():
            last_suggestion_time = 0
            last_stats_time = 0
            while self.is_running:
                time.sleep(10) # check more frequently for timing logic
                
                now = time.time()
                # Memory Stats every 2 mins
                if now - last_stats_time > 120:
                    stats = self.memory.get_stats()
                    self.emit_event("memory_stats", stats)
                    last_stats_time = now

                # Proactive Suggestions every 30 mins
                if now - last_suggestion_time > 1800:
                    suggestion = self.memory.get_proactive_suggestion()
                    if suggestion:
                        self.emit_event("proactive_event", {"text": suggestion})
                        self.add_task("Proactive Suggestion", eta="completed")
                    last_suggestion_time = now

                # Generic system health/scan logic could be expanded here

        t = threading.Thread(target=monitor, daemon=True)
        t.start()
        self._threads.append(t)

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
