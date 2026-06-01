import asyncio
import json

from websocket_manager import manager


class EventManager:

    async def send_event(
        self,
        event_type,
        data
    ):

        payload = {
            "type": event_type,
            "data": data
        }

        await manager.broadcast(
            json.dumps(payload)
        )


event_manager = EventManager()