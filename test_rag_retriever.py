from core.knowledge_base import KnowledgeBase
from agents.rag_retriever import RAGRetriever

# Create KB and add transcripts
kb = KnowledgeBase()
kb.add_transcript(
    'transcript_1',
    'Customer: My internet keeps disconnecting. Support: Try restarting your modem.',
    {'issue': 'connectivity', 'resolution': 'restart_modem'}
)
kb.add_transcript(
    'transcript_2',
    'Customer: How do I reset my password? Support: Go to login and click forgot password.',
    {'issue': 'account', 'resolution': 'password_reset'}
)

# Create RAG retriever
rag = RAGRetriever(kb)

# Test retrieval
query = "internet keeps disconnecting"
context_data = rag.retrieve_context(query, top_k=2, min_similarity=0.5)

print(f"Found Context: {context_data['found_context']}")
print(f"Confidence: {context_data['confidence']}")
print(f"Sources: {context_data['sources']}")
print()
print("Formatted for Prompt:")
print(rag.format_context_for_prompt(context_data))