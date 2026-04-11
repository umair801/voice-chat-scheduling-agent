import asyncio
from core.knowledge_base import KnowledgeBase
from core.models import NormalizedMessage, Channel
from agents.tech_support_agent import parse_tech_intent, _kb
from datetime import datetime

async def test():
    # Add sample transcripts to KB
    _kb.add_transcript(
        'transcript_1',
        'Customer: My internet keeps disconnecting every few hours. Support: Try restarting your modem and checking cables.',
        {'issue': 'connectivity', 'resolution': 'restart_modem'}
    )
    
    _kb.add_transcript(
        'transcript_2',
        'Customer: Service keeps dropping. Support: We recommend updating your router firmware.',
        {'issue': 'service', 'resolution': 'firmware_update'}
    )
    
    # Test tech support with RAG
    msg = NormalizedMessage(
        session_id='test-tech-rag',
        channel=Channel.VOICE,
        raw_text='My satellite internet keeps disconnecting. This is urgent!',
        customer_phone='+1234567890',
        timestamp=datetime.utcnow()
    )
    
    result = await parse_tech_intent(msg)
    print(f'Intent: {result.intent.value}')
    print(f'Confidence: {result.confidence}')
    print(f'Notes: {result.entities.notes}')
    print(f'Urgency: {result.entities.urgency}')

asyncio.run(test())