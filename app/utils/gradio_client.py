import httpx
import asyncio
import logging
import os
import backoff
from typing import Dict, Any, Optional, List, Tuple
from fastapi import HTTPException

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gradio-client")

# Constants
GRADIO_URL = os.getenv("GRADIO_URL", "http://localhost:7860")
TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "300"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

class GradioClient:
    """Client for interacting with Gradio servers with robust connection handling"""
    
    @staticmethod
    async def check_health(gradio_url: str = GRADIO_URL) -> Tuple[bool, Dict[str, Any]]:
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
    
    @staticmethod
    @backoff.on_exception(
        backoff.expo,
        (httpx.ConnectError, httpx.TimeoutException),
        max_tries=MAX_RETRIES
    )
    async def fetch_data_with_retry(
        client: httpx.AsyncClient, 
        fn_index: int = 0,
        data: List[Any] = None,
        session_hash: Optional[str] = None
    ) -> Dict[Any, Any]:
        """
        Fetch data from Gradio with retry logic
        """
        try:
            # First, get a session hash if not provided
            if not session_hash:
                logger.info("Getting new session hash from Gradio")
                response = await client.post(
                    f"{GRADIO_URL}/api/sessions",
                    timeout=TIMEOUT
                )
                response.raise_for_status()
                session_data = response.json()
                session_hash = session_data.get("session_hash")
                
                if not session_hash:
                    logger.error("Failed to get session hash from Gradio")
                    raise HTTPException(status_code=500, detail="Failed to get session hash from Gradio")
            
            logger.info(f"Using session hash: {session_hash}")
            
            # Now fetch the actual data
            payload = {
                "session_hash": session_hash,
                "fn_index": fn_index
            }
            
            # Add data if provided
            if data:
                payload["data"] = data
                
            response = await client.post(
                f"{GRADIO_URL}/api/predict",
                json=payload,
                timeout=TIMEOUT
            )
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, 
                           detail=f"Gradio server returned error: {e.response.text}")
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.error(f"Connection error: {str(e)}")
            raise HTTPException(status_code=500, detail="All connection attempts failed")
    
    @staticmethod
    async def get_data(fn_index: int = 0, data: List[Any] = None):
        """Get data from Gradio with connection handling"""
        # Create a connection pool for better performance
        async with httpx.AsyncClient(limits=httpx.Limits(max_connections=10)) as client:
            try:
                # Check if Gradio is accessible first
                logger.info("Checking if Gradio server is accessible")
                try:
                    health_check = await client.get(f"{GRADIO_URL}/", timeout=5.0)
                    if health_check.status_code != 200:
                        logger.error(f"Gradio server health check failed: {health_check.status_code}")
                        raise HTTPException(status_code=503, detail="Gradio server is not available")
                except Exception as e:
                    logger.error(f"Gradio server health check failed: {str(e)}")
                    raise HTTPException(status_code=503, detail=f"Gradio server is not available: {str(e)}")
                
                # Proceed with data fetch
                return await GradioClient.fetch_data_with_retry(client, fn_index, data)
                
            except asyncio.TimeoutError:
                logger.error("Request to Gradio timed out")
                raise HTTPException(status_code=504, detail="Request to Gradio timed out")
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}") 