# Add this to your FastAPI app to improve the Gradio connection handling

import httpx
import asyncio
from fastapi import FastAPI, HTTPException
import logging
from typing import Optional, Dict, Any, List
import backoff

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gradio-api")

# Constants
GRADIO_URL = "http://localhost:7860"  # Adjust this to your actual Gradio server address
TIMEOUT = 30.0  # Seconds
MAX_RETRIES = 3

# Backoff handler for retry logic
@backoff.on_exception(
    backoff.expo,
    (httpx.ConnectError, httpx.TimeoutException),
    max_tries=MAX_RETRIES
)
async def fetch_gradio_data_with_retry(client: httpx.AsyncClient, session_hash: Optional[str] = None) -> Dict[Any, Any]:
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
        response = await client.post(
            f"{GRADIO_URL}/api/predict",
            json={
                "session_hash": session_hash,
                "fn_index": 0  # Adjust this based on your Gradio app
            },
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

# Your FastAPI endpoint
async def get_gradio_data():
    """Endpoint to fetch Gradio data with connection handling"""
    # Create a connection pool for better performance
    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=10)) as client:
        try:
            # Try to connect to Gradio
            logger.info("Attempting to connect to Gradio server")
            
            # Check if Gradio is accessible first
            health_check = await client.get(f"{GRADIO_URL}/", timeout=5.0)
            if health_check.status_code != 200:
                logger.error(f"Gradio server health check failed: {health_check.status_code}")
                raise HTTPException(status_code=503, detail="Gradio server is not available")
            
            # Proceed with data fetch
            data = await fetch_gradio_data_with_retry(client)
            return data
            
        except asyncio.TimeoutError:
            logger.error("Request to Gradio timed out")
            raise HTTPException(status_code=504, detail="Request to Gradio timed out")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

# Add this to your FastAPI routes
# @app.get("/gradio-data", response_model=Any)
# async def gradio_data_endpoint():
#     return await get_gradio_data()
