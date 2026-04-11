import json
import os
from typing import Optional, List
from pathlib import Path

import chromadb

from core.logger import get_logger

logger = get_logger(__name__)


class KnowledgeBase:
    """Vector database for storing and retrieving chat transcripts."""

    def __init__(self, db_path: str = "./.chroma_db"):
        """Initialize Chroma vector database."""
        self.db_path = db_path
        os.makedirs(db_path, exist_ok=True)
        
        # Use new Chroma API (v0.4+)
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(
            name="tech_support_kb",
            metadata={"hnsw:space": "cosine"},
        )
        
        logger.info("knowledge_base.initialized", db_path=db_path)

    def add_transcript(self, transcript_id: str, text: str, metadata: dict = None) -> None:
        """Add a chat transcript to the knowledge base."""
        try:
            if metadata is None:
                metadata = {}
            
            self.collection.add(
                ids=[transcript_id],
                documents=[text],
                metadatas=[metadata],
            )
            
            logger.info(
                "knowledge_base.transcript_added",
                transcript_id=transcript_id,
                length=len(text),
            )
        except Exception as e:
            logger.error("knowledge_base.add_error", transcript_id=transcript_id, error=str(e))
            raise

    def search(self, query: str, top_k: int = 3) -> List[dict]:
        """Search for relevant transcripts in the knowledge base."""
        try:
            if not query or not query.strip():
                logger.warning("knowledge_base.empty_query")
                return []
            
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )
            
            # Convert Chroma results to readable format
            documents = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0]
            
            formatted_results = []
            for doc, metadata, distance in zip(documents, metadatas, distances):
                # Convert distance to similarity score (0-1, where 1 is most similar)
                similarity = 1 - (distance / 2)  # Cosine distance is 0-2
                
                formatted_results.append({
                    "text": doc,
                    "metadata": metadata,
                    "similarity": max(0, similarity),
                })
            
            logger.info(
                "knowledge_base.search_completed",
                query_length=len(query),
                results_count=len(formatted_results),
            )
            
            return formatted_results

        except Exception as e:
            logger.error("knowledge_base.search_error", query=query[:50], error=str(e))
            return []

    def load_from_file(self, json_file: str) -> None:
        """Load transcripts from a JSON file."""
        try:
            with open(json_file, "r") as f:
                data = json.load(f)
            
            # Expect format: [{"id": "...", "text": "...", "metadata": {...}}, ...]
            if not isinstance(data, list):
                raise ValueError("JSON file must contain a list of transcripts")
            
            for idx, item in enumerate(data):
                transcript_id = item.get("id", f"transcript_{idx}")
                text = item.get("text", "")
                metadata = item.get("metadata", {})
                
                if text:
                    self.add_transcript(transcript_id, text, metadata)
            
            logger.info("knowledge_base.loaded_from_file", file=json_file, count=len(data))

        except Exception as e:
            logger.error("knowledge_base.load_error", file=json_file, error=str(e))
            raise

    def get_stats(self) -> dict:
        """Get statistics about the knowledge base."""
        try:
            count = self.collection.count()
            return {
                "total_documents": count,
                "collection_name": self.collection.name,
            }
        except Exception as e:
            logger.error("knowledge_base.stats_error", error=str(e))
            return {"total_documents": 0, "collection_name": "unknown"}