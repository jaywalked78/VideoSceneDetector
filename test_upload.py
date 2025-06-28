#!/usr/bin/env python3
"""
Test script to upload frames to Google Drive folder
"""
import os
import sys
import time
import logging

# Add the app directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils.video_processor import VideoProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_upload():
    # Test parameters
    output_dir = os.path.expanduser("~/Videos/screenRecordings/screen_recording_2025_06_20_at_5_47_19_am")
    original_filename = "screen_recording_2025_06_20_at_5_47_19_am.mp4"
    target_folder_id = "1cSD-WXczrjz8eJwbhWA6NHsQA2_Qnbif"
    
    logger.info("=" * 60)
    logger.info("TESTING GOOGLE DRIVE UPLOAD FUNCTIONALITY")
    logger.info("=" * 60)
    logger.info(f"Source directory: {output_dir}")
    logger.info(f"Target folder ID: {target_folder_id}")
    
    # Check if directory exists
    if not os.path.exists(output_dir):
        logger.error(f"Directory not found: {output_dir}")
        return
    
    # Count frames
    frames = [f for f in os.listdir(output_dir) if f.startswith("frame_") and f.endswith(".jpg")]
    logger.info(f"Found {len(frames)} frames to upload")
    
    if not frames:
        logger.error("No frames found in directory")
        return
    
    # Test 1: Concurrent upload (recommended)
    logger.info("\n" + "=" * 60)
    logger.info("TEST 1: CONCURRENT UPLOAD (10 workers)")
    logger.info("=" * 60)
    
    start_time = time.time()
    
    # We need to modify the upload function to use our target folder
    # For testing, let's create a modified version
    success, result = test_concurrent_upload(output_dir, original_filename, target_folder_id)
    
    elapsed = time.time() - start_time
    
    if success:
        logger.info(f"\n✓ UPLOAD SUCCESSFUL!")
        logger.info(f"- Frames uploaded: {result.get('frames_uploaded')}/{result.get('total_frames')}")
        logger.info(f"- Upload time: {elapsed:.2f} seconds")
        logger.info(f"- Upload speed: {result.get('frames_uploaded')/elapsed:.1f} frames/sec")
        logger.info(f"- Folder URL: https://drive.google.com/drive/folders/{target_folder_id}")
    else:
        logger.error(f"\n✗ UPLOAD FAILED!")
        logger.error(f"- Error: {result.get('error')}")
        logger.error(f"- Details: {result.get('details')}")

def test_concurrent_upload(output_dir, original_filename, folder_id):
    """Modified version of concurrent upload that uses existing folder"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading
    import mimetypes
    from googleapiclient.http import MediaFileUpload
    from app.utils.google_drive import GoogleDriveService
    
    try:
        start_time = time.time()
        
        # Get frames to upload
        frames = [f for f in os.listdir(output_dir) if f.startswith("frame_") and f.endswith(".jpg")]
        logger.info(f"Preparing to upload {len(frames)} frames")
        
        # Initialize Google Drive service
        logger.info("Initializing Google Drive service...")
        drive_service_handler = GoogleDriveService(operation_type="upload")
        drive_service = drive_service_handler.drive_service
        
        if not drive_service:
            return False, {"error": "Authentication failed"}
        
        logger.info("Successfully authenticated with Google Drive")
        
        # Upload tracking
        uploaded_count = 0
        failed_count = 0
        failed_frames = []
        upload_lock = threading.Lock()
        
        logger.info(f"Starting concurrent uploads with 10 workers...")
        upload_start_time = time.time()
        
        def upload_single_frame(frame):
            nonlocal uploaded_count, failed_count
            
            frame_path = os.path.join(output_dir, frame)
            
            file_metadata = {
                'name': frame,
                'parents': [folder_id]
            }
            
            mime_type = mimetypes.guess_type(frame_path)[0] or 'image/jpeg'
            
            media = MediaFileUpload(
                frame_path,
                mimetype=mime_type,
                resumable=False  # Simple upload for small files
            )
            
            try:
                file = drive_service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id'
                ).execute()
                
                with upload_lock:
                    uploaded_count += 1
                    
                    # Log progress
                    if uploaded_count % 10 == 0 or uploaded_count == len(frames):
                        current_time = time.time()
                        elapsed = current_time - upload_start_time
                        frames_per_second = uploaded_count / max(0.1, elapsed)
                        estimated_remaining = (len(frames) - uploaded_count) / max(0.1, frames_per_second)
                        
                        logger.info(f"Progress: {uploaded_count}/{len(frames)} frames "
                                  f"({(uploaded_count/len(frames)*100):.1f}%) - "
                                  f"{frames_per_second:.1f} frames/sec, "
                                  f"~{estimated_remaining:.1f} sec remaining")
                
                return True, frame, None
                
            except Exception as e:
                with upload_lock:
                    failed_count += 1
                    failed_frames.append(frame)
                    if failed_count <= 3:
                        logger.error(f"Error uploading {frame}: {str(e)}")
                
                return False, frame, str(e)
        
        # Use ThreadPoolExecutor for concurrent uploads
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(upload_single_frame, frame): frame for frame in frames}
            
            for future in as_completed(futures):
                frame = futures[future]
                try:
                    success, frame_name, error = future.result()
                except Exception as e:
                    logger.error(f"Exception in thread for {frame}: {str(e)}")
                    with upload_lock:
                        failed_count += 1
                        failed_frames.append(frame)
        
        upload_time = time.time() - start_time
        
        result = {
            "success": uploaded_count > 0,
            "frames_uploaded": uploaded_count,
            "frames_failed": failed_count,
            "total_frames": len(frames),
            "upload_time": round(upload_time, 2)
        }
        
        if failed_frames:
            result["failed_frames"] = failed_frames[:10]
        
        return uploaded_count > 0, result
        
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False, {"error": str(e)}

if __name__ == "__main__":
    test_upload()