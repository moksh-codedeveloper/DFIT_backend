import json
from channels.generic.websocket import AsyncWebsocketConsumer

class FileUploadConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if user.is_authenticated:
            await self.accept()
            await self.send(text_data=json.dumps({
                "message": "Connected to DFIT WebSocket!"
            }))
        else:
            await self.close()

    async def disconnect(self, close_code):
        print("Disconnected")

    async def receive(self, text_data=None, bytes_data=None):
        if bytes_data:
            await self.send(text_data=json.dumps({
                "message": "File received!"
            }))
        else:
            await self.send(text_data=json.dumps({
                "error": "No file data received"
            }))
