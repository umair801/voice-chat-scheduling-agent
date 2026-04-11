from core.knowledge_base import KnowledgeBase

# Create KB
kb = KnowledgeBase()

# Add some sample transcripts
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

# Search
results = kb.search('internet disconnecting', top_k=2)
print(f'Found {len(results)} results')
for r in results:
    print(f'Similarity: {r["similarity"]:.2f}')
    print(f'Text: {r["text"][:80]}...')
    print()

# Stats
stats = kb.get_stats()
print(f'Stats: {stats}')