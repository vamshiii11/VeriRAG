import asyncio, json
from collections import defaultdict
from fastapi import WebSocket

class EventBus:
    def __init__(self):
        self.clients=defaultdict(set)
    async def subscribe(self,user_id,ws:WebSocket):
        await ws.accept(); self.clients[user_id].add(ws)
    def unsubscribe(self,user_id,ws):
        self.clients[user_id].discard(ws)
    async def emit(self,user_id,event,stage,message,percent=None,resource_id=None):
        payload={"event":event,"stage":stage,"message":message,"percent":percent,"resourceId":resource_id}
        for ws in list(self.clients[user_id]):
            try: await ws.send_text(json.dumps(payload))
            except Exception: self.clients[user_id].discard(ws)
bus=EventBus()
