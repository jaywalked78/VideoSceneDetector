# VideoSceneDetector

A powerful FastAPI-based service that detects scene changes in videos, extracts frames, and uploads them to Google Drive. The system includes a robust webhook notification system to integrate with other services.

## Features

- **Scene Detection**: Automatically detects scene changes in videos using FFmpeg
- **Frame Extraction**: Extracts high-quality frames at scene change points
- **Google Drive Integration**: Uploads extracted frames to Google Drive
- **Webhook Notifications**: Sends detailed webhooks to integrate with other services
- **Video Processing Queue**: Manages processing tasks to prevent system overload

## Setup and Installation

### Prerequisites

- Python 3.8+
- FFmpeg installed on the system
- A Google Cloud project with the Drive API enabled

### Installation Steps

1. Clone the repository:
   ```bash
   git clone https://github.com/jaywalked78/VideoSceneDetector.git
   cd VideoSceneDetector
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up Google Drive Authentication:
   - Create OAuth credentials or a service account in Google Cloud Console
   - Download the credentials JSON file and save it as `credentials.json` in the project root
   - Run the authentication script:
     ```bash
     python authenticate_drive.py
     ```

## Configuration

The app uses environment variables for configuration. You can create a `.env` file in the project root with the following settings:

```env
# API Configuration
API_VERSION=1.0.0
DEBUG_MODE=false

# Feature Flags
ENABLE_GRADIO=true

# Google Drive Configuration
GOOGLE_CREDENTIALS=credentials.json
GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE=/path/to/service-account-key.json
GOOGLE_DRIVE_USE_SERVICE_ACCOUNT=true

# Gradio Integration
GRADIO_URL=http://localhost:7860
REQUEST_TIMEOUT=30.0
MAX_RETRIES=3

# Default Paths
DEFAULT_DOWNLOAD_FOLDER=/home/username/Downloads
DEFAULT_DESTINATION_FOLDER=/home/videos/screenRecordings

# Webhook Configuration
DEFAULT_CALLBACK_URL=http://localhost:5678/webhook/9268d2b1-e4de-421e-9685-4c5aa5e79289
FRAME_ANALYSIS_WEBHOOK_URL=http://localhost:5678/webhook/9268d2b1-e4de-421e-9685-4c5aa5e79289
FRAME_PROCESSOR_WEBHOOK_URL=http://localhost:5678/webhook/c9af1341-63b6-43fa-a5fc-c7fefc6ab732
```

## Running the Server

Use the provided script to run the server with proper logging:

```bash
./run_server_with_logs.sh
```

Or run it directly with:

```bash
python -m app.main
```

The server will be available at `http://localhost:8000`.

## API Endpoints

### Process a video already on the server

```
POST /api/v1/process-video
```

Request body:
```json
{
  "filename": "video.mp4",
  "download_folder": "/path/to/downloads",
  "destination_folder": "/path/to/output",
  "callback_url": "http://your-callback-url.com/webhook",
  "scene_threshold": 0.4
}
```

### Process a video from Google Drive

```
POST /api/v1/process-drive-video
```

Request body:
```json
{
  "file_id": "google-drive-file-id",
  "destination_folder": "/path/to/output",
  "callback_url": "http://your-callback-url.com/webhook",
  "scene_threshold": 0.369,
  "create_subfolder": true,
  "delete_after_processing": true,
  "force_download": false
}
```

### Health Check

```
GET /api/v1/health
```

## Webhook System

The system sends webhooks at two stages of processing:

1. **Frame Analysis Webhook**: Sent immediately after processing with comprehensive data
   - Includes all extracted frames information, scene metadata, video info
   - Used for data analysis in services like Airtable
   - URL: Configured via the `FRAME_ANALYSIS_WEBHOOK_URL` environment variable

2. **Frame Processor Webhook**: Sent 60 seconds after the first webhook
   - Contains information about the Google Drive folder with frames
   - Used to trigger frame processing in external services
   - URL: Configured via the `FRAME_PROCESSOR_WEBHOOK_URL` environment variable

3. **Custom Callback URL**: Optional additional webhook endpoint
   - Can be specified in the API request
   - Will receive the same data as the Frame Analysis webhook
   - Used for custom integrations

### Webhook Configuration

You can configure the webhook URLs in your `.env` file:
```
FRAME_ANALYSIS_WEBHOOK_URL=http://localhost:5678/webhook/9268d2b1-e4de-421e-9685-4c5aa5e79289
FRAME_PROCESSOR_WEBHOOK_URL=http://localhost:5678/webhook/c9af1341-63b6-43fa-a5fc-c7fefc6ab732
```

### Webhook Payload Example (Frame Analysis)

```json
{
  "success": true,
  "message": "Video processing completed successfully. Extracted 69 frames.",
  "process_id": "1743186333__nJd26",
  "file_id": "1tIVWr8DPvPJj51DG36nGbqUfQI_nJd26",
  "file_name": "Screen Recording.mov",
  "frames_extracted": 69,
  "frames_info": [...],
  "output_directory": "/path/to/output",
  "processing_time": 138.1,
  "extraction_time": 109.89,
  "download_time": -28.21,
  "file_already_existed": false,
  "scene_metadata": [...],
  "video_info": {...},
  "drive_upload": {
    "folder_name": "screen_recording",
    "folder_id": "abc123",
    "drive_folder_url": "https://drive.google.com/drive/folders/abc123"
  },
  "webhookUrl": "http://localhost:5678/webhook/9268d2b1-e4de-421e-9685-4c5aa5e79289",
  "executionMode": "production"
}
```

### Webhook Payload Example (Frame Processor)

```json
{
  "folder_name": "screen_recording",
  "frame_count": 69,
  "timestamp": "2025-03-29 22:45:12",
  "folder_id": "abc123",
  "drive_folder_url": "https://drive.google.com/drive/folders/abc123",
  "process_id": "1743186333__nJd26",
  "success": true
}
```

## Google Drive Authentication

The application supports two authentication methods:

1. **Service Account Authentication** (recommended for production):
   - Create a service account in Google Cloud Console with appropriate permissions
   - Download the JSON key file and save it somewhere secure
   - Configure the path to the service account key file in your `.env` file:
     ```
     GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE=/path/to/service-account-key.json
     GOOGLE_DRIVE_USE_SERVICE_ACCOUNT=true
     ```
   - No user interaction required - works on servers without browser access

2. **OAuth Authentication** (fallback if service account is not configured):
   - Run `python authenticate_drive.py` to generate the token
   - The token is saved as `token.pickle` and reused
   - Requires browser interaction on the first run

The application attempts authentication in this order:
1. Service account from the path specified in `GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE`
2. OAuth token from `token.pickle`
3. Service account from `credentials.json`
4. OAuth flow using `credentials.json`

## Troubleshooting

### OAuth Authentication Issues

If you encounter `redirect_uri_mismatch` errors:
1. Delete the token file: `rm token.pickle`
2. Run authentication again: `python authenticate_drive.py`

### FFmpeg Errors

Make sure FFmpeg is properly installed and available in your PATH:
```bash
ffmpeg -version
```

### Google Drive Permission Issues

Ensure your Google account has proper permissions to:
1. Read files in Google Drive
2. Create folders in Google Drive
3. Upload files to Google Drive

## License

MIT 

# Project Dependencies

## Core Dependencies
- ...existing dependencies...

## Media Processing
- **get-video-duration**: Used to retrieve video duration information for progress tracking in FFMPEG operations
- **ffmpeg** (system dependency): Required for video processing operations

## System Utilities
- Memory management utilities (built-in)
- FFMPEG progress tracking (built-in) 