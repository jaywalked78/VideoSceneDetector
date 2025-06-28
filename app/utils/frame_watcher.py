"""
Frame file watcher that monitors directories for new frame files
"""
import os
import time
import threading
import logging
from typing import Callable, Set
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class FrameWatcher:
    """Watches a directory for new frame files and triggers callbacks"""
    
    def __init__(self, watch_dir: str, callback: Callable[[str, str], None], 
                 file_pattern: str = "frame_*.jpg", poll_interval: float = None):
        self.watch_dir = Path(watch_dir)
        self.callback = callback
        self.file_pattern = file_pattern
        self.poll_interval = poll_interval if poll_interval is not None else float(os.getenv("FRAME_WATCHER_POLL_INTERVAL", "0.5"))
        
        # Track processed files
        self.processed_files: Set[str] = set()
        self.processed_lock = threading.Lock()
        
        # Watcher thread
        self.watcher_thread = None
        self.stop_event = threading.Event()
        
    def start(self):
        """Start watching the directory"""
        if not self.watch_dir.exists():
            logger.error(f"Watch directory does not exist: {self.watch_dir}")
            return
        
        if self.watcher_thread is None or not self.watcher_thread.is_alive():
            self.watcher_thread = threading.Thread(target=self._watch_loop, daemon=True)
            self.watcher_thread.start()
            logger.info(f"Started watching directory: {self.watch_dir}")
    
    def stop(self):
        """Stop watching the directory"""
        logger.info("Stopping frame watcher...")
        self.stop_event.set()
        if self.watcher_thread and self.watcher_thread.is_alive():
            self.watcher_thread.join(timeout=5)
        logger.info("Frame watcher stopped")
    
    def _watch_loop(self):
        """Main watch loop that monitors for new files"""
        logger.info(f"Frame watcher started for pattern: {self.file_pattern}")
        
        # Process any existing files first
        self._scan_directory()
        
        while not self.stop_event.is_set():
            try:
                self._scan_directory()
                time.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Error in frame watcher: {str(e)}")
                time.sleep(1)
    
    def _scan_directory(self):
        """Scan directory for new frame files"""
        try:
            # Get all files matching the pattern
            frame_files = sorted(self.watch_dir.glob(self.file_pattern))
            
            # Batch process new files for efficiency
            new_files = []
            
            with self.processed_lock:
                for file_path in frame_files:
                    file_str = str(file_path)
                    if file_str not in self.processed_files:
                        # Check if file is fully written (size stable)
                        if self._is_file_ready(file_path):
                            self.processed_files.add(file_str)
                            new_files.append((str(file_path), file_path.name))
            
            # Process new files
            if new_files:
                if len(new_files) == 1:
                    # Single file
                    self.callback(new_files[0][0], new_files[0][1])
                else:
                    # Batch of files
                    logger.info(f"Found batch of {len(new_files)} new frames")
                    for frame_path, frame_name in new_files:
                        self.callback(frame_path, frame_name)
                        
        except Exception as e:
            logger.error(f"Error scanning directory: {str(e)}")
    
    def _is_file_ready(self, file_path: Path) -> bool:
        """Check if a file is fully written and ready for processing"""
        try:
            if not file_path.exists() or file_path.stat().st_size == 0:
                return False

            # Check file size stability
            size1 = file_path.stat().st_size
            stability_time = float(os.getenv("FRAME_WATCHER_STABILITY_TIME", "0.2"))
            time.sleep(stability_time)  # Configurable stability check

            if not file_path.exists():
                return False

            size2 = file_path.stat().st_size

            # Also check modification time
            mtime = file_path.stat().st_mtime
            current_time = time.time()

            # File must be stable and not modified in last configurable seconds
            stability_threshold = float(os.getenv("FRAME_WATCHER_STABILITY_TIME", "0.2"))
            return size1 == size2 and size1 > 0 and (current_time - mtime) > stability_threshold

        except Exception:
            return False
    
    def get_processed_count(self) -> int:
        """Get the number of processed files"""
        with self.processed_lock:
            return len(self.processed_files)