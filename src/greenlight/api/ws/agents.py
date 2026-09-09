"""WebSocket hub for agent status events. Broadcasts AgentEvent to all connected clients."""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services.agent_runner import broker

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/agents")
async def agents_websocket(ws: WebSocket):
    await ws.accept()
    queue = await broker.subscribe()

    try:
        while True:
            event = await queue.get()
            await ws.send_json(
                {
                    "agent": event.agent,
                    "status": event.status,
                    "message": event.message,
                    "ts": event.ts,
                }
            )
    except WebSocketDisconnect:
        logger.info("Agent status client disconnected")
    except Exception as e:
        logger.error(f"Agent status WS error: {e}", exc_info=True)
    finally:
        try:
            await broker.unsubscribe(queue)
        except Exception as e:
            logger.warning(f"broker unsubscribe failed: {e}", exc_info=True)
        try:
            await ws.close()
        except Exception:
            pass
