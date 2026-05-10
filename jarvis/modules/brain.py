import json
try:
    import ollama
    import anthropic
except ImportError:
    pass

class Brain:
    def __init__(self, config, memory_system):
        self.config = config.get("brain", {})
        self.memory = memory_system
        self.primary_llm = self.config.get("primary_llm", "local")
        self.local_model = self.config.get("local_model", "llama3.1:8b-instruct-q4_K_M")
        
        # Load system prompt
        self.system_prompt = "You are JARVIS. Answer concisely."
        try:
            with open("prompts/system_prompt.txt", "r", encoding="utf-8") as f:
                self.system_prompt = f.read()
        except:
            pass

    def ask(self, query, context_override=None):
        """Standard conversational query with memory context injected."""
        context_str = ""
        
        # Retrieve memories
        if self.memory:
            memories = self.memory.recall(query)
            if memories:
                context_str = "\nRelevant past memories:\n" + "\n".join(memories)
                
        if context_override:
            context_str += f"\nAdditional Context:\n{context_override}"

        full_prompt = f"{self.system_prompt}\n{context_str}\n\nUser: {query}\nJARVIS:"

        if self.primary_llm == "local":
            return self._ask_ollama(full_prompt)
        else:
            return self._ask_claude(full_prompt)

    def _ask_ollama(self, prompt):
        try:
            response = ollama.generate(model=self.local_model, prompt=prompt)
            return response['response'].strip()
        except Exception as e:
            print(f"[OLLAMA ERROR] Is Ollama running? {e}")
            return "I am currently offline. Please start the Ollama server."

    def _ask_claude(self, prompt):
        api_key = self.config.get("anthropic_api_key")
        if not api_key or api_key == "YOUR_ANTHROPIC_KEY":
            return "My cloud brain is disconnected. API key is missing."
            
        try:
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model=self.config.get("cloud_model", "claude-3-5-sonnet-20240620"),
                max_tokens=512,
                system=self.system_prompt,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text.strip()
        except Exception as e:
            return f"Cloud error: {str(e)}"

    def parse_intent(self, text):
        """Ask LLM to classify intent into JSON for Tool Calling."""
        schema = '''
        Analyze the text. If it is a conversational request, return {"action": "chat"}.
        If it requires opening an app, return {"action": "open_app", "args": {"app_name": "name"}}.
        If it requires looking at screen, return {"action": "vision"}.
        If it requires pasting a prompt, return {"action": "paste_prompt", "args": {"prompt_name": "name"}}.
        If it requires sending a WhatsApp message, return {"action": "send_whatsapp", "args": {"phone": "number", "message": "text"}}.
        If it requires playing a YouTube video, return {"action": "play_youtube", "args": {"query": "search term"}}.
        If it requires getting the news, return {"action": "get_news"}.
        If it requires system power control (shutdown, restart, logout), return {"action": "system_control", "args": {"command": "restart|shutdown|logout"}}.
        Respond ONLY in valid JSON format.
        '''
        prompt = f"Text: {text}\nSchema instructions: {schema}"
        try:
            res = self._ask_ollama(prompt)
            # Find json block
            import re
            json_str = re.search(r'\{.*\}', res, re.DOTALL)
            if json_str:
                return json.loads(json_str.group(0))
            return {"action": "chat"}
        except Exception:
            return {"action": "chat"}
