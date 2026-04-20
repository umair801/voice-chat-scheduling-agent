# tests/test_rag_retriever.py

import pytest
from core.models import Channel
from core.knowledge_base import KnowledgeBase
from agents.rag_retriever import RAGRetriever


class TestRAGRetrieverImport:
    """Test that RAG components import cleanly."""

    def test_knowledge_base_imports(self):
        try:
            from core.knowledge_base import KnowledgeBase
            assert KnowledgeBase is not None
        except ImportError as e:
            pytest.fail(f"KnowledgeBase import failed: {e}")

    def test_rag_retriever_imports(self):
        try:
            from agents.rag_retriever import RAGRetriever
            assert RAGRetriever is not None
        except ImportError as e:
            pytest.fail(f"RAGRetriever import failed: {e}")

    def test_rag_retriever_instantiation(self):
        retriever = RAGRetriever()
        assert retriever is not None
        assert retriever.kb is not None

    def test_rag_retriever_with_custom_kb(self):
        kb = KnowledgeBase()
        retriever = RAGRetriever(kb=kb)
        assert retriever.kb is kb


class TestRAGRetrieverMethods:
    """Test RAGRetriever method signatures and return structures."""

    def setup_method(self):
        self.retriever = RAGRetriever()

    def test_retrieve_context_returns_dict(self):
        result = self.retriever.retrieve_context("test query")
        assert isinstance(result, dict)

    def test_retrieve_context_has_required_keys(self):
        result = self.retriever.retrieve_context("satellite signal problem")
        assert "found_context" in result
        assert "context" in result
        assert "sources" in result
        assert "confidence" in result

    def test_retrieve_context_found_context_is_bool(self):
        result = self.retriever.retrieve_context("connectivity issue")
        assert isinstance(result["found_context"], bool)

    def test_retrieve_context_sources_is_list(self):
        result = self.retriever.retrieve_context("device not working")
        assert isinstance(result["sources"], list)

    def test_retrieve_context_confidence_is_float(self):
        result = self.retriever.retrieve_context("billing question")
        assert isinstance(result["confidence"], float)
        assert 0.0 <= result["confidence"] <= 1.0

    def test_retrieve_context_empty_query(self):
        result = self.retriever.retrieve_context("")
        assert result["found_context"] is False
        assert result["confidence"] == 0.0

    def test_retrieve_context_whitespace_query(self):
        result = self.retriever.retrieve_context("   ")
        assert result["found_context"] is False

    def test_format_context_for_prompt_returns_string(self):
        context_data = {
            "found_context": False,
            "context": "",
            "sources": [],
            "confidence": 0.0,
        }
        result = self.retriever.format_context_for_prompt(context_data)
        assert isinstance(result, str)

    def test_format_context_with_content(self):
        context_data = {
            "found_context": True,
            "context": "Previous issue: customer had connectivity problem. Resolution: reset the device.",
            "sources": ["transcript_001"],
            "confidence": 0.85,
        }
        result = self.retriever.format_context_for_prompt(context_data)
        assert isinstance(result, str)
        assert len(result) > 0


class TestKnowledgeBaseBasics:
    """Test KnowledgeBase initialization and basic structure."""

    def test_knowledge_base_instantiation(self):
        kb = KnowledgeBase()
        assert kb is not None

    def test_knowledge_base_has_search_method(self):
        kb = KnowledgeBase()
        assert hasattr(kb, "search")
        assert callable(kb.search)

    def test_knowledge_base_search_returns_list(self):
        kb = KnowledgeBase()
        results = kb.search("test query", top_k=3)
        assert isinstance(results, list)

    def test_knowledge_base_search_empty_query(self):
        kb = KnowledgeBase()
        results = kb.search("", top_k=3)
        assert isinstance(results, list)