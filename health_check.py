#!/usr/bin/env python3
import httpx
import asyncio
import logging
import json
import sys
import datetime
from typing import Dict, Any, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("health-check")

# Constants
API_URL = "http://localhost:8000"  # Your FastAPI service
GRADIO_URL = "http://localhost:7860"  # Gradio server
DRIVE_API_URL = "https://www.googleapis.com/drive/v3/files"

async def check_api_health(api_url: str = API_URL) -> Tuple[bool, Dict[str, Any]]:
    """
    Check if our API server is running
    """
    result = {
        "status": "failed",
        "url": api_url,
        "message": "",
        "details": {}
    }
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Try to connect to the root path
            logger.info(f"Checking API server at {api_url}")
            response = await client.get(f"{api_url}/api/v1/health")
            
            if response.status_code == 200:
                result["status"] = "healthy"
                result["message"] = "API server is running"
                result["details"] = response.json()
                return True, result
            else:
                result["message"] = f"API server returned status code {response.status_code}"
                return False, result
                
    except httpx.ConnectError:
        result["message"] = "Failed to connect to API server"
        return False, result
    except httpx.TimeoutException:
        result["message"] = "Connection to API server timed out"
        return False, result
    except Exception as e:
        result["message"] = f"Unexpected error: {str(e)}"
        return False, result

async def check_gradio_health(gradio_url: str = GRADIO_URL) -> Tuple[bool, Dict[str, Any]]:
    """
    Check if the Gradio server is running and accessible.
    """
    result = {
        "status": "failed",
        "url": gradio_url,
        "message": "",
        "details": {}
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Try to connect to the root path
            logger.info(f"Checking Gradio server at {gradio_url}")
            response = await client.get(f"{gradio_url}/", timeout=5.0)
            
            result["details"]["root_status_code"] = response.status_code
            
            # Try to get session
            try:
                session_response = await client.post(f"{gradio_url}/api/sessions", timeout=5.0)
                result["details"]["session_status_code"] = session_response.status_code
                
                if session_response.status_code == 200:
                    session_data = session_response.json()
                    result["details"]["session_hash"] = session_data.get("session_hash", "not found")
            except Exception as e:
                result["details"]["session_error"] = str(e)
            
            # Final health determination
            if response.status_code == 200:
                result["status"] = "healthy"
                result["message"] = "Gradio server is running"
                return True, result
            else:
                result["message"] = f"Gradio server returned status code {response.status_code}"
                return False, result
                
    except httpx.ConnectError:
        result["message"] = "Failed to connect to Gradio server"
        return False, result
    except httpx.TimeoutException:
        result["message"] = "Connection to Gradio server timed out"
        return False, result
    except Exception as e:
        result["message"] = f"Unexpected error: {str(e)}"
        return False, result

async def check_drive_api_connection(api_url: str = DRIVE_API_URL) -> Tuple[bool, Dict[str, Any]]:
    """
    Check if the Google Drive API is accessible.
    """
    result = {
        "status": "failed",
        "url": api_url,
        "message": "",
        "details": {}
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # This will fail without auth, but we can check if we get an auth error (which means the API is reachable)
            logger.info(f"Checking Google Drive API at {api_url}")
            response = await client.get(api_url, timeout=5.0)
            
            result["details"]["status_code"] = response.status_code
            
            # Google will return 401 if the API is reachable but unauthorized
            if response.status_code == 401:
                result["status"] = "reachable"
                result["message"] = "Google Drive API is reachable but requires authentication"
                return True, result
            elif response.status_code == 200:
                result["status"] = "healthy"
                result["message"] = "Google Drive API is accessible"
                return True, result
            else:
                result["message"] = f"Google Drive API returned unexpected status code {response.status_code}"
                return False, result
                
    except httpx.ConnectError:
        result["message"] = "Failed to connect to Google Drive API"
        return False, result
    except httpx.TimeoutException:
        result["message"] = "Connection to Google Drive API timed out"
        return False, result
    except Exception as e:
        result["message"] = f"Unexpected error: {str(e)}"
        return False, result

async def main():
    # Check API server
    is_api_healthy, api_result = await check_api_health()
    
    # Check Gradio server
    is_gradio_healthy, gradio_result = await check_gradio_health()
    
    # Check Google Drive API
    is_drive_accessible, drive_result = await check_drive_api_connection()
    
    # Combine results
    results = {
        "api_server": api_result,
        "gradio_server": gradio_result,
        "google_drive_api": drive_result,
        "timestamp": str(datetime.datetime.now()),
        "overall_status": "healthy" if (is_api_healthy and is_gradio_healthy and is_drive_accessible) else "unhealthy"
    }
    
    # Print results
    print(json.dumps(results, indent=2))
    
    # Exit with appropriate code
    if not is_api_healthy or not is_gradio_healthy:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main()) 