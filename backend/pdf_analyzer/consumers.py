import json
import tempfile
import os
from urllib.parse import parse_qs

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User

class FileUploadConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Parse the query string to get the token
        query_string = self.scope["query_string"].decode()
        query_params = parse_qs(query_string)
        token = query_params.get('token', [None])[0]

        # Authenticate user using the token
        user = await self.get_user_from_token(token)

        if user:
            self.scope["user"] = user  # Attach user to scope
            await self.accept()
            await self.send(text_data=json.dumps({
                "message": "Connected with token!"
            }))
        else:
            await self.close()

    async def disconnect(self, close_code):
        print("WebSocket disconnected")

    async def receive(self, text_data=None, bytes_data=None):
        if bytes_data:
            try:
                # Save the file temporarily
                tmp_file = tempfile.NamedTemporaryFile(delete=False)
                tmp_file.write(bytes_data)
                tmp_file_path = tmp_file.name
                tmp_file.close()

                # Dummy parsed text – simulate processing
                parsed_text = f"Simulated parsed content from file ({os.path.basename(tmp_file_path)})"

                # Send the parsed result back to the client
                await self.send(text_data=json.dumps({
                    "message": "File uploaded and processed!",
                    "parsed_text": parsed_text
                }))

                # Optionally delete the file after processing
                os.remove(tmp_file_path)

            except Exception as e:
                await self.send(text_data=json.dumps({
                    "error": f"Error processing file: {str(e)}"
                }))
        else:
            await self.send(text_data=json.dumps({
                "error": "No file data received"
            }))

    @database_sync_to_async
    def get_user_from_token(self, token):
        from django.contrib.auth.models import User  # ✅ Import inside the method
        from django.core.exceptions import ObjectDoesNotExist

        try:
            return User.objects.get(username="testuser")  # Replace with actual logic
        except ObjectDoesNotExist:
            return None
