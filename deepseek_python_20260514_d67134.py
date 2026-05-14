"""
JARVIS Enhanced Memory System v1.0
Single-file drop-in replacement for basic ChromaDB memory

Place this file in your jarvis/modules/memory/ directory as enhanced_memory.py
Then replace your existing chroma.py imports with: from enhanced_memory import JarvisMemory

Requirements (add to your requirements.txt):
    pip install chromadb sentence-transformers torch scikit-learn numpy networkx
"""

import json
import os
import pickle
import hashlib
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict, field
from collections import defaultdict
import threading
import time
import logging

# Core imports
import chromadb
from chromadb.config import Settings
import numpy as np
from sentence_transformers import SentenceTransformer
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.metrics.pairwise import cosine_similarity
import networkx as nx

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class EpisodicMemory:
    """Single memory entry with full metadata"""
    id: str
    content: str
    embedding: Optional[np.ndarray] = None
    timestamp: float = field(default_factory=time.time)
    event_type: str = "conversation"  # conversation, action, error, success, fact, preference
    importance: float = 0.5  # 0-1, auto-calculated
    recall_count: int = 0
    last_recalled: Optional[float] = None
    emotional_valence: float = 0.0  # -1 (negative) to +1 (positive)
    linked_events: List[str] = field(default_factory=list)
    source: str = "user_conversation"
    tags: List[str] = field(default_factory=list)
    compressed_summary: Optional[str] = None
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        if self.embedding is not None:
            data['embedding'] = self.embedding.tolist()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict):
        if data.get('embedding'):
            data['embedding'] = np.array(data['embedding'])
        return cls(**data)


@dataclass
class UserModel:
    """Evolving user model for personalization"""
    identity: Dict[str, Any] = field(default_factory=dict)
    preferences: Dict[str, float] = field(default_factory=lambda: {
        "ui_theme": 1.0,  # 1=dark, 0=light
        "response_verbosity": 0.6,
        "humor_level": 0.3,
        "proactive_level": 0.7,
        "technical_explanation_depth": 0.6
    })
    behavioral_patterns: Dict[str, Any] = field(default_factory=lambda: {
        "peak_hours": [],
        "common_tasks": defaultdict(int),
        "interruption_tolerance": 0.5,
        "response_times": []
    })
    knowledge_state: Dict[str, float] = field(default_factory=dict)
    mood_trend: List[float] = field(default_factory=list)  # Recent valence scores
    
    def update_from_interaction(self, interaction_type: str, feedback: float = 0):
        """Update model based on interaction feedback"""
        if interaction_type == "positive_feedback":
            self.preferences["response_verbosity"] = min(1.0, self.preferences["response_verbosity"] + 0.01)
        elif interaction_type == "negative_feedback":
            self.preferences["response_verbosity"] = max(0.2, self.preferences["response_verbosity"] - 0.01)


# ============================================================================
# NEURAL NETWORK MODELS (Small, CPU-only)
# ============================================================================

class ImportancePredictor(nn.Module):
    """Predicts importance of a memory from its embedding"""
    def __init__(self, embedding_dim: int = 384):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(embedding_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
            nn.Sigmoid()
        )
    
    def forward(self, x):
        return self.net(x)


class EmotionDetector(nn.Module):
    """Detects emotional valence from embeddings"""
    def __init__(self, embedding_dim: int = 384):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(embedding_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
            nn.Tanh()  # Output range -1 to +1
        )
    
    def forward(self, x):
        return self.net(x)


class IntentClassifier(nn.Module):
    """Fast pre-LLM intent routing"""
    def __init__(self, embedding_dim: int = 384, num_intents: int = 8):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(embedding_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, num_intents)
        )
    
    def forward(self, x):
        return F.softmax(self.net(x), dim=-1)


# ============================================================================
# MAIN MEMORY SYSTEM
# ============================================================================

class JarvisMemory:
    """
    Enhanced memory system for JARVIS with:
    - Episodic memory with importance scoring
    - Temporal decay and forgetting
    - Associative memory graph
    - User modeling
    - Neural network-based importance prediction
    - Auto-compression of old memories
    """
    
    def __init__(self, 
                 persist_directory: str = "./jarvis_memory_enhanced",
                 embedding_model: str = "all-MiniLM-L6-v2",
                 auto_train: bool = True):
        
        # Initialize ChromaDB
        self.persist_directory = persist_directory
        os.makedirs(persist_directory, exist_ok=True)
        
        self.chroma_client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Create collections
        self.memories_collection = self.chroma_client.get_or_create_collection(
            name="episodic_memories"
        )
        self.graph_collection = self.chroma_client.get_or_create_collection(
            name="memory_graph"
        )
        
        # Embedding model
        self.embedder = SentenceTransformer(embedding_model)
        self.embedding_dim = self.embedder.get_sentence_embedding_dimension()
        
        # Neural networks
        self.importance_predictor = ImportancePredictor(self.embedding_dim)
        self.intent_classifier = IntentClassifier(self.embedding_dim)
        self.emotion_detector = EmotionDetector(self.embedding_dim)
        
        # Intent labels
        self.intents = ["conversation", "question", "fact", "preference", "action", "error", "code", "correction"]
        
        # Storage for memory objects (not just vectors)
        self.memory_store: Dict[str, EpisodicMemory] = {}
        
        # User model
        self.user_model = UserModel()
        
        # Memory graph (associative network)
        self.memory_graph = nx.Graph()
        
        # Cache for recent memories
        self.working_memory: List[EpisodicMemory] = []  # Last 10 interactions
        self.episodic_buffer: List[EpisodicMemory] = []  # Last 100
        
        # Configuration
        self.config = {
            "working_memory_size": 10,
            "episodic_buffer_size": 100,
            "importance_threshold_for_deletion": 0.3,
            "forgetting_days": 30,
            "auto_compress_days": 7,
            "graph_association_strength": 0.7
        }
        
        # Load existing memories if any
        self._load_memories()
        
        # Background task for maintenance
        self.auto_train = auto_train
        if auto_train:
            self._start_background_tasks()
        
        logger.info("JarvisMemory initialized with enhanced features")
    
    def _load_memories(self):
        """Load memories from disk"""
        memory_file = os.path.join(self.persist_directory, "memory_store.pkl")
        user_model_file = os.path.join(self.persist_directory, "user_model.pkl")
        graph_file = os.path.join(self.persist_directory, "memory_graph.pkl")
        
        if os.path.exists(memory_file):
            with open(memory_file, 'rb') as f:
                raw_memories = pickle.load(f)
                for mem_data in raw_memories:
                    mem = EpisodicMemory.from_dict(mem_data)
                    self.memory_store[mem.id] = mem
        
        if os.path.exists(user_model_file):
            with open(user_model_file, 'rb') as f:
                self.user_model = pickle.load(f)
        
        if os.path.exists(graph_file):
            with open(graph_file, 'rb') as f:
                self.memory_graph = pickle.load(f)
        
        # Rebuild working memory from recent memories
        self._rebuild_working_memory()
    
    def _save_memories(self):
        """Save memories to disk"""
        memory_file = os.path.join(self.persist_directory, "memory_store.pkl")
        user_model_file = os.path.join(self.persist_directory, "user_model.pkl")
        graph_file = os.path.join(self.persist_directory, "memory_graph.pkl")
        
        with open(memory_file, 'wb') as f:
            pickle.dump([mem.to_dict() for mem in self.memory_store.values()], f)
        
        with open(user_model_file, 'wb') as f:
            pickle.dump(self.user_model, f)
        
        with open(graph_file, 'wb') as f:
            pickle.dump(self.memory_graph, f)
    
    def _rebuild_working_memory(self):
        """Rebuild working memory from most recent memories"""
        sorted_memories = sorted(
            self.memory_store.values(),
            key=lambda x: x.timestamp,
            reverse=True
        )
        self.working_memory = sorted_memories[:self.config["working_memory_size"]]
        self.episodic_buffer = sorted_memories[:self.config["episodic_buffer_size"]]
    
    def _start_background_tasks(self):
        """Start background maintenance tasks"""
        def maintenance_loop():
            while True:
                time.sleep(3600)  # Run every hour
                self._prune_memories()
                self._compress_old_memories()
                self._update_user_model()
        
        thread = threading.Thread(target=maintenance_loop, daemon=True)
        thread.start()
    
    def _calculate_importance(self, content: str, embedding: np.ndarray, event_type: str) -> float:
        """Calculate importance score using neural network + heuristics"""
        # NN prediction
        with torch.no_grad():
            tensor_embedding = torch.tensor(embedding, dtype=torch.float32).unsqueeze(0)
            nn_score = self.importance_predictor(tensor_embedding).item()
        
        # Heuristics
        heuristics = 0.5
        
        # Longer content might be more important
        if len(content) > 200:
            heuristics += 0.1
        if len(content) > 500:
            heuristics += 0.1
        
        # Certain event types are more important
        importance_weights = {
            "error": 0.8,
            "success": 0.7,
            "preference": 0.8,
            "fact": 0.7,
            "action": 0.5,
            "conversation": 0.4
        }
        heuristics += importance_weights.get(event_type, 0.4) - 0.5
        
        # Combine
        final_score = 0.6 * nn_score + 0.4 * heuristics
        return min(1.0, max(0.1, final_score))
    
    def _calculate_emotional_valence(self, content: str) -> float:
        """Simple sentiment analysis using word lists (fallback until NN is trained)"""
        positive_words = ["good", "great", "excellent", "amazing", "love", "happy", "thanks", "perfect"]
        negative_words = ["bad", "terrible", "awful", "hate", "annoying", "frustrating", "error", "fail", "wrong"]
        
        content_lower = content.lower()
        pos_score = sum(content_lower.count(word) for word in positive_words)
        neg_score = sum(content_lower.count(word) for word in negative_words)
        
        total = pos_score + neg_score
        if total == 0:
            return 0.0
        
        return (pos_score - neg_score) / total
    
    def add_memory(self, 
                   content: str, 
                   event_type: str = "conversation",
                   tags: List[str] = None,
                   source: str = "user_conversation",
                   user_feedback: Optional[float] = None) -> str:
        """
        Add a new memory to the system.
        
        Args:
            content: Text content to remember
            event_type: Type of event (conversation, action, error, etc.)
            tags: Optional tags for categorization
            source: Source of the memory
            user_feedback: If provided, adjusts importance
        
        Returns:
            memory_id: Unique identifier for this memory
        """
        # Generate embedding
        embedding = self.embedder.encode(content)
        
        # Generate unique ID
        memory_id = hashlib.md5(f"{content}{time.time()}{event_type}".encode()).hexdigest()[:16]
        
        # Calculate importance
        importance = self._calculate_importance(content, embedding, event_type)
        if user_feedback:
            importance = 0.7 * importance + 0.3 * user_feedback
        
        # Calculate emotional valence using NN
        with torch.no_grad():
            tensor_embedding = torch.tensor(embedding, dtype=torch.float32).unsqueeze(0)
            valence = self.emotion_detector(tensor_embedding).item()
            
        # Predict intent if default is used
        if event_type == "conversation":
            with torch.no_grad():
                intent_probs = self.intent_classifier(tensor_embedding)
                intent_idx = torch.argmax(intent_probs).item()
                predicted_event_type = self.intents[intent_idx]
                if predicted_event_type != "conversation":
                    event_type = predicted_event_type
        
        # Create memory
        memory = EpisodicMemory(
            id=memory_id,
            content=content,
            embedding=embedding,
            timestamp=time.time(),
            event_type=event_type,
            importance=importance,
            emotional_valence=valence,
            tags=tags or [],
            source=source
        )
        
        # Store in memory store
        self.memory_store[memory_id] = memory
        
        # Store in ChromaDB
        self.memories_collection.add(
            embeddings=[embedding.tolist()],
            documents=[content],
            metadatas=[{
                "memory_id": memory_id,
                "timestamp": memory.timestamp,
                "event_type": event_type,
                "importance": importance,
                "valence": valence
            }],
            ids=[memory_id]
        )
        
        # Update working memory
        self.working_memory.insert(0, memory)
        if len(self.working_memory) > self.config["working_memory_size"]:
            self.working_memory = self.working_memory[:self.config["working_memory_size"]]
        
        self.episodic_buffer.insert(0, memory)
        if len(self.episodic_buffer) > self.config["episodic_buffer_size"]:
            self.episodic_buffer = self.episodic_buffer[:self.config["episodic_buffer_size"]]
        
        # Create graph associations with existing memories
        self._create_associations(memory)
        
        # Save
        self._save_memories()
        
        logger.info(f"Added memory {memory_id}: {content[:50]}... (importance={importance:.2f})")
        return memory_id
    
    def _create_associations(self, memory: EpisodicMemory):
        """Create associative links between this memory and similar ones"""
        # Find similar memories
        similar = self.search_memories(
            query=memory.content,
            n_results=5,
            min_importance=0.4
        )
        
        # Create graph edges
        for sim_mem in similar:
            if sim_mem.id != memory.id:
                similarity = cosine_similarity(
                    [memory.embedding],
                    [sim_mem.embedding]
                )[0][0]
                
                if similarity > self.config["graph_association_strength"]:
                    self.memory_graph.add_edge(
                        memory.id, 
                        sim_mem.id,
                        weight=similarity,
                        created_at=time.time()
                    )
                    memory.linked_events.append(sim_mem.id)
                    sim_mem.linked_events.append(memory.id)
    
    def recall(self, memory_id: str) -> Optional[EpisodicMemory]:
        """Recall a specific memory by ID"""
        if memory_id in self.memory_store:
            memory = self.memory_store[memory_id]
            memory.recall_count += 1
            memory.last_recalled = time.time()
            self._save_memories()
            return memory
        return None
    
    def search_memories(self, 
                        query: str, 
                        n_results: int = 5,
                        min_importance: float = 0.0,
                        max_age_days: Optional[int] = None,
                        event_type: Optional[str] = None) -> List[EpisodicMemory]:
        """
        Search memories semantically with filters.
        
        Args:
            query: Search query
            n_results: Number of results to return
            min_importance: Minimum importance score
            max_age_days: Maximum age in days
            event_type: Filter by event type
        
        Returns:
            List of matching memories
        """
        # Encode query
        query_embedding = self.embedder.encode(query)
        
        # Search ChromaDB
        results = self.memories_collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=n_results * 2  # Get extra for filtering
        )
        
        # Process results
        memories = []
        current_time = time.time()
        
        for i, mem_id in enumerate(results['ids'][0]):
            if mem_id not in self.memory_store:
                continue
            
            memory = self.memory_store[mem_id]
            
            # Apply filters
            if memory.importance < min_importance:
                continue
            
            if max_age_days:
                age_days = (current_time - memory.timestamp) / 86400
                if age_days > max_age_days:
                    continue
            
            if event_type and memory.event_type != event_type:
                continue
            
            memories.append(memory)
            
            if len(memories) >= n_results:
                break
        
        # Update recall counts
        for mem in memories:
            mem.recall_count += 1
            mem.last_recalled = current_time
        
        self._save_memories()
        
        return memories
    
    def get_context_for_llm(self, 
                            current_input: str, 
                            n_memories: int = 5,
                            include_working_memory: bool = True) -> str:
        """
        Get formatted context for LLM injection.
        This is the main method you call before every LLM query.
        
        Args:
            current_input: User's current query
            n_memories: Number of relevant memories to retrieve
            include_working_memory: Include recent conversation history
        
        Returns:
            Formatted context string for system prompt
        """
        context_parts = []
        
        # 1. Working memory (recent conversation)
        if include_working_memory and self.working_memory:
            context_parts.append("## RECENT CONVERSATION")
            for mem in self.working_memory[:5]:  # Last 5 exchanges
                date_str = datetime.fromtimestamp(mem.timestamp).strftime("%H:%M")
                context_parts.append(f"[{date_str}] {mem.content[:200]}")
        
        # 2. Relevant long-term memories
        relevant = self.search_memories(
            query=current_input,
            n_results=n_memories,
            min_importance=0.4
        )
        
        if relevant:
            context_parts.append("\n## RELEVANT MEMORIES")
            for mem in relevant:
                # Apply temporal decay for context
                age_days = (time.time() - mem.timestamp) / 86400
                decay = 0.9 ** age_days  # Exponential decay
                effective_importance = mem.importance * decay
                
                if effective_importance > 0.3:
                    date_str = datetime.fromtimestamp(mem.timestamp).strftime("%Y-%m-%d")
                    context_parts.append(f"- [{date_str}] {mem.content}")
        
        # 3. User preferences (from user model)
        prefs = []
        if self.user_model.preferences.get("ui_theme", 1.0) > 0.5:
            prefs.append("prefers dark theme")
        if self.user_model.preferences.get("response_verbosity", 0.6) < 0.4:
            prefs.append("prefers concise responses")
        elif self.user_model.preferences.get("response_verbosity", 0.6) > 0.7:
            prefs.append("appreciates detailed explanations")
        
        if prefs:
            context_parts.append(f"\n## USER PREFERENCES\n{', '.join(prefs)}")
        
        return "\n".join(context_parts)
    
    def forget(self, memory_id: str):
        """Delete a memory"""
        if memory_id in self.memory_store:
            del self.memory_store[memory_id]
            self.memories_collection.delete(ids=[memory_id])
            self.memory_graph.remove_node(memory_id)
            self._save_memories()
            logger.info(f"Forgot memory {memory_id}")
    
    def _prune_memories(self):
        """Remove unimportant old memories"""
        current_time = time.time()
        to_delete = []
        
        for mem_id, memory in self.memory_store.items():
            age_days = (current_time - memory.timestamp) / 86400
            
            # Calculate forget probability using Ebbinghaus curve
            recall_probability = 0.5 ** (age_days / memory.importance)
            
            # Apply importance threshold
            if memory.importance < self.config["importance_threshold_for_deletion"]:
                if age_days > self.config["forgetting_days"]:
                    to_delete.append(mem_id)
            elif recall_probability < 0.1 and age_days > self.config["forgetting_days"] * 2:
                to_delete.append(mem_id)
        
        for mem_id in to_delete:
            self.forget(mem_id)
        
        if to_delete:
            logger.info(f"Pruned {len(to_delete)} memories")
    
    def _compress_old_memories(self):
        """Compress old memories into summaries"""
        current_time = time.time()
        
        for mem_id, memory in list(self.memory_store.items()):
            age_days = (current_time - memory.timestamp) / 86400
            
            if age_days > self.config["auto_compress_days"] and not memory.compressed_summary:
                # Generate summary using simple truncation + key extraction
                words = memory.content.split()
                if len(words) > 50:
                    # Extract key sentences (simple heuristic)
                    sentences = memory.content.split('.')
                    key_sentences = sentences[:3]  # First 3 sentences
                    memory.compressed_summary = '. '.join(key_sentences) + '...'
                else:
                    memory.compressed_summary = memory.content
        
        self._save_memories()
    
    def _update_user_model(self):
        """Update user model based on interaction patterns"""
        # Analyze response times
        # Analyze common tasks from memory tags
        task_counts = defaultdict(int)
        for memory in self.memory_store.values():
            for tag in memory.tags:
                task_counts[tag] += 1
        
        # Update top 5 common tasks
        self.user_model.behavioral_patterns["common_tasks"] = dict(
            sorted(task_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        )
        
        # Update peak hours from timestamps
        hour_counts = defaultdict(int)
        for memory in self.memory_store.values():
            hour = datetime.fromtimestamp(memory.timestamp).hour
            hour_counts[hour] += 1
        
        # Get top 3 peak hours
        peak_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        self.user_model.behavioral_patterns["peak_hours"] = [h for h, _ in peak_hours]
        
        # Update mood trend from recent memories
        recent_memories = sorted(self.memory_store.values(), key=lambda x: x.timestamp, reverse=True)[:50]
        if recent_memories:
            self.user_model.mood_trend = [m.emotional_valence for m in recent_memories]
        
        # Update knowledge state (topics user is interested in)
        for memory in recent_memories:
            for tag in memory.tags:
                current_val = self.user_model.knowledge_state.get(tag, 0.5)
                # Boost knowledge level if frequently mentioned
                self.user_model.knowledge_state[tag] = min(1.0, current_val + 0.05)
        
        self._save_memories()
    
    def get_user_context_summary(self) -> str:
        """Get a summary of the user model for system prompt"""
        summary_parts = []
        
        # Identity
        if self.user_model.identity.get("name"):
            summary_parts.append(f"User name: {self.user_model.identity['name']}")
        
        # Peak hours
        if self.user_model.behavioral_patterns["peak_hours"]:
            hours = self.user_model.behavioral_patterns["peak_hours"]
            summary_parts.append(f"Most active hours: {', '.join(str(h) for h in hours)}:00")
        
        # Common tasks
        if self.user_model.behavioral_patterns["common_tasks"]:
            tasks = list(self.user_model.behavioral_patterns["common_tasks"].items())[:3]
            task_str = ", ".join(f"{task} ({count} times)" for task, count in tasks)
            summary_parts.append(f"Common tasks: {task_str}")
        
        return "\n".join(summary_parts)
    
    def learn_from_feedback(self, memory_id: str, feedback: str):
        """
        Learn from user feedback to improve memory importance.
        
        Args:
            memory_id: ID of the memory being evaluated
            feedback: "positive", "negative", or "neutral"
        """
        if memory_id not in self.memory_store:
            return
        
        memory = self.memory_store[memory_id]
        
        if feedback == "positive":
            memory.importance = min(1.0, memory.importance + 0.15)
            self.user_model.update_from_interaction("positive_feedback")
        elif feedback == "negative":
            memory.importance = max(0.1, memory.importance - 0.15)
            self.user_model.update_from_interaction("negative_feedback")
        
        # Update in ChromaDB
        self.memories_collection.update(
            ids=[memory_id],
            metadatas=[{
                "memory_id": memory.id,
                "timestamp": memory.timestamp,
                "event_type": memory.event_type,
                "importance": memory.importance,
                "valence": memory.emotional_valence
            }]
        )
        
        self._save_memories()
        logger.info(f"Updated memory {memory_id} importance to {memory.importance:.2f}")
    
    def get_memory_statistics(self) -> Dict:
        """Get statistics about memory system"""
        total = len(self.memory_store)
        
        if total == 0:
            return {"total_memories": 0}
        
        avg_importance = np.mean([m.importance for m in self.memory_store.values()])
        avg_impressions = np.mean([m.recall_count for m in self.memory_store.values()])
        
        type_counts = defaultdict(int)
        for m in self.memory_store.values():
            type_counts[m.event_type] += 1
        
        return {
            "total_memories": total,
            "average_importance": float(avg_importance),
            "average_recalls": float(avg_impressions),
            "memories_by_type": dict(type_counts),
            "graph_edges": self.memory_graph.number_of_edges(),
            "working_memory_count": len(self.working_memory)
        }
    
    def get_proactive_suggestion(self) -> Optional[str]:
        """
        Generate a proactive suggestion based on memory patterns.
        Called periodically by the main loop.
        """
        current_hour = datetime.now().hour
        
        # Check if we're in peak hours
        if current_hour in self.user_model.behavioral_patterns["peak_hours"]:
            # Find most common task at this hour
            common_tasks = self.user_model.behavioral_patterns.get("common_tasks", {})
            if common_tasks:
                top_task = max(common_tasks.items(), key=lambda x: x[1])[0]
                return f"You usually work on {top_task} around this time. Ready to continue?"
        
        # Check for pending tasks in memory
        pending_keywords = ["todo", "need to", "should", "remember to"]
        pending_tasks = []
        
        for memory in self.memory_store.values():
            if any(keyword in memory.content.lower() for keyword in pending_keywords):
                age_days = (time.time() - memory.timestamp) / 86400
                if age_days < 3:  # Recent todos
                    pending_tasks.append(memory.content[:100])
        
        if pending_tasks:
            return f"By the way, you had these pending items: {pending_tasks[0]}"
        
        # Check mood trend
        if self.user_model.mood_trend:
            avg_mood = np.mean(self.user_model.mood_trend[-5:])
            if avg_mood < -0.3:
                return "You seem a bit frustrated lately. Would you like to take a break or should I simplify my responses?"
        
        # Knowledge-based suggestion
        if self.user_model.knowledge_state:
            top_topic = max(self.user_model.knowledge_state.items(), key=lambda x: x[1])
            if top_topic[1] > 0.8:
                return f"I've noticed you're working a lot with {top_topic[0]}. I can find more advanced resources on this if you'd like."
        
        return None
    
    def train_models(self, training_data: List[Dict[str, Any]]):
        """
        Train all NNs on labeled data.
        
        Args:
            training_data: List of dicts with 'content', 'importance', 'intent', 'valence'
        """
        if not training_data:
            return
        
        texts = [d['content'] for d in training_data]
        embeddings = self.embedder.encode(texts)
        X = torch.tensor(embeddings, dtype=torch.float32)
        
        # 1. Train Importance Predictor
        if 'importance' in training_data[0]:
            y_imp = torch.tensor([d['importance'] for d in training_data], dtype=torch.float32).unsqueeze(1)
            self._train_step(self.importance_predictor, X, y_imp, nn.MSELoss())
            
        # 2. Train Emotion Detector
        if 'valence' in training_data[0]:
            y_val = torch.tensor([d['valence'] for d in training_data], dtype=torch.float32).unsqueeze(1)
            self._train_step(self.emotion_detector, X, y_val, nn.MSELoss())
            
        # 3. Train Intent Classifier
        if 'intent' in training_data[0]:
            intent_indices = []
            for d in training_data:
                try:
                    idx = self.intents.index(d['intent'])
                except ValueError:
                    idx = 0  # Default to conversation
                intent_indices.append(idx)
            y_int = torch.tensor(intent_indices, dtype=torch.long)
            self._train_step(self.intent_classifier, X, y_int, nn.CrossEntropyLoss())
            
        logger.info(f"Trained all models on {len(training_data)} samples")

    def _train_step(self, model, X, y, loss_fn, epochs=50):
        """Helper for a single training loop"""
        optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
        model.train()
        for _ in range(epochs):
            optimizer.zero_grad()
            pred = model(X)
            loss = loss_fn(pred, y)
            loss.backward()
            optimizer.step()
        
        logger.info(f"Training completed for {model.__class__.__name__}")
    
    def get_associative_chain(self, start_memory_id: str, max_depth: int = 3) -> List[EpisodicMemory]:
        """
        Get chain of associated memories (for narrative recall)
        
        Args:
            start_memory_id: Starting memory ID
            max_depth: How deep to traverse
        
        Returns:
            List of memories in association order
        """
        if start_memory_id not in self.memory_graph:
            return []
        
        # BFS to find associative chain
        visited = set()
        chain = []
        queue = [(start_memory_id, 0)]
        
        while queue and len(chain) < max_depth:
            mem_id, depth = queue.pop(0)
            if mem_id in visited:
                continue
            
            visited.add(mem_id)
            memory = self.recall(mem_id)
            if memory:
                chain.append(memory)
            
            if depth < max_depth - 1:
                neighbors = list(self.memory_graph.neighbors(mem_id))
                for neighbor in neighbors[:3]:  # Limit branching
                    if neighbor not in visited:
                        queue.append((neighbor, depth + 1))
        
        return chain


# ============================================================================
# CONVENIENCE FUNCTIONS FOR MAIN AGENT
# ============================================================================

class JarvisMemoryManager:
    """
    Singleton wrapper for easy integration into your main agent.
    Just import and use: memory = JarvisMemoryManager.get_instance()
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.memory = JarvisMemory()
        self._initialized = True
        logger.info("JarvisMemoryManager initialized")
    
    def remember(self, content: str, event_type: str = "conversation", tags: List[str] = None):
        """Add a memory"""
        return self.memory.add_memory(content, event_type, tags)
    
    def recall_relevant(self, query: str, n: int = 5) -> str:
        """Get context for LLM"""
        return self.memory.get_context_for_llm(query, n)
    
    def get_proactive_suggestion(self) -> Optional[str]:
        """Get a proactive suggestion"""
        return self.memory.get_proactive_suggestion()
    
    def learn(self, memory_id: str, feedback: str):
        """Learn from feedback"""
        self.memory.learn_from_feedback(memory_id, feedback)
    
    def get_stats(self) -> Dict:
        """Get statistics"""
        return self.memory.get_memory_statistics()


# ============================================================================
# EXAMPLE USAGE IN YOUR MAIN AGENT
# ============================================================================

"""
HOW TO INTEGRATE INTO YOUR EXISTING JARVIS:

1. Replace your old memory import:
   # from modules.memory.chroma import MemorySystem
   from enhanced_memory import JarvisMemoryManager, JarvisMemory

2. Initialize at startup:
   memory = JarvisMemoryManager()
   
   # Or for more control:
   memory_system = JarvisMemory(persist_directory="./jarvis_memory_enhanced")

3. Before every LLM call:
   context = memory_system.get_context_for_llm(user_input)
   system_prompt = f"You are JARVIS. Here is context:\n{context}\n\nRespond to: {user_input}"

4. After each interaction, store the exchange:
   memory_system.add_memory(
       content=f"User said: {user_input}\nJARVIS responded: {response}",
       event_type="conversation"
   )

5. Store facts explicitly:
   memory_system.add_memory(
       content=f"User prefers {preference}",
       event_type="preference",
       tags=["preference"]
   )

6. For proactive suggestions (call every few minutes):
   suggestion = memory_system.get_proactive_suggestion()
   if suggestion:
       print(f"[PROACTIVE] {suggestion}")

7. Get statistics for HUD:
   stats = memory_system.get_memory_statistics()
   # Show in your PyQt6 overlay
"""


if __name__ == "__main__":
    # Test the system
    print("Testing Jarvis Enhanced Memory System v1.1...")
    
    # Initialize
    memory_sys = JarvisMemory(persist_directory="./test_memory")
    
    # 1. Train models with some synthetic data
    print("\nTraining models on synthetic data...")
    synthetic_data = [
        {"content": "Set the lights to blue", "importance": 0.5, "intent": "action", "valence": 0.2},
        {"content": "What is the square root of 256?", "importance": 0.4, "intent": "question", "valence": 0.0},
        {"content": "I am so annoyed with this error", "importance": 0.8, "intent": "error", "valence": -0.8},
        {"content": "Great job JARVIS, this is perfect", "importance": 0.7, "intent": "conversation", "valence": 0.9},
        {"content": "The project deadline is June 15th", "importance": 0.9, "intent": "fact", "valence": 0.1},
        {"content": "I prefer using Python for data analysis", "importance": 0.6, "intent": "preference", "valence": 0.3},
    ]
    memory_sys.train_models(synthetic_data)
    
    # 2. Add memories and test auto-categorization
    print("\nAdding memories (testing auto-categorization)...")
    memory_sys.add_memory("I really hate it when the build fails like this") # Should be error/negative
    memory_sys.add_memory("Remind me to buy milk later") # Should be conversation/action
    memory_sys.add_memory("This new feature is absolutely amazing, I love it!") # Should be conversation/positive
    
    # 3. Search
    print("\nSearching memories...")
    results = memory_sys.search_memories("how does the user feel?")
    for r in results:
        print(f"  - [{r.event_type}] {r.content[:50]}... (valence={r.emotional_valence:.2f})")
    
    # 4. Proactive suggestion
    # Trigger a mood-based suggestion by adding more negative memories
    for _ in range(5):
        memory_sys.add_memory("I'm feeling very stressed and overwhelmed", event_type="conversation")
    
    memory_sys._update_user_model()
    suggestion = memory_sys.get_proactive_suggestion()
    if suggestion:
        print(f"\nProactive suggestion: {suggestion}")
    
    # 5. Statistics
    stats = memory_sys.get_memory_statistics()
    print(f"\nMemory stats: {stats}")
    
    print("\nTest complete! System v1.1 ready.")