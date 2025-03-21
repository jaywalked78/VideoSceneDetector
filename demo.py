#!/usr/bin/env python3
import requests
import json
import time
import argparse
import os

def demo_video_processing(video_id, api_url="http://localhost:8000"):
    """Demo the video processing functionality with Google Drive"""
    endpoint = f"{api_url}/api/v1/process-drive-video"
    
    payload = {
        "file_id": video_id,
        "destination_folder": "/home/jason/Videos/screenRecordings",
        "callback_url": "http://localhost:5678/webhook/9268d2b1-e4de-421e-9685-4c5aa5e79289",
        "scene_threshold": 0.4
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    print(f"Sending request to process video {video_id} from Google Drive...")
    response = requests.post(endpoint, json=payload, headers=headers)
    
    if response.status_code == 200:
        result = response.json()
        print(f"Request successful: {json.dumps(result, indent=2)}")
        return True
    else:
        print(f"Request failed: {response.status_code} - {response.text}")
        return False

def demo_gradio_integration(api_url="http://localhost:8000"):
    """Demo the Gradio integration functionality"""
    # First check Gradio health
    health_endpoint = f"{api_url}/api/v1/gradio/health"
    
    print("Checking Gradio server health...")
    response = requests.get(health_endpoint)
    
    if response.status_code == 200:
        health_result = response.json()
        print(f"Gradio health check: {health_result['status']}")
        
        if health_result['status'] != "healthy":
            print("Gradio server is not healthy, skipping data test")
            return False
    else:
        print(f"Gradio health check failed: {response.status_code} - {response.text}")
        return False
    
    # Now try getting data from Gradio
    data_endpoint = f"{api_url}/api/v1/gradio/gradio-data"
    
    print("Getting data from Gradio...")
    response = requests.get(data_endpoint)
    
    if response.status_code == 200:
        data_result = response.json()
        print(f"Received data from Gradio: {json.dumps(data_result, indent=2)}")
        return True
    else:
        print(f"Failed to get data from Gradio: {response.status_code} - {response.text}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Demo the Video Scene Detector API")
    parser.add_argument("--video-id", help="Google Drive video ID to process")
    parser.add_argument("--api-url", default="http://localhost:8000", help="API server URL")
    parser.add_argument("--demo-gradio", action="store_true", help="Demo Gradio integration")
    parser.add_argument("--demo-video", action="store_true", help="Demo video processing")
    
    args = parser.parse_args()
    
    # If no specific demo is requested, run both if possible
    run_gradio_demo = args.demo_gradio or (not args.demo_video and not args.demo_gradio)
    run_video_demo = args.demo_video or (not args.demo_video and not args.demo_gradio and args.video_id)
    
    # Check API health first
    try:
        health_response = requests.get(f"{args.api_url}/api/v1/health")
        if health_response.status_code != 200:
            print(f"API server is not healthy: {health_response.status_code} - {health_response.text}")
            return
    except Exception as e:
        print(f"Failed to connect to API server: {str(e)}")
        return
    
    # Run the demos
    if run_gradio_demo:
        print("\n=== Gradio Integration Demo ===\n")
        demo_gradio_integration(args.api_url)
    
    if run_video_demo:
        if not args.video_id:
            print("\nError: Video ID is required for video processing demo")
            print("Use --video-id GOOGLE_DRIVE_FILE_ID to specify a video")
            return
            
        print("\n=== Video Processing Demo ===\n")
        demo_video_processing(args.video_id, args.api_url)

if __name__ == "__main__":
    main() 