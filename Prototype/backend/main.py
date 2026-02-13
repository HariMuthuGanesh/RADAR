import asynciocls
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from radar_handler import RadarHandler
import os

app = FastAPI(title="Radar Monitoring Dashboard API")

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Radar Handler
# Note: Adjust COM ports as per your device
radar = RadarHandler(cfg_port="COM6", data_port="COM7")

# Store active websocket connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                # Remove dead connections
                self.active_connections.remove(connection)

manager = ConnectionManager()

@app.on_event("startup")
async def startup_event():
    # Attempt to connect and send config on startup
    if radar.connect():
        # Look for config in parent or current dir
        cfg_path = os.path.join(os.getcwd(), "radar_profile.cfg")
        if not os.path.exists(cfg_path):
             # Try common locations in this project
             cfg_path = "radar_profile.cfg" 
        
        if os.path.exists(cfg_path):
            radar.send_config(cfg_path)
            print("Radar connected and configured.")
        else:
            print(f"Warning: Config file not found at {cfg_path}")
        
        # Start background task for radar streaming
        asyncio.create_task(radar.start_streaming(manager.broadcast))
    else:
        print("Failed to connect to radar. Check ports.")

@app.websocket("/ws/radar")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/status")
async def get_status():
    return {"status": "running", "radar_connected": radar.is_running}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
