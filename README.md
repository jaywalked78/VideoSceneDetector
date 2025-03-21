# Video Scene Detector API

A FastAPI application that processes videos to extract frames based on scene detection using FFmpeg. It can process videos from local storage or download them directly from Google Drive. It also provides integration with Gradio.

## Features

- Process videos from local storage
- Download and process videos directly from Google Drive
- Extract frames based on scene detection using FFmpeg
- Configurable scene threshold
- Webhook callbacks for integration with n8n
- Health check endpoints
- Gradio API integration
- Robust error handling with retries and backoff

## Prerequisites

- Python 3.9+
- FFmpeg installed on the system
- Ubuntu 22.04 (or compatible Linux distribution)
- Google Cloud project with Drive API enabled (for Google Drive integration)
- Gradio server (optional, for Gradio integration)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd VideoSceneDetector
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Copy the example environment file and customize as needed:
```bash
cp .env.example .env
```

## Google Drive Integration Setup

To use the Google Drive integration:

1. Create a Google Cloud project if you don't have one already
2. Enable the Google Drive API in your project
3. Create service account credentials:
   - Go to APIs & Services > Credentials
   - Click "Create credentials" > "Service account"
   - Fill in the service account details
   - Grant the service account access to your project (Role: "Project > Viewer")
   - Create a JSON key for the service account and download it
4. Save the JSON key as `credentials.json` in the project's root directory or set the path in your environment

## Usage

1. Start the FastAPI server:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

2. Access the API documentation at:
```
http://localhost:8000/docs
```

## API Endpoints

### Video Processing

#### POST /api/v1/process-video

Process a local video file and extract frames based on scene detection.

Example curl request:
```bash
curl -X POST \
  http://localhost:8000/api/v1/process-video \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "Screen Recording 2023-07-15.mov",
    "download_folder": "/home/jason/Downloads",
    "destination_folder": "/home/jason/Videos/screenRecordings",
    "callback_url": "http://localhost:5678/webhook/9268d2b1-e4de-421e-9685-4c5aa5e79289",
    "scene_threshold": 0.4
  }'
```

#### POST /api/v1/process-drive-video

Process a video file from Google Drive and extract frames based on scene detection.

Example curl request:
```bash
curl -X POST \
  http://localhost:8000/api/v1/process-drive-video \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "1x2y3z...",
    "destination_folder": "/home/jason/Videos/screenRecordings",
    "callback_url": "http://localhost:5678/webhook/9268d2b1-e4de-421e-9685-4c5aa5e79289",
    "scene_threshold": 0.4
  }'
```

### Gradio Integration

#### GET /api/v1/gradio/health

Check if the Gradio server is accessible.

#### GET /api/v1/gradio/gradio-data

Get data from Gradio with automatic session handling.

#### POST /api/v1/gradio/gradio-data

Send data to Gradio and receive a response.

Example curl request:
```bash
curl -X POST \
  http://localhost:8000/api/v1/gradio/gradio-data \
  -H "Content-Type: application/json" \
  -d '{
    "fn_index": 0,
    "data": ["input data here"]
  }'
```

### Health Check

#### GET /api/v1/health

Health check endpoint to verify the API is running.

## Health Check Script

The repository includes a standalone health check script that can verify the status of:
- The FastAPI server
- The Gradio server
- Google Drive API connectivity

Run it with:
```bash
python health_check.py
```

## Using in n8n Workflows

1. Set up your n8n instance with a webhook node configured to the URL:
   `http://localhost:5678/webhook/9268d2b1-e4de-421e-9685-4c5aa5e79289`

2. In your n8n workflow:
   - Use the HTTP Request node to call the FastAPI endpoint
   - Configure the node with the appropriate JSON payload
   - The webhook node will receive the processing results automatically

## Error Handling

The API includes comprehensive error handling for:
- Missing files
- Invalid directories
- Google Drive API errors
- Gradio connection issues
- FFmpeg processing errors
- Callback failures

All endpoints include retry logic with exponential backoff for transient errors.

## Logging

Logs are output to the console and include:
- API startup/shutdown events
- Video processing steps
- Google Drive download progress
- Gradio connection status
- Error details
- Callback status

## Configuration

The application is configurable via environment variables. See `.env.example` for available options.

## License

MIT 