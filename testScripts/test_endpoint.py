import requests
import json

# Test local endpoint
def test_process_drive_video():
    # URL with the /api/v1 prefix
    url1 = "http://localhost:8000/api/v1/process-drive-video"
    
    # URL without the prefix (direct)
    url2 = "http://localhost:8000/process-drive-video"
    
    # Prepare the data
    data = {
        "file_id": "1QGxh9whlg5U6mAs_jLSDRkomyJeutlDf",
        "destination_folder": "/home/jason/Videos/screenRecordings",
        "callback_url": "http://localhost:5678/webhook/9268d2b1-e4de-421e-9685-4c5aa5e79289",
        "scene_threshold": 0.4
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    # Test both URLs
    print(f"Testing URL: {url1}")
    try:
        response1 = requests.post(url1, json=data, headers=headers)
        print(f"Status Code: {response1.status_code}")
        print(f"Response: {response1.text[:100]}...")
    except Exception as e:
        print(f"Error: {str(e)}")
    
    print("\n---\n")
    
    print(f"Testing URL: {url2}")
    try:
        response2 = requests.post(url2, json=data, headers=headers)
        print(f"Status Code: {response2.status_code}")
        print(f"Response: {response2.text[:100]}...")
    except Exception as e:
        print(f"Error: {str(e)}")

# Get available routes
def list_available_routes():
    url = "http://localhost:8000/openapi.json"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            api_spec = response.json()
            print("Available routes:")
            for path, methods in api_spec.get("paths", {}).items():
                print(f"  {path}")
    except Exception as e:
        print(f"Error retrieving routes: {str(e)}")

if __name__ == "__main__":
    print("Testing API Endpoints")
    print("=====================")
    list_available_routes()
    print("\n=====================\n")
    test_process_drive_video() 