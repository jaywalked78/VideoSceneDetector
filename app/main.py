from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import video, gradio
import logging
import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Get configuration from environment variables
API_VERSION = os.getenv("API_VERSION", "1.0.0")
ENABLE_GRADIO = os.getenv("ENABLE_GRADIO", "true").lower() in ("true", "1", "yes")
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() in ("true", "1", "yes")

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(pathname)s:%(lineno)d',
    handlers=[
        logging.StreamHandler()
    ]
)

# Set specific loggers to lower levels for more detailed output
logging.getLogger('app.routers.video').setLevel(logging.DEBUG)
logging.getLogger('app.utils.video_processor').setLevel(logging.DEBUG)
logging.getLogger('app.utils.google_drive').setLevel(logging.DEBUG)
logging.getLogger('httpx').setLevel(logging.INFO)
logging.getLogger('urllib3').setLevel(logging.INFO)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Video Scene Detector",
    description="API for processing videos and extracting frames based on scene detection",
    version=API_VERSION,
    debug=DEBUG_MODE
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(video.router, prefix="/api/v1", tags=["video"])

# Add Gradio integration if enabled
if ENABLE_GRADIO:
    logger.info("Gradio integration enabled")
    app.include_router(gradio.router, prefix="/api/v1/gradio", tags=["gradio"])
else:
    logger.info("Gradio integration disabled")

# Add routes directly to app for easier access (optional)
app.include_router(video.router, tags=["video-direct"])

# Startup event
@app.on_event("startup")
async def startup_event():
    logger.info(f"Starting Video Scene Detector API v{API_VERSION}")
    logger.info(f"Debug mode: {DEBUG_MODE}")
    
    # Check if the credentials file exists
    credentials_path = os.getenv("GOOGLE_CREDENTIALS", "credentials.json")
    if os.path.exists(credentials_path):
        logger.info(f"Google Drive credentials found at {credentials_path}")
    else:
        logger.warning(f"Google Drive credentials not found at {credentials_path}")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Video Scene Detector API") 