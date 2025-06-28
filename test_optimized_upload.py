#!/usr/bin/env python3
"""
Optimized test script for Google Drive uploads with better performance
"""
import os
import sys
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import mimetypes
import requests
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
import random

# Add the app directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.utils.google_drive import GoogleDriveService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class OptimizedUploader:
    def __init__(self, folder_id, max_workers=3, max_retries=3):
        self.folder_id = folder_id
        self.max_workers = max_workers
        self.max_retries = max_retries
        self.uploaded_count = 0
        self.failed_count = 0
        self.upload_lock = threading.Lock()
        self.failed_frames = []
        self.drive_service = None
        self.session = requests.Session()
        
    def initialize_service(self):
        """Initialize Google Drive service"""
        logger.info("Initializing Google Drive service...")
        drive_service_handler = GoogleDriveService(operation_type="upload")
        self.drive_service = drive_service_handler.drive_service
        
        if not self.drive_service:
            raise Exception("Failed to initialize Google Drive service")
            
        logger.info("Successfully authenticated with Google Drive")
        
    def upload_single_frame_with_retry(self, frame_path, frame_name):
        """Upload a single frame with retry logic"""
        for attempt in range(self.max_retries):
            try:
                # Add exponential backoff with jitter
                if attempt > 0:
                    sleep_time = (2 ** attempt) + random.uniform(0, 1)
                    time.sleep(sleep_time)
                
                file_metadata = {
                    'name': frame_name,
                    'parents': [self.folder_id]
                }
                
                mime_type = mimetypes.guess_type(frame_path)[0] or 'image/jpeg'
                
                # Use simple upload for small files
                media = MediaFileUpload(
                    frame_path,
                    mimetype=mime_type,
                    resumable=False
                )
                
                # Create file with timeout
                request = self.drive_service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id'
                )
                
                # Execute with custom timeout
                file = request.execute(num_retries=0)
                
                with self.upload_lock:
                    self.uploaded_count += 1
                
                return True, None
                
            except HttpError as e:
                if e.resp.status in [500, 502, 503, 504]:
                    # Retry on server errors
                    if attempt < self.max_retries - 1:
                        logger.warning(f"Server error uploading {frame_name}, retrying... (attempt {attempt + 1})")
                        continue
                    else:
                        return False, f"Server error after {self.max_retries} attempts: {str(e)}"
                elif e.resp.status == 403 and 'rateLimitExceeded' in str(e):
                    # Rate limit - wait longer
                    sleep_time = 30 + random.uniform(0, 10)
                    logger.warning(f"Rate limit hit, waiting {sleep_time:.1f} seconds...")
                    time.sleep(sleep_time)
                    continue
                else:
                    # Don't retry on client errors
                    return False, f"HTTP error: {str(e)}"
                    
            except Exception as e:
                if attempt < self.max_retries - 1 and "timeout" in str(e).lower():
                    logger.warning(f"Timeout uploading {frame_name}, retrying... (attempt {attempt + 1})")
                    continue
                else:
                    return False, f"Error: {str(e)}"
        
        return False, f"Failed after {self.max_retries} attempts"
    
    def upload_frames(self, output_dir, frames):
        """Upload frames with optimized concurrency"""
        start_time = time.time()
        total_frames = len(frames)
        
        logger.info(f"Starting optimized upload with {self.max_workers} workers...")
        
        def upload_wrapper(frame):
            frame_path = os.path.join(output_dir, frame)
            success, error = self.upload_single_frame_with_retry(frame_path, frame)
            
            if not success:
                with self.upload_lock:
                    self.failed_count += 1
                    self.failed_frames.append((frame, error))
                    if self.failed_count <= 5:
                        logger.error(f"Failed to upload {frame}: {error}")
            
            # Log progress
            with self.upload_lock:
                current_count = self.uploaded_count + self.failed_count
                if current_count % 10 == 0 or current_count == total_frames:
                    elapsed = time.time() - start_time
                    rate = current_count / max(0.1, elapsed)
                    remaining = (total_frames - current_count) / max(0.1, rate)
                    
                    logger.info(f"Progress: {self.uploaded_count} uploaded, "
                              f"{self.failed_count} failed / {total_frames} total "
                              f"({(current_count/total_frames*100):.1f}%) - "
                              f"{rate:.1f} frames/sec, ~{remaining:.1f} sec remaining")
            
            return frame, success
        
        # Use thread pool with limited workers
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(upload_wrapper, frame): frame for frame in frames}
            
            for future in as_completed(futures):
                try:
                    frame, success = future.result()
                except Exception as e:
                    logger.error(f"Exception in upload thread: {str(e)}")
        
        return time.time() - start_time

def test_upload_methods():
    """Test different upload configurations"""
    output_dir = os.path.expanduser("~/Videos/screenRecordings/screen_recording_2025_06_20_at_5_47_19_am")
    folder_id = "1cSD-WXczrjz8eJwbhWA6NHsQA2_Qnbif"
    
    logger.info("=" * 60)
    logger.info("OPTIMIZED GOOGLE DRIVE UPLOAD TEST")
    logger.info("=" * 60)
    logger.info(f"Source directory: {output_dir}")
    logger.info(f"Target folder ID: {folder_id}")
    
    # Get frames
    frames = sorted([f for f in os.listdir(output_dir) if f.startswith("frame_") and f.endswith(".jpg")])
    logger.info(f"Found {len(frames)} frames to upload")
    
    if not frames:
        logger.error("No frames found")
        return
    
    # Test with 3 workers (optimal for most connections)
    logger.info("\n" + "=" * 60)
    logger.info("TEST: OPTIMIZED CONCURRENT UPLOAD (3 workers)")
    logger.info("=" * 60)
    
    uploader = OptimizedUploader(folder_id, max_workers=3)
    uploader.initialize_service()
    
    upload_time = uploader.upload_frames(output_dir, frames)
    
    logger.info(f"\n✓ UPLOAD COMPLETE!")
    logger.info(f"- Frames uploaded: {uploader.uploaded_count}/{len(frames)}")
    logger.info(f"- Failed uploads: {uploader.failed_count}")
    logger.info(f"- Total time: {upload_time:.2f} seconds")
    logger.info(f"- Average speed: {len(frames)/upload_time:.1f} frames/sec")
    
    if uploader.failed_frames:
        logger.info(f"\nFailed frames:")
        for frame, error in uploader.failed_frames[:10]:
            logger.info(f"  - {frame}: {error}")
        if len(uploader.failed_frames) > 10:
            logger.info(f"  ... and {len(uploader.failed_frames) - 10} more")

if __name__ == "__main__":
    test_upload_methods()