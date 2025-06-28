"""
Upload queue manager for streaming frame uploads to Google Drive
"""
import os
import queue
import threading
import time
import logging
import mimetypes
import ssl
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

@dataclass
class UploadTask:
    """Represents a frame upload task"""
    frame_path: str
    frame_name: str
    folder_id: str
    timestamp: float
    retry_count: int = 0

class UploadQueueManager:
    """Manages a queue for uploading frames to Google Drive as they're created"""
    
    def __init__(self, drive_service, folder_id: str, max_retries: int = None):
        self.drive_service = drive_service
        self.folder_id = folder_id
        self.max_retries = max_retries if max_retries is not None else int(os.getenv("MAX_RETRIES", "3"))
        
        # Thread-safe queue for upload tasks
        self.upload_queue = queue.Queue()
        
        # Statistics
        self.stats = {
            'queued': 0,
            'uploaded': 0,
            'failed': 0,
            'retried': 0,
            'start_time': time.time()
        }
        self.stats_lock = threading.Lock()
        
        # Upload worker thread
        self.worker_thread = None
        self.stop_event = threading.Event()
        self.is_processing_complete = False
        
        # Failed uploads tracking
        self.failed_uploads = []
        
    def start(self):
        """Start the upload worker thread"""
        try:
            if self.worker_thread is None or not self.worker_thread.is_alive():
                logger.info("Starting upload queue worker thread...")
                self.worker_thread = threading.Thread(target=self._upload_worker, daemon=True)
                self.worker_thread.start()
                logger.info("Upload queue worker thread created")
                # Give the thread a moment to start
                time.sleep(0.5)  # Increased delay
                if not self.worker_thread.is_alive():
                    raise Exception("Worker thread failed to start")
                logger.info("✅ Upload queue worker is alive and ready")
        except Exception as e:
            logger.error(f"❌ Failed to start upload queue worker: {str(e)}")
            raise
    
    def stop(self):
        """Stop the upload worker thread"""
        logger.info("Stopping upload queue worker...")
        self.stop_event.set()
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=10)
        logger.info("Upload queue worker stopped")
    
    def add_frame(self, frame_path: str, frame_name: str):
        """Add a frame to the upload queue"""
        task = UploadTask(
            frame_path=frame_path,
            frame_name=frame_name,
            folder_id=self.folder_id,
            timestamp=time.time()
        )
        
        self.upload_queue.put(task)
        
        with self.stats_lock:
            self.stats['queued'] += 1
        
        logger.info(f"Added {frame_name} to upload queue (queue size: {self.upload_queue.qsize()}, total queued: {self.stats['queued']})")
        
        # Log queue status periodically
        if self.stats['queued'] % 10 == 0:
            self._log_status()
    
    def add_frames_batch(self, frames: list):
        """Add multiple frames to the queue at once"""
        for frame_path, frame_name in frames:
            self.add_frame(frame_path, frame_name)
        
        logger.info(f"Added batch of {len(frames)} frames to upload queue")
    
    def set_processing_complete(self):
        """Signal that video processing is complete"""
        self.is_processing_complete = True
        logger.info("Video processing marked as complete")
    
    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """Wait for all uploads to complete"""
        logger.info("Waiting for all uploads to complete...")
        start_time = time.time()
        
        while True:
            # Check if queue is empty and processing is done
            if self.upload_queue.empty() and self.is_processing_complete:
                # Give a small delay to ensure last uploads finish
                time.sleep(2)
                if self.upload_queue.empty():
                    logger.info("All uploads completed")
                    return True
            
            # Check timeout
            if timeout and (time.time() - start_time) > timeout:
                logger.warning(f"Upload completion timeout after {timeout} seconds")
                return False
            
            time.sleep(1)
            self._log_status()
    
    def get_statistics(self) -> Dict:
        """Get current upload statistics"""
        with self.stats_lock:
            stats = self.stats.copy()
            stats['queue_size'] = self.upload_queue.qsize()
            stats['elapsed_time'] = time.time() - stats['start_time']
            
            if stats['uploaded'] > 0:
                stats['avg_upload_time'] = stats['elapsed_time'] / stats['uploaded']
            else:
                stats['avg_upload_time'] = 0
                
            return stats
    
    def _upload_worker(self):
        """Worker thread that processes the upload queue"""
        logger.info("🚀 Upload worker thread started and ready to process frames")
        
        try:
            while not self.stop_event.is_set():
                logger.debug("Upload worker: Checking for new tasks...")
                try:
                    # Get task from queue with timeout
                    task = self.upload_queue.get(timeout=1)
                    logger.info(f"Processing upload task: {task.frame_name}")
                    
                    # Upload the frame
                    success = self._upload_single_frame(task)
                    
                    if success:
                        with self.stats_lock:
                            self.stats['uploaded'] += 1
                    else:
                        # Retry logic
                        task.retry_count += 1
                        if task.retry_count < self.max_retries:
                            with self.stats_lock:
                                self.stats['retried'] += 1
                            # Re-queue with delay
                            time.sleep(2 ** task.retry_count)  # Exponential backoff
                            self.upload_queue.put(task)
                        else:
                            with self.stats_lock:
                                self.stats['failed'] += 1
                            self.failed_uploads.append({
                                'frame': task.frame_name,
                                'path': task.frame_path,
                                'timestamp': datetime.now().isoformat()
                            })
                    
                    self.upload_queue.task_done()
                    
                except queue.Empty:
                    # No items in queue, continue
                    continue
                except Exception as e:
                    logger.error(f"Error in upload worker: {str(e)}")
                    time.sleep(1)
        except Exception as e:
            logger.error(f"Fatal error in upload worker: {str(e)}")
        finally:
            logger.info("Upload worker thread stopped")
    
    def _upload_single_frame(self, task: UploadTask) -> bool:
        """Upload a single frame to Google Drive"""
        try:
            # Check if file exists
            if not os.path.exists(task.frame_path):
                logger.error(f"Frame file not found: {task.frame_path}")
                return False
            
            # Prepare metadata
            file_metadata = {
                'name': task.frame_name,
                'parents': [task.folder_id]
            }
            
            # Determine MIME type
            mime_type = mimetypes.guess_type(task.frame_path)[0]
            if not mime_type:
                mime_type = 'image/jpeg'
            
            # Create media upload object (simple upload for small files)
            media = MediaFileUpload(
                task.frame_path,
                mimetype=mime_type,
                resumable=False
            )
            
            # Upload the file
            file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            logger.info(f"✅ Successfully uploaded {task.frame_name} to Google Drive")
            return True
            
        except HttpError as e:
            if e.resp.status == 403 and 'rateLimitExceeded' in str(e):
                logger.warning(f"Rate limit hit, will retry {task.frame_name}")
                time.sleep(10)
                return False
            else:
                logger.error(f"HTTP error uploading {task.frame_name}: {str(e)}")
                return False
        except ssl.SSLError as e:
            logger.error(f"SSL error uploading {task.frame_name}: {str(e)}")
            # SSL errors often transient, retry
            return False
        except Exception as e:
            logger.error(f"Error uploading {task.frame_name}: {str(e)}")
            return False
    
    def _log_status(self):
        """Log current queue status"""
        stats = self.get_statistics()
        logger.info(
            f"Upload Queue Status - "
            f"Queued: {stats['queued']}, "
            f"Uploaded: {stats['uploaded']}, "
            f"Failed: {stats['failed']}, "
            f"In Queue: {stats['queue_size']}, "
            f"Rate: {stats['uploaded']/max(1, stats['elapsed_time']):.1f} frames/sec"
        )