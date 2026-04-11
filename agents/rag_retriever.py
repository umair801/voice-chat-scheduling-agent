from typing import List, Optional

from core.knowledge_base import KnowledgeBase
from core.logger import get_logger

logger = get_logger(__name__)


class RAGRetriever:
    """Retrieval-Augmented Generation wrapper for knowledge base."""

    def __init__(self, kb: Optional[KnowledgeBase] = None):
        """Initialize RAG retriever with optional knowledge base."""
        self.kb = kb or KnowledgeBase()
        logger.info("rag_retriever.initialized")

    def retrieve_context(self, query: str, top_k: int = 3, min_similarity: float = 0.5) -> dict:
        """
        Retrieve relevant context from knowledge base for a query.
        
        Args:
            query: Customer question or issue
            top_k: Maximum number of results to retrieve
            min_similarity: Minimum similarity threshold (0-1)
        
        Returns:
            dict with 'found_context' (bool), 'context' (str), 'sources' (list), 'confidence' (float)
        """
        try:
            if not query or not query.strip():
                logger.warning("rag_retriever.empty_query")
                return {
                    "found_context": False,
                    "context": "",
                    "sources": [],
                    "confidence": 0.0,
                }
            
            # Search knowledge base
            results = self.kb.search(query, top_k=top_k)
            
            # Filter by minimum similarity
            relevant_results = [r for r in results if r["similarity"] >= min_similarity]
            
            if not relevant_results:
                logger.info(
                    "rag_retriever.no_relevant_context",
                    query_length=len(query),
                    threshold=min_similarity,
                )
                return {
                    "found_context": False,
                    "context": "",
                    "sources": [],
                    "confidence": 0.0,
                }
            
            # Build context string from top results
            context_parts = []
            sources = []
            
            for idx, result in enumerate(relevant_results, 1):
                context_parts.append(f"[Reference {idx}]\n{result['text']}")
                sources.append({
                    "index": idx,
                    "similarity": round(result["similarity"], 2),
                    "metadata": result.get("metadata", {}),
                })
            
            context = "\n\n".join(context_parts)
            
            # Average similarity as confidence
            avg_similarity = sum(r["similarity"] for r in relevant_results) / len(relevant_results)
            
            logger.info(
                "rag_retriever.context_retrieved",
                query_length=len(query),
                results_count=len(relevant_results),
                avg_similarity=round(avg_similarity, 2),
            )
            
            return {
                "found_context": True,
                "context": context,
                "sources": sources,
                "confidence": round(avg_similarity, 2),
            }

        except Exception as e:
            logger.error("rag_retriever.retrieval_error", query=query[:50], error=str(e))
            return {
                "found_context": False,
                "context": "",
                "sources": [],
                "confidence": 0.0,
            }

    def format_context_for_prompt(self, context_data: dict) -> str:
        """
        Format retrieved context for inclusion in LLM prompt.
        
        Args:
            context_data: Output from retrieve_context()
        
        Returns:
            Formatted string for LLM system prompt
        """
        if not context_data["found_context"]:
            return ""
        
        formatted = f"""
Based on similar customer conversations in our knowledge base (confidence: {context_data['confidence']}):

{context_data['context']}

Use the above references to provide an accurate answer. If the exact situation isn't in the knowledge base, mention that and provide the best guidance you can.
"""
        return formatted.strip()