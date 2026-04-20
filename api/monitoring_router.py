# api/monitoring_router.py

from datetime import datetime
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.database import get_db
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/monitor", tags=["Monitoring"])


class TakeoverRequest(BaseModel):
    session_id: str
    agent_note: str = "Human takeover requested via dashboard"


@router.get("/sessions")
async def get_active_sessions() -> dict[str, Any]:
    """
    Return all active sessions from Supabase.
    Used by the monitoring dashboard to show live conversations.
    """
    try:
        db = get_db()
        result = (
            db.table("scheduling_sessions")
            .select("*")
            .eq("is_active", True)
            .order("updated_at", desc=True)
            .limit(50)
            .execute()
        )
        sessions = result.data or []

        # Sanitize conversation history for display
        for session in sessions:
            history = session.get("conversation_history", [])
            session["turn_count"] = len(history)
            session["last_message"] = history[-1] if history else None

        logger.info("monitoring.sessions_fetched", count=len(sessions))
        return {
            "status": "ok",
            "count": len(sessions),
            "sessions": sessions,
            "fetched_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error("monitoring.sessions_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/takeover")
async def human_takeover(request: TakeoverRequest) -> dict[str, Any]:
    """
    Flag a session for human takeover.
    Sets human_takeover=True in Supabase so the agent stops responding.
    """
    try:
        db = get_db()
        db.table("scheduling_sessions").update({
            "is_active": False,
            "current_intent": "human_takeover",
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("session_id", request.session_id).execute()

        logger.info(
            "monitoring.takeover_triggered",
            session_id=request.session_id,
            note=request.agent_note,
        )
        return {
            "status": "ok",
            "session_id": request.session_id,
            "message": "Session flagged for human takeover. Agent will stop responding.",
        }

    except Exception as e:
        logger.error("monitoring.takeover_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats() -> dict[str, Any]:
    """
    Return quick stats for the dashboard header.
    """
    try:
        db = get_db()

        active = db.table("scheduling_sessions").select(
            "session_id", count="exact"
        ).eq("is_active", True).execute()

        total_bookings = db.table("scheduling_bookings").select(
            "booking_id", count="exact"
        ).execute()

        confirmed = db.table("scheduling_bookings").select(
            "booking_id", count="exact"
        ).eq("status", "confirmed").execute()

        return {
            "status": "ok",
            "active_sessions": active.count or 0,
            "total_bookings": total_bookings.count or 0,
            "confirmed_bookings": confirmed.count or 0,
            "fetched_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error("monitoring.stats_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test")
async def monitoring_test() -> dict:
    """Health check for the monitoring router."""
    return {"status": "ok", "router": "monitoring"}