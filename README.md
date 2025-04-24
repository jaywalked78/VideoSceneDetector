# Video Scene Detector

A powerful FastAPI-based service using FFmpeg to detect scene changes in videos, extract key frames, and upload them to Google Drive. Designed as a crucial first step in RAG ingestion pipelines, it integrates seamlessly with n8n workflows via robust webhook notifications.

## Workflow Context

This Video Scene Detector service initiates the content processing pipeline for RAG systems, primarily handling video input. Here's the overall flow, heavily orchestrated by n8n:

```mermaid
flowchart TD
    A[Video Input] --> B(n8n: Trigger VIDEO SCENE DETECTOR);
    B --> C[FRAME EXTRACTOR (This Repo)];
    C --> D(n8n: AI Enrichment + OCR Refinement + Airtable Upsert);
    D --> E(n8n: Trigger IntelliChunk);
    E --> F(IntelliChunk + Image Server);
    F --> G(n8n: Embedding Generation);
    G --> H[(PostgreSQL Vector DB)];
```

**Role in Pipeline:**

1.  An external trigger (e.g., new video upload) starts an n8n workflow.
2.  The n8n workflow calls the `/api/v1/process-drive-video` or `/api/v1/process-video` endpoint of this `VideoSceneDetector` service.
3.  This service processes the video, detects scenes, extracts relevant frames, and uploads them to a designated Google Drive folder.
4.  Upon completion, it sends two webhooks (Frame Analysis and Frame Processor) back to n8n.
5.  The `Frame Processor Webhook` triggers the next n8n workflow segment, which handles AI enrichment, OCR, Airtable updates, and eventually calls the [IntelliChunk](https://github.com/jaywalked78/IntelliChunk) service for semantic chunking and the [Image Server](https://github.com/jaywalked78/Lightweight-File-Hosting-Server) for hosting.

## Features

- **Scene Detection:** Uses FFmpeg `select` filter with `scenedetect` option for accurate scene change identification.
- **Frame Extraction:** Extracts high-quality frames precisely at detected scene change points.
- **Google Drive Integration:** Securely uploads extracted frames to specified Google Drive folders using Service Account or OAuth authentication.
- **Dual Webhook System:** Provides immediate detailed analysis data and a delayed trigger for subsequent processing steps.
- **Configurable:** Fine-tune scene detection threshold, destination folders, webhook URLs, and authentication via `.env` file.
- **Processing Queue:** Manages video processing tasks sequentially to ensure stability.

## Setup and Installation

### Prerequisites

- Python 3.8+
- FFmpeg installed and accessible in system PATH (`ffmpeg -version`)
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

4. Set up Google Drive Authentication (See [Google Drive Authentication](#google-drive-authentication) section below):
   - Obtain `credentials.json` (OAuth) or a service account JSON key file.
   - Place the file(s) appropriately.
   - Run `python authenticate_drive.py` if using OAuth for the first time.
   - Configure `.env` file (`GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE`, `GOOGLE_DRIVE_USE_SERVICE_ACCOUNT`).

## Configuration

Create a `.env` file in the project root (copy from `.env.example`). Key settings:

```env
# API Configuration
API_VERSION=1.0.0
DEBUG_MODE=false # Set to true for more verbose logging

# Google Drive Configuration
GOOGLE_CREDENTIALS=credentials.json # For OAuth fallback
GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE=/path/to/your/service-account-key.json # Recommended
GOOGLE_DRIVE_USE_SERVICE_ACCOUNT=true # Set to true to use service account

# Default Paths (can be overridden in API calls)
DEFAULT_DOWNLOAD_FOLDER=/tmp/video_downloads # Temporary local storage for downloads
DEFAULT_DESTINATION_FOLDER=/path/to/local/frame/output # Local output before GDrive upload

# Webhook Configuration (Update with your n8n webhook URLs)
FRAME_ANALYSIS_WEBHOOK_URL=http://localhost:5678/webhook/your-analysis-webhook-id
FRAME_PROCESSOR_WEBHOOK_URL=http://localhost:5678/webhook/your-processor-trigger-webhook-id
# DEFAULT_CALLBACK_URL is optional, often overridden in API calls
```

## Running the Server

Use the provided script for robust execution with logging:

```bash
./run_server_with_logs.sh
```

This script handles PID management and log rotation. The server will be available at `http://localhost:8000` (or as configured).

To run directly for development:
```bash
python -m app.main
```

## API Endpoints

### Process a video from Google Drive (Recommended)

```
POST /api/v1/process-drive-video
```
Handles downloading from Google Drive, processing, and uploading frames back to Drive.

**Request Body:**
```json
{
  "file_id": "google-drive-file-id",
  "destination_folder": "NameOfOutputFolderInDrive", // GDrive folder name
  "callback_url": "http://optional-custom-webhook.com", // Optional
  "scene_threshold": 0.369, // Adjust sensitivity (lower = more scenes)
  "create_subfolder": true, // Create a subfolder within destination_folder named after the video
  "delete_after_processing": false, // Delete the downloaded video file locally after processing
  "force_download": false // Re-download even if file exists locally
}
```

### Process a video already on the server

```
POST /api/v1/process-video
```
Processes a video file already present on the server's local filesystem.

**Request Body:**
```json
{
  "filename": "video.mp4", // Name of the video file
  "download_folder": "/path/to/local/video/directory", // Where the video file is located
  "destination_folder": "NameOfOutputFolderInDrive", // GDrive folder name for frame uploads
  "callback_url": "http://optional-custom-webhook.com", // Optional
  "scene_threshold": 0.4
}
```

### Health Check

```
GET /api/v1/health
```
Returns the status of the server.

## Webhook System

 crucial for integrating with n8n or other automation tools.

1.  **Frame Analysis Webhook** (`FRAME_ANALYSIS_WEBHOOK_URL`):
    *   Sent immediately after local processing and frame extraction completes.
    *   Contains detailed metadata about the video, scenes detected, and extracted frame information (before GDrive upload).
    *   Ideal for logging, analysis, or initial data recording (e.g., in Airtable).
2.  **Frame Processor Webhook** (`FRAME_PROCESSOR_WEBHOOK_URL`):
    *   Sent after a dynamic delay (based on frame count, default 0.75s/frame) *after* frames are successfully uploaded to Google Drive.
    *   Contains the Google Drive folder ID and URL where frames were uploaded.
    *   Specifically designed to trigger the *next* stage of processing in n8n (AI enrichment, OCR, chunking via IntelliChunk).
3.  **Custom Callback URL** (Optional, provided in API request):
    *   Receives the same payload as the Frame Analysis Webhook.
    *   Allows for flexible, per-request integration points.

### Webhook Payloads
*(See original README section for detailed payload examples)*

## Google Drive Authentication

Supports **Service Account** (recommended for server environments) and **OAuth** (requires initial browser interaction).

1.  **Service Account:**
    *   Create service account in Google Cloud Console, enable Drive API, download JSON key.
    *   Set `GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE` in `.env` to the key file path.
    *   Set `GOOGLE_DRIVE_USE_SERVICE_ACCOUNT=true` in `.env`.
2.  **OAuth:**
    *   Get `credentials.json` from Google Cloud Console (OAuth 2.0 Client ID).
    *   Place `credentials.json` in the project root.
    *   Run `python authenticate_drive.py` once interactively to generate `token.pickle`.
    *   Ensure `GOOGLE_DRIVE_USE_SERVICE_ACCOUNT=false` or is commented out in `.env`.

**Authentication Order:** Service Account (from env path) -> OAuth Token -> Service Account (`credentials.json`) -> OAuth Flow (`credentials.json`).

## Troubleshooting

*(See original README section for Troubleshooting tips on OAuth, FFmpeg, and GDrive permissions)*

## License

MIT

# Project Dependencies
*(See original README section for Dependencies)* 
