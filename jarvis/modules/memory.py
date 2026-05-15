"""
JARVIS Memory Module Bridge
Connects the core engine to the Enhanced Memory System.
"""
import os
import logging
from jarvis.modules.memory.enhanced_memory import JarvisMemoryManager

logger = logging.getLogger(__name__)

class MemorySystem:
    """
    Bridge class for compatibility with existing JARVIS core code.
    Wraps the JarvisMemoryManager (v1.1) which handles neural classification,
    associative graphs, and proactive modeling.
    """
    def __init__(self, config=None):
        # We use a singleton manager to ensure consistency across the app
        self.manager = JarvisMemoryManager()
        logger.info("[JARVIS] Enhanced Memory System Bridge initialized.")

    def remember(self, text, metadata=None):
        """Stores a string of text in the long-term vector database."""
        # Note: The new system handles importance and intent auto-detection
        event_type = "conversation"
        if metadata and "event_type" in metadata:
            event_type = metadata["event_type"]
        
        return self.manager.remember(text, event_type=event_type)

    def recall(self, query, n_results=5):
        """Retrieves top n_results most relevant memories based on the query."""
        return self.manager.recall(query, n_results=n_results)

    def get_context(self, query, n=5):
        """Returns a pre-formatted context string for LLM injection."""
        return self.manager.get_context(query, n)

    def stats(self):
        """Returns memory health information for the UI."""
        raw_stats = self.manager.get_stats()
        return {
            "available": True,
            "count": raw_stats["total_entries"],
            "working_size": raw_stats["working_size"],
            "graph_edges": raw_stats["graph_edges"]
        }
    
    def get_proactive_suggestion(self):
        """Polls for any proactive system suggestions."""
        return self.manager.get_proactive_suggestion()
