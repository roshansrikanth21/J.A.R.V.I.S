import os
import time
try:
    import chromadb
    from sentence_transformers import SentenceTransformer
except ImportError:
    pass

class MemorySystem:
    def __init__(self, config):
        self.config = config.get("memory", {})
        db_path = self.config.get("db_path", "./memory/chroma_db")
        model_name = self.config.get("embedding_model", "all-MiniLM-L6-v2")
        
        os.makedirs(db_path, exist_ok=True)
        print("[JARVIS] Initializing memory embeddings...")
        
        try:
            import chromadb.config
            self.embed_model = SentenceTransformer(model_name)
            self.client = chromadb.PersistentClient(
                path=db_path,
                settings=chromadb.config.Settings(anonymized_telemetry=False)
            )
            self.collection = self.client.get_or_create_collection("jarvis_memories")
        except Exception as e:
            print(f"[WARN] Memory init failed: {e}")
            self.collection = None

    def remember(self, text, metadata=None):
        """Stores a string of text in the long-term vector database."""
        if not self.collection:
            return
            
        if metadata is None:
            metadata = {}
        metadata["timestamp"] = str(time.time())
        
        try:
            embedding = self.embed_model.encode(text).tolist()
            doc_id = str(time.time_ns())
            
            self.collection.add(
                embeddings=[embedding],
                documents=[text],
                ids=[doc_id],
                metadatas=[metadata]
            )
            print(f"[JARVIS] Memorized: {text[:30]}...")
        except Exception as e:
            print(f"[WARN] Failed to remember: {e}")

    def recall(self, query, n_results=5):
        """Retrieves top n_results most relevant memories based on the query."""
        if not self.collection or not query:
            return []
            
        try:
            q_embed = self.embed_model.encode(query).tolist()
            results = self.collection.query(
                query_embeddings=[q_embed],
                n_results=n_results
            )
            
            if results and results.get("documents") and len(results["documents"]) > 0:
                return results["documents"][0]
            return []
        except Exception as e:
            print(f"[WARN] Recall failed: {e}")
            return []

    def stats(self):
        """Returns lightweight memory health information for the UI."""
        if not self.collection:
            return {"available": False, "count": 0}

        try:
            return {"available": True, "count": self.collection.count()}
        except Exception as e:
            return {"available": False, "count": 0, "error": str(e)}
