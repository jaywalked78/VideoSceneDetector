from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from app.models.gradio import GradioRequest, GradioResponse, HealthCheckResponse
from app.utils.gradio_client import GradioClient
import logging
import datetime

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/health", response_model=HealthCheckResponse)
async def check_gradio_health():
    """
    Check if the Gradio server is running and accessible
    """
    try:
        is_healthy, details = await GradioClient.check_health()
        timestamp = datetime.datetime.now().isoformat()
        
        return HealthCheckResponse(
            status="healthy" if is_healthy else "unhealthy",
            message=details["message"],
            details=details,
            timestamp=timestamp
        )
    except Exception as e:
        logger.error(f"Error checking Gradio health: {str(e)}")
        return HealthCheckResponse(
            status="error",
            message=f"Error checking Gradio health: {str(e)}",
            timestamp=datetime.datetime.now().isoformat()
        )

@router.get("/gradio-data")
async def get_gradio_data():
    """
    Get data from Gradio with automatic session handling
    """
    try:
        result = await GradioClient.get_data()
        return result
    except Exception as e:
        logger.error(f"Error fetching Gradio data: {str(e)}")
        raise

@router.post("/gradio-data")
async def post_gradio_data(request: GradioRequest):
    """
    Send data to Gradio and get response
    """
    try:
        result = await GradioClient.get_data(
            fn_index=request.fn_index,
            data=request.data
        )
        return result
    except Exception as e:
        logger.error(f"Error posting to Gradio: {str(e)}")
        raise 