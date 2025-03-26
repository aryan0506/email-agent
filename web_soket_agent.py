from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict
import os
from dotenv import load_dotenv
import re

# Load environment variables
load_dotenv()

# Read user credentials from .env file
USERS = {
    os.getenv("YOU_ID"): os.getenv("YOU_PASSWORD"),
    os.getenv("FRIEND_ID"): os.getenv("FRIEND_PASSWORD"),
}

app = FastAPI()


# 🎛️ WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, username: str, password: str):
        # Validate username and password
        if username not in USERS or USERS[username] != password:
            await websocket.close(code=4001)  # ❌ Authentication failed
            return None

        # Ensure password is exactly 7 digits
        if not re.fullmatch(r"\d{7}", password):
            await websocket.close(code=4002)  # ❌ Invalid password format
            return None

        if len(self.active_connections) >= 2:
            await websocket.close(code=4000)  # ❌ Max users reached
            return None

        await websocket.accept()  # ✅ Accept connection
        self.active_connections[username] = websocket
        return username  # Return authenticated username

    def disconnect(self, username: str):
        if username in self.active_connections:
            del self.active_connections[username]

    async def send_message(self, sender: str, message: str):
        for user, websocket in self.active_connections.items():
            if user != sender:
                await websocket.send_text(f"{sender}: {message}")


manager = ConnectionManager()


# 📡 WebSocket Endpoint with Authentication
@app.websocket("/ws/{username}/{password}")
async def websocket_endpoint(websocket: WebSocket, username: str, password: str):
    user_id = await manager.connect(websocket, username, password)

    if user_id is None:
        return

    try:
        while True:
            data = await websocket.receive_text()
            await manager.send_message(user_id, data)
    except WebSocketDisconnect:
        manager.disconnect(user_id)
