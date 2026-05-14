import ast
import datetime as _dt
import json
import re

try:
    import ollama
except ImportError:
    ollama = None

try:
    import anthropic
except ImportError:
    anthropic = None

try:
    import requests
except ImportError:
    requests = None


class Brain:
    def __init__(self, config, memory_system):
        self.config = config.get("brain", {})
        self.memory = memory_system
        self.primary_llm = self.config.get("primary_llm", "local")
        self.ollama_server = self.config.get("ollama_server", "http://localhost:11434")
        self.local_model = self.config.get("local_model", "llama3.1:8b-instruct-q4_K_M")
        self.max_agent_steps = int(self.config.get("max_agent_steps", 25))
        self.use_llm_intent_router = bool(self.config.get("use_llm_intent_router", False))

        self.system_prompt = "You are JARVIS. Answer concisely."
        try:
            with open("prompts/system_prompt.txt", "r", encoding="utf-8") as f:
                self.system_prompt = f.read()
        except OSError:
            pass

    def ask(self, query, context_override=None):
        """Standard conversational query with memory context injected."""
        context_str = ""

        if self.memory:
            memories = self.memory.recall(query)
            if memories:
                context_str = "\nRelevant past memories:\n" + "\n".join(memories)

        if context_override:
            context_str += f"\nAdditional Context:\n{context_override}"

        full_prompt = f"{self.system_prompt}\n{context_str}\n\nUser: {query}\nJARVIS:"
        return self._ask_model(full_prompt)

    def _ask_model(self, prompt):
        if self.primary_llm == "local":
            return self._ask_ollama(prompt)
        return self._ask_claude(prompt)

    def _ask_ollama(self, prompt):
        if ollama is None:
            return "I am currently offline. Please install the Ollama Python package."

        try:
            client = ollama.Client(host=self.ollama_server)
            response = client.generate(model=self.local_model, prompt=prompt)
            return response["response"].strip()
        except Exception as e:
            print(f"[OLLAMA ERROR] Is Ollama running at {self.ollama_server}? {e}")
            return f"I am currently offline. Please start the Ollama server at {self.ollama_server}."

    def _ask_claude(self, prompt):
        if anthropic is None:
            return "My cloud brain is disconnected. The Anthropic package is missing."

        api_key = self.config.get("anthropic_api_key")
        if not api_key or api_key == "YOUR_ANTHROPIC_KEY":
            return "My cloud brain is disconnected. API key is missing."

        try:
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model=self.config.get("cloud_model", "claude-3-5-sonnet-20240620"),
                max_tokens=512,
                system=self.system_prompt,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except Exception as e:
            return f"Cloud error: {str(e)}"

    def parse_intent(self, text):
        """Ask the model to classify direct command intents into JSON."""
        quick_intent = self._quick_intent(text)
        if quick_intent:
            return quick_intent
        if not self.use_llm_intent_router:
            return {"action": "chat"}

        schema = """
        Analyze the text. If it is a conversational request, return {"action": "chat"}.
        If it requires opening an app, return {"action": "open_app", "args": {"app_name": "name"}}.
        If it requires looking at screen, return {"action": "vision"}.
        If it requires pasting a prompt, return {"action": "paste_prompt", "args": {"prompt_name": "name"}}.
        If it requires sending a WhatsApp message, return {"action": "send_whatsapp", "args": {"phone": "number", "message": "text"}}.
        If it requires playing a YouTube video, return {"action": "play_youtube", "args": {"query": "search term"}}.
        If it requires getting the news, return {"action": "get_news"}.
        If it requires system power control (shutdown, restart, logout), return {"action": "system_control", "args": {"command": "restart|shutdown|logout"}}.
        Respond ONLY in valid JSON format.
        """
        prompt = f"Text: {text}\nSchema instructions: {schema}"
        try:
            res = self._ask_model(prompt)
            json_str = re.search(r"\{.*\}", res, re.DOTALL)
            if json_str:
                return json.loads(json_str.group(0))
            return {"action": "chat"}
        except Exception:
            return {"action": "chat"}

    def _quick_intent(self, text):
        text = str(text or "").strip()
        lower = text.lower()

        for prefix in ("open ", "launch ", "start "):
            if lower.startswith(prefix):
                app_name = text[len(prefix) :].strip()
                if app_name:
                    return {"action": "open_app", "args": {"app_name": app_name}}

        if "paste prompt" in lower:
            prompt_name = lower.split("paste prompt", 1)[1].strip()
            if prompt_name:
                return {"action": "paste_prompt", "args": {"prompt_name": prompt_name}}

        screen_phrases = ("look at screen", "see my screen", "what is on my screen", "analyze my screen")
        if any(phrase in lower for phrase in screen_phrases):
            return {"action": "vision"}

        if "youtube" in lower and ("play" in lower or "open" in lower):
            query = re.sub(r"\b(play|open|on|youtube)\b", " ", lower)
            query = re.sub(r"\s+", " ", query).strip()
            return {"action": "play_youtube", "args": {"query": query or text}}

        if "whatsapp" in lower and "send" in lower:
            phone_match = re.search(r"(\+?\d[\d\s-]{7,}\d)", text)
            if phone_match:
                phone = re.sub(r"[\s-]+", "", phone_match.group(1))
                message = text[phone_match.end() :].strip(" :,-")
                for marker in (" saying ", " message ", " that "):
                    marker_index = lower.find(marker)
                    if marker_index >= 0:
                        message = text[marker_index + len(marker) :].strip(" :,-")
                        break
                if message:
                    return {"action": "send_whatsapp", "args": {"phone": phone, "message": message}}

        if "news" in lower and any(word in lower for word in ("get", "latest", "today", "headlines", "show")):
            return {"action": "get_news"}

        for command in ("restart", "shutdown", "logout"):
            if command in lower and any(word in lower for word in ("pc", "computer", "system", "windows")):
                return {"action": "system_control", "args": {"command": command}}

        return None

    def run_agent(self, query, tools=None, max_steps=None, context_override=None, on_step=None):
        """
        Run a bounded sense-think-act loop.

        The model emits JSON that either calls one allowed tool or returns the
        final answer. Tool observations are fed back into the next turn.
        """
        max_steps = max_steps or self.max_agent_steps
        tools = tools or self.default_tools()
        memories = self.memory.recall(query) if self.memory else []
        transcript = []

        for step in range(max_steps):
            prompt = self._build_agent_prompt(
                query=query,
                tools=tools,
                memories=memories,
                transcript=transcript,
                context_override=context_override,
            )
            raw_response = self._ask_model(prompt)
            decision = self._parse_agent_decision(raw_response)

            if not decision:
                return self.ask(query, context_override=context_override)

            action = str(decision.get("action", "final")).strip()
            args = decision.get("args", {}) or {}
            thought = decision.get("thought", "")

            if on_step and thought:
                on_step({"type": "AGENT_THOUGHT", "text": thought, "step": step + 1})

            if action == "final":
                answer = str(decision.get("answer", "")).strip()
                if on_step:
                    on_step({"type": "AGENT_PLAN_UPDATE", "status": "completed"})
                return answer or self.ask(query, context_override=context_override)

            if on_step:
                on_step({"type": "AGENT_TOOL_CALL", "action": action, "args": args, "step": step + 1})

            if action not in tools:
                observation = f"Tool '{action}' is not available. Choose one of: {', '.join(tools)}."
            else:
                observation = self._execute_tool(tools[action], args)

            transcript.append(
                {
                    "step": step + 1,
                    "thought": thought,
                    "action": action,
                    "args": args,
                    "observation": self._truncate(observation, 1200),
                }
            )
            if on_step:
                on_step({
                    "type": "AGENT_TOOL_RESULT",
                    "step": step + 1,
                    "action": action,
                    "observation": self._truncate(observation, 1200)
                })

        summary = "\n".join(
            f"{item['step']}. {item['action']} -> {item['observation']}"
            for item in transcript
        )
        return self.ask(
            f"Give the user a concise answer for: {query}\nTool work completed:\n{summary}",
            context_override=context_override,
        )

    def react(self, query, max_steps=5):
        """Compatibility wrapper for older callers."""
        return self.run_agent(query, max_steps=max_steps)

    def default_tools(self):
        return {
            "current_time": {
                "description": "Get the current local date and time.",
                "args_schema": {},
                "handler": lambda args: _dt.datetime.now().strftime("%A, %Y-%m-%d %H:%M:%S"),
            },
            "calculate": {
                "description": "Safely evaluate arithmetic expressions only.",
                "args_schema": {"expression": "string"},
                "handler": lambda args: self._tool_calculate(args.get("expression", "")),
            },
            "remember": {
                "description": "Save an important user preference or fact to long-term memory.",
                "args_schema": {"text": "string"},
                "handler": lambda args: self._tool_remember(args.get("text", "")),
            },
            "recall_memory": {
                "description": "Search long-term memory for relevant past facts.",
                "args_schema": {"query": "string"},
                "handler": lambda args: self._tool_recall(args.get("query", "")),
            },
            "weather": {
                "description": "Get a concise weather summary for a location.",
                "args_schema": {"location": "string"},
                "handler": lambda args: self._tool_weather_live(args.get("location", "")),
            },
            "read_url": {
                "description": "Read the text content of a webpage to answer questions. Use this to read full articles and web pages after searching.",
                "args_schema": {"url": "string"},
                "handler": lambda args: self._tool_read_url(args.get("url", "")),
            },
            "sequential_thinking": {
                "description": "A tool for dynamic and reflective problem-solving through thoughts. Use this to break down complex problems, formulate hypotheses, or revise previous thoughts before taking actions like web searches. You can do this multiple times.",
                "args_schema": {"thought": "string", "thoughtNumber": "integer", "nextThoughtNeeded": "boolean"},
                "handler": lambda args: self._tool_sequential_thinking(args.get("thought", ""), args.get("thoughtNumber", 1), args.get("nextThoughtNeeded", False)),
            },
        }

    def tool_manifest(self, tools=None):
        """Returns UI-safe tool metadata without callable handlers."""
        tools = tools or self.default_tools()
        return [
            {
                "name": name,
                "description": spec.get("description", ""),
                "args_schema": spec.get("args_schema", {}),
            }
            for name, spec in tools.items()
        ]

    def _build_agent_prompt(self, query, tools, memories, transcript, context_override=None):
        tool_specs = []
        for name, spec in tools.items():
            tool_specs.append(
                {
                    "name": name,
                    "description": spec.get("description", ""),
                    "args_schema": spec.get("args_schema", {}),
                }
            )

        context_bits = []
        if memories:
            context_bits.append("Relevant memory:\n" + "\n".join(memories))
        if context_override:
            context_bits.append("Additional context:\n" + str(context_override))

        return f"""{self.system_prompt}

You are JARVIS, an advanced, autonomous deep-research AI assistant.
When faced with a complex user query, DO NOT answer immediately. Instead, use your `sequential_thinking` tool to:
1. Break down the problem into logical steps.
2. Formulate hypotheses about what you need to search for.
3. Track your thought process (thoughtNumber 1, 2, 3...).
4. Decide if you need more thoughts (`nextThoughtNeeded`: true).

After thinking, use `search_web` to find relevant information, and then strongly prefer using `read_url` to read the full content of those URLs rather than relying solely on snippets. 
You must iterate: Think -> Search -> Read -> Think again -> Conclude.
Never invent tool results. Return ONLY one valid JSON object in one of these forms:

{{"thought":"reasoning for this step","action":"tool_name","args":{{"key":"value"}}}}
{{"thought":"final conclusion","action":"final","answer":"comprehensive user-facing answer"}}

Available tools:
{json.dumps(tool_specs, indent=2)}

Context:
{self._truncate(chr(10).join(context_bits), 2000)}

Previous tool observations:
{json.dumps(transcript, indent=2)}

User request: {query}
"""

    def _parse_agent_decision(self, raw_response):
        if not raw_response:
            return None

        raw_response = raw_response.strip()
        try:
            return json.loads(raw_response)
        except Exception:
            pass

        json_match = re.search(r"\{.*\}", raw_response, re.DOTALL)
        if not json_match:
            return None

        try:
            return json.loads(json_match.group(0))
        except Exception:
            return None

    def _execute_tool(self, tool_spec, args):
        handler = tool_spec.get("handler")
        if not handler:
            return "Tool has no handler."
        try:
            return str(handler(args))
        except Exception as e:
            return f"Tool error: {e}"

    def _tool_calculate(self, expression):
        expression = str(expression).strip()
        if not expression:
            return "No expression provided."

        allowed_nodes = (
            ast.Expression,
            ast.BinOp,
            ast.UnaryOp,
            ast.Add,
            ast.Sub,
            ast.Mult,
            ast.Div,
            ast.FloorDiv,
            ast.Mod,
            ast.Pow,
            ast.USub,
            ast.UAdd,
            ast.Constant,
        )
        tree = ast.parse(expression, mode="eval")
        if not all(isinstance(node, allowed_nodes) for node in ast.walk(tree)):
            return "Only arithmetic expressions are allowed."
        return str(eval(compile(tree, "<calculator>", "eval"), {"__builtins__": {}}, {}))

    def _tool_remember(self, text):
        text = str(text).strip()
        if not text:
            return "Nothing to remember."
        if not self.memory:
            return "Memory is unavailable."
        self.memory.remember(text, metadata={"source": "agent"})
        return "Saved to memory."

    def _tool_recall(self, query):
        if not self.memory:
            return "Memory is unavailable."
        memories = self.memory.recall(str(query), n_results=5)
        return "\n".join(memories) if memories else "No relevant memories found."

    def _tool_search_live(self, query):
        query = str(query).strip()
        if not query:
            return "No search query provided."
        if requests is None:
            return "Web search is unavailable because requests is not installed."
        try:
            response = requests.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
                timeout=8,
            )
            response.raise_for_status()
            data = response.json()
            parts = []
            if data.get("AbstractText"):
                parts.append(data["AbstractText"])
            for topic in data.get("RelatedTopics", [])[:3]:
                if isinstance(topic, dict) and topic.get("Text"):
                    parts.append(topic["Text"])
            return "\n".join(parts) if parts else "No instant web result found."
        except Exception as e:
            return f"Web search failed: {e}"

    def _tool_weather_live(self, location):
        location = str(location).strip()
        if not location:
            return "No location provided."
        if requests is None:
            return "Weather lookup is unavailable because requests is not installed."
        try:
            response = requests.get(f"https://wttr.in/{location}", params={"format": "3"}, timeout=8)
            response.raise_for_status()
            return response.text.strip()
        except Exception as e:
            return f"Weather lookup failed: {e}"

    def _tool_read_url(self, url):
        url = str(url).strip()
        if not url:
            return "No URL provided."
        if requests is None:
            return "URL reading is unavailable because requests is not installed."
        try:
            from bs4 import BeautifulSoup
            # Add a user-agent to avoid basic blocks
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JARVIS/1.0"}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.extract()
            text = soup.get_text(separator=' ')
            # Collapse whitespace
            text = re.sub(r'\s+', ' ', text).strip()
            # Return first 8000 chars to allow deep reading
            return text[:8000]
        except Exception as e:
            return f"Failed to read URL: {e}"

    def _tool_sequential_thinking(self, thought, thought_number, next_thought_needed):
        # The agent uses this tool just to 'think' and record its train of thought in the transcript.
        status = "continue thinking" if next_thought_needed else "ready to act or conclude"
        return f"Thought #{thought_number} recorded. Status: {status}."

    def _truncate(self, text, limit):
        text = str(text or "")
        if len(text) <= limit:
            return text
        return text[: limit - 3] + "..."
