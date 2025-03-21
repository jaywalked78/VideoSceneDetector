import httpx
import asyncio
import logging
import json
import sys
from typing import Dict, Any, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("gradio-health-check")

async def check_gradio_health(gradio_url: str = "http://localhost:7860") -> Tuple[bool, Dict[str, Any]]:
    """
    Check if the Gradio server is running and accessible.
    
    Args:
        gradio_url: URL of the Gradio server
        
    Returns:
        Tuple of (is_healthy, details)
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
                    
                    # Try a basic API call with the session
                    if "session_hash" in session_data:
                        predict_response = await client.post(
                            f"{gradio_url}/api/predict",
                            json={
                                "session_hash": session_data["session_hash"],
                                "fn_index": 0
                            },
                            timeout=5.0
                        )
                        result["details"]["predict_status_code"] = predict_response.status_code
            except Exception as e:
                result["details"]["session_error"] = str(e)
            
            # Check if we can get the config
            try:
                config_response = await client.get(f"{gradio_url}/config", timeout=5.0)
                result["details"]["config_status_code"] = config_response.status_code
                
                if config_response.status_code == 200:
                    config = config_response.json()
                    result["details"]["app_version"] = config.get("version", "unknown")
                    result["details"]["components"] = len(config.get("components", []))
            except Exception as e:
                result["details"]["config_error"] = str(e)
            
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

async def check_drive_api_connection(api_url: str = "https://www.googleapis.com/drive/v3/files") -> Tuple[bool, Dict[str, Any]]:
    """
    Check if the Google Drive API is accessible.
    
    Args:
        api_url: Google Drive API URL
        
    Returns:
        Tuple of (is_healthy, details)
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
    # Check Gradio server
    gradio_url = "http://localhost:7860"  # Default Gradio port
    is_gradio_healthy, gradio_result = await check_gradio_health(gradio_url)
    
    # Check Google Drive API
    is_drive_accessible, drive_result = await check_drive_api_connection()
    
    # Combine results
    results = {
        "gradio_server": gradio_result,
        "google_drive_api": drive_result,
        "timestamp": str(datetime.datetime.now()),
        "overall_status": "healthy" if is_gradio_healthy and is_drive_accessible else "unhealthy"
    }
    
    # Print results
    print(json.dumps(results, indent=2))
    
    # Exit with appropriate code
    if not is_gradio_healthy:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    import datetime
    asyncio.run(main())
