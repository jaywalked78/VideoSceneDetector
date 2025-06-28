# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Video Scene Detector is a FastAPI-based service that detects scene changes in videos, extracts key frames, and uploads them to Google Drive. It's designed as a crucial first step in RAG ingestion pipelines and integrates with n8n workflows via webhooks.

Key features:
- FFmpeg-based scene detection and frame extraction
- Real-time streaming upload system (frames upload concurrently with extraction)
- Dual Google Drive account support (primary for upload, secondary for download)
- Webhook notifications for n8n workflow integration
- Processing queue for sequential video handling

## Development Commands

### Running the Server
```bash
# Primary method - with logging and PID management
./run_server_with_logs.sh

# Development mode
python -m app.main

# Kill server if needed
./kill_server.sh
# or force kill
./force_kill_server.sh
```

### Testing
```bash
# Run individual test scripts
python testScripts/test_api_flow.py
python testScripts/test_flexible_accounts.py
python testScripts/test_endpoint.py

# Test upload functionality
python test_upload.py
python test_queue_upload.py
python test_optimized_upload.py
```

### Dependency Management
```bash
# Python dependencies
pip install -r requirements.txt

# Node.js dependencies (for TypeScript components)
npm install
```

### Update and Deploy
```bash
# Update code and restart systemd service
./update_and_restart.sh
```

## Architecture

### Core Components

1. **FastAPI Application** (`app/`)
   - `main.py`: Application entry point
   - `routers/video.py`: API endpoints for video processing
   - `models/video.py`: Pydantic models for request/response validation
   - `services/`: Business logic services

2. **Video Processing Pipeline**
   - `app/utils/video_processor.py`: FFmpeg scene detection and frame extraction
   - `app/utils/frame_watcher.py`: Real-time file system monitoring for new frames
   - `app/utils/upload_queue.py`: Thread-safe queue for concurrent uploads

3. **Google Drive Integration**
   - `app/utils/google_drive.py`: Dual-account Google Drive service
   - Supports OAuth and Service Account authentication
   - Primary account for uploads, secondary for downloads

4. **Webhook System**
   - Frame Analysis Webhook: Sent immediately after processing
   - Frame Processor Webhook: Delayed trigger for next pipeline stage
   - Custom callback URL support per request

### Streaming Upload Architecture

The streaming upload system eliminates traditional upload bottlenecks by uploading frames concurrently as FFmpeg extracts them:

1. FFmpeg starts extraction → Creates output directory
2. FrameWatcher monitors directory → Detects new frame files
3. New frames added to UploadQueueManager → Sequential upload to Google Drive
4. Process continues until FFmpeg completes → Final queue cleanup

This reduces total processing time from ~25 minutes (sequential) to ~10 minutes (streaming).

## Configuration

### Environment Variables (.env)

Critical settings:
- `DEBUG_MODE`: Enable verbose logging
- `GOOGLE_DOWNLOAD_*`: Secondary account for downloads
- `GOOGLE_UPLOAD_*`: Primary account for uploads
- `FRAME_ANALYSIS_WEBHOOK_URL`: n8n webhook for analysis data
- `FRAME_PROCESSOR_WEBHOOK_URL`: n8n webhook to trigger next stage

### Google Drive Authentication

Priority order:
1. Service Account (from env path)
2. OAuth Token (token.pickle)
3. Service Account fallback (credentials.json)
4. OAuth flow (credentials.json)

## API Endpoints

### POST /api/v1/process-drive-video
Process video from Google Drive with scene detection and frame extraction.

Key parameters:
- `file_id`: Google Drive file ID
- `destination_folder`: Output folder name in Drive
- `scene_threshold`: Detection sensitivity (default: 0.369)
- `create_subfolder`: Create video-named subfolder
- `download_account_type`: "primary" or "secondary"

### POST /api/v1/process-video
Process local video file.

### GET /api/v1/health
Health check endpoint.

## Development Notes

### FFmpeg Integration
- Uses `select` filter with `scenedetect` for scene changes
- Non-blocking subprocess execution for streaming
- Configurable scene threshold (lower = more sensitive)

### Error Handling
- Comprehensive logging with DEBUG_MODE
- Automatic retry with exponential backoff for uploads
- Graceful handling of Google Drive API rate limits
- No webhooks sent on processing failures

### Performance Considerations
- Sequential video processing (one at a time)
- Concurrent frame uploads (respects API limits)
- File watcher poll interval: 200ms
- Upload queue worker with configurable retry

### Security
- Supports both OAuth and Service Account authentication
- Environment-based configuration (no hardcoded secrets)
- Separate credentials for upload/download operations

## Common Tasks

### Debug Authentication Issues
```bash
python testScripts/test_api_flow.py
```

### Monitor Processing Progress
Enable DEBUG_MODE in .env for detailed logging:
- Frame extraction count
- Upload success/failure tracking
- Queue statistics and processing rate

### Handle Port Conflicts
The run_server_with_logs.sh script automatically handles port 8000 conflicts using lsof, fuser, and aggressive cleanup.

### Update Webhook URLs
Update in .env:
- FRAME_ANALYSIS_WEBHOOK_URL
- FRAME_PROCESSOR_WEBHOOK_URL

Or provide custom callback_url in API requests.