from pydantic import BaseModel
from typing import Optional, List, Any, Dict

class GradioRequest(BaseModel):
    """
    Request model for Gradio API
    """
    fn_index: int = 0
    data: List[Any] = []
    session_hash: Optional[str] = None

class GradioResponse(BaseModel):
    """
    Response model for Gradio API
    """
    data: Any
    duration: Optional[float] = None
    is_generating: Optional[bool] = None
    average_duration: Optional[float] = None

class HealthCheckResponse(BaseModel):
    """
    Response model for health check
    """
    status: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None 