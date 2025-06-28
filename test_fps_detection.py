#!/usr/bin/env python3
"""
Test script for FPS detection using FFprobe and MediaInfo
Tests the video file in ~/Videos/screenRecordings/screen_recording_2025_06_20_at_5_47_19_am
"""

import os
import subprocess
import json
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_ffprobe_fps(video_path: str) -> dict:
    """Test FFprobe FPS detection"""
    logger.info("=" * 60)
    logger.info("TESTING FFPROBE FPS DETECTION")
    logger.info("=" * 60)
    
    results = {
        "method": "FFprobe",
        "success": False,
        "fps": None,
        "avg_frame_rate": None,
        "r_frame_rate": None,
        "raw_output": None,
        "error": None
    }
    
    try:
        ffprobe_cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-select_streams", "v:0", "-show_entries", 
            "stream=avg_frame_rate,r_frame_rate,duration,nb_frames", video_path
        ]
        
        logger.info(f"Running command: {' '.join(ffprobe_cmd)}")
        result = subprocess.run(ffprobe_cmd, capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0:
            data = json.loads(result.stdout)
            results["raw_output"] = data
            
            if 'streams' in data and len(data['streams']) > 0:
                stream = data['streams'][0]
                logger.info(f"Stream data: {stream}")
                
                # Extract avg_frame_rate
                if 'avg_frame_rate' in stream and stream['avg_frame_rate'] != '0/0':
                    fps_str = stream['avg_frame_rate']
                    results["avg_frame_rate"] = fps_str
                    if '/' in fps_str:
                        num, den = fps_str.split('/')
                        fps = float(num) / float(den)
                        results["fps"] = fps
                        logger.info(f"✅ avg_frame_rate: {fps_str} = {fps:.6f} fps")
                        
                        if fps != 60.0:
                            results["success"] = True
                            logger.info(f"✅ ACCEPTED: {fps:.6f} fps (not 60fps)")
                        else:
                            logger.warning(f"⚠️  REJECTED: 60.0 fps detected, continuing search...")
                
                # Extract r_frame_rate  
                if 'r_frame_rate' in stream and stream['r_frame_rate'] != '0/0':
                    fps_str = stream['r_frame_rate']
                    results["r_frame_rate"] = fps_str
                    if '/' in fps_str:
                        num, den = fps_str.split('/')
                        fps = float(num) / float(den)
                        logger.info(f"📊 r_frame_rate: {fps_str} = {fps:.6f} fps")
                        
                        if not results["success"] and fps != 60.0:
                            results["fps"] = fps
                            results["success"] = True
                            logger.info(f"✅ ACCEPTED: {fps:.6f} fps (from r_frame_rate)")
                        elif fps == 60.0:
                            logger.warning(f"⚠️  REJECTED: 60.0 fps from r_frame_rate")
                
                # Additional info
                if 'duration' in stream:
                    logger.info(f"📹 Duration: {stream['duration']} seconds")
                if 'nb_frames' in stream:
                    logger.info(f"📈 Total frames: {stream['nb_frames']}")
            else:
                results["error"] = "No video streams found"
                logger.error("❌ No video streams found in FFprobe output")
        else:
            results["error"] = f"FFprobe failed with return code {result.returncode}: {result.stderr}"
            logger.error(f"❌ FFprobe failed: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        results["error"] = "FFprobe timed out"
        logger.error("❌ FFprobe timed out")
    except Exception as e:
        results["error"] = str(e)
        logger.error(f"❌ FFprobe error: {e}")
    
    return results

def test_mediainfo_fps(video_path: str) -> dict:
    """Test MediaInfo FPS detection"""
    logger.info("=" * 60)
    logger.info("TESTING MEDIAINFO FPS DETECTION")
    logger.info("=" * 60)
    
    results = {
        "method": "MediaInfo",
        "success": False,
        "fps": None,
        "frame_rate": None,
        "frame_rate_original": None,
        "raw_output": None,
        "error": None
    }
    
    try:
        mediainfo_cmd = ["mediainfo", "--Output=JSON", video_path]
        
        logger.info(f"Running command: {' '.join(mediainfo_cmd)}")
        result = subprocess.run(mediainfo_cmd, capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0:
            data = json.loads(result.stdout)
            results["raw_output"] = data
            
            if 'media' in data and 'track' in data['media']:
                for track in data['media']['track']:
                    if track.get('@type') == 'Video' or track.get('type') == 'Video':
                        logger.info(f"Video track found: {track.get('Format', 'Unknown format')}")
                        
                        # Extract frame_rate
                        for field in ['FrameRate', 'frame_rate']:
                            if field in track:
                                fps = float(track[field])
                                results["frame_rate"] = fps
                                logger.info(f"📊 {field}: {fps:.6f} fps")
                                
                                if fps != 60.0:
                                    results["fps"] = fps
                                    results["success"] = True
                                    logger.info(f"✅ ACCEPTED: {fps:.6f} fps (not 60fps)")
                                    break
                                else:
                                    logger.warning(f"⚠️  REJECTED: 60.0 fps detected from {field}")
                        
                        # Extract frame_rate_original if needed
                        if not results["success"]:
                            for field in ['FrameRate_Original', 'frame_rate_original']:
                                if field in track:
                                    fps = float(track[field])
                                    results["frame_rate_original"] = fps
                                    logger.info(f"📊 {field}: {fps:.6f} fps")
                                    
                                    if fps != 60.0:
                                        results["fps"] = fps
                                        results["success"] = True
                                        logger.info(f"✅ ACCEPTED: {fps:.6f} fps (from {field})")
                                        break
                                    else:
                                        logger.warning(f"⚠️  REJECTED: 60.0 fps from {field}")
                        
                        # Additional metadata
                        for info_field, display_name in [
                            ('Width', 'Width'),
                            ('Height', 'Height'), 
                            ('Duration', 'Duration'),
                            ('FrameCount', 'Frame Count'),
                            ('BitRate', 'Bit Rate')
                        ]:
                            if info_field in track:
                                logger.info(f"📹 {display_name}: {track[info_field]}")
                        
                        break
                else:
                    results["error"] = "No video track found"
                    logger.error("❌ No video track found in MediaInfo output")
            else:
                results["error"] = "Invalid MediaInfo output structure"
                logger.error("❌ Invalid MediaInfo output structure")
        else:
            results["error"] = f"MediaInfo failed with return code {result.returncode}: {result.stderr}"
            logger.error(f"❌ MediaInfo failed: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        results["error"] = "MediaInfo timed out"
        logger.error("❌ MediaInfo timed out")
    except Exception as e:
        results["error"] = str(e)
        logger.error(f"❌ MediaInfo error: {e}")
    
    return results

def test_video_file_detection():
    """Find and test the video file"""
    logger.info("🎬 VIDEO FPS DETECTION TEST SCRIPT")
    logger.info("🎬 Testing FFprobe and MediaInfo on screen recording")
    
    # Try to find the video file
    base_dir = Path.home() / "Videos" / "screenRecordings" / "screen_recording_2025_06_20_at_5_47_19_am"
    
    logger.info(f"🔍 Looking for video file in: {base_dir}")
    
    if not base_dir.exists():
        logger.error(f"❌ Directory not found: {base_dir}")
        return
    
    # Look for video files
    video_extensions = ['.mov', '.mp4', '.avi', '.mkv', '.m4v']
    video_files = []
    
    for ext in video_extensions:
        video_files.extend(list(base_dir.glob(f"*{ext}")))
    
    if not video_files:
        logger.error(f"❌ No video files found in {base_dir}")
        logger.info("📁 Contents of directory:")
        for item in base_dir.iterdir():
            logger.info(f"   {item.name}")
        return
    
    # Use the first video file found
    video_path = str(video_files[0])
    logger.info(f"✅ Found video file: {video_path}")
    
    # Get file info
    file_size = os.path.getsize(video_path) / (1024 * 1024)  # MB
    logger.info(f"📊 File size: {file_size:.2f} MB")
    
    # Test both methods
    ffprobe_results = test_ffprobe_fps(video_path)
    mediainfo_results = test_mediainfo_fps(video_path)
    
    # Summary
    logger.info("=" * 60)
    logger.info("FINAL RESULTS SUMMARY")
    logger.info("=" * 60)
    
    logger.info(f"🎯 Video file: {os.path.basename(video_path)}")
    
    # FFprobe results
    if ffprobe_results["success"]:
        logger.info(f"✅ FFprobe: {ffprobe_results['fps']:.6f} fps")
    else:
        logger.info(f"❌ FFprobe: Failed - {ffprobe_results['error']}")
    
    # MediaInfo results  
    if mediainfo_results["success"]:
        logger.info(f"✅ MediaInfo: {mediainfo_results['fps']:.6f} fps")
    else:
        logger.info(f"❌ MediaInfo: Failed - {mediainfo_results['error']}")
    
    # Recommendation
    if ffprobe_results["success"]:
        logger.info(f"🏆 RECOMMENDED FPS: {ffprobe_results['fps']:.6f} fps (from FFprobe)")
    elif mediainfo_results["success"]:
        logger.info(f"🏆 RECOMMENDED FPS: {mediainfo_results['fps']:.6f} fps (from MediaInfo fallback)")
    else:
        logger.info(f"⚠️  FALLBACK FPS: 30.0 fps (detection failed)")
    
    logger.info("=" * 60)

if __name__ == "__main__":
    test_video_file_detection()