# Attention Tracker Server

## Overview
This server provides attention tracking functionality using computer vision and WebSocket communication.

## Technologies
- **FastAPI**: For REST API and WebSocket handling
- **Uvicorn**: ASGI server for FastAPI
- **MediaPipe**: For face and eye tracking
- **OpenCV**: For image processing

## Running the Server

### Option 1: Direct Python execution
```bash
cd attention_tracker
python fastapi_server.py
```

### Option 2: Using the run script (recommended)
```bash
cd attention_tracker
python run_server.py
```

## API Endpoints

- `GET /api/status` - Get server status
- `POST /api/start` - Start a tracking session
- `POST /api/stop` - Stop a tracking session
- `GET /api/summary/{session_id}` - Get session summary
- `WS /ws/attention/{session_id}` - WebSocket for real-time tracking

## Requirements
Install dependencies:
```bash
pip install -r requirements.txt
```

## Notes
- The server runs on port 5050
- WebSocket connections are handled asynchronously for better stability
- Frames are processed at ~6 FPS to prevent overload