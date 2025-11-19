"""
FastAPI application for ImageToSTLConverter backend
"""
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from contextlib import asynccontextmanager
import logging

from api.models import (
    ProcessImageResponse,
    DownloadCSVRequest,
    DownloadSTLRequest
)
from services.image_processor import process_image
from services.csv_generator import generate_csv
from services.stl_generator import initialize_color_mapping, generate_stl_zip

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler
    Initialize color mapping on startup
    """
    logger.info("Initializing color mapping reference matrices...")
    initialize_color_mapping(layer_count=4, layer_height=0.08)
    logger.info("Application startup complete")
    yield
    logger.info("Application shutdown")


# Create FastAPI app with lifespan handler
app = FastAPI(
    title="ImageToSTL Converter API",
    description="Backend API for converting images to color-separated STL files",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite default ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "message": "ImageToSTL Converter API"}


@app.post("/api/process-image", response_model=ProcessImageResponse)
async def api_process_image(
    image: UploadFile = File(...),
    maxColors: int = Form(10),
    colorThreshold: float = Form(50),
    pixelSize: float = Form(0.08)
):
    """
    Process uploaded image to extract color blocks

    Args:
        image: Uploaded image file
        maxColors: Maximum number of colors to extract
        colorThreshold: Threshold for merging similar colors
        pixelSize: Physical size of each pixel in mm

    Returns:
        ProcessImageResponse with colorBlocks, processedImage, and imageDimensions
    """
    try:
        # Read image bytes
        image_bytes = await image.read()

        # Process image
        result = process_image(
            image_bytes=image_bytes,
            max_colors=maxColors,
            color_threshold=colorThreshold,
            pixel_size=pixelSize
        )

        logger.info(f"Request parameters: maxColors={maxColors}, colorThreshold={colorThreshold}, pixelSize={pixelSize}")
        logger.info(f"Processed image: {result['imageDimensions']['width']}x{result['imageDimensions']['height']}, "
                   f"extracted {len(result['colorBlocks'])} colors")

        return result

    except Exception as e:
        logger.error(f"Error processing image: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process image: {str(e)}")


@app.post("/api/download-csv")
async def api_download_csv(request: DownloadCSVRequest):
    """
    Generate and download CSV file with color data

    Args:
        request: DownloadCSVRequest with colorBlocks

    Returns:
        CSV file as response
    """
    try:
        # Convert Pydantic models to dicts
        color_blocks = [block.dict() for block in request.colorBlocks]

        # Generate CSV
        csv_content = generate_csv(color_blocks)

        logger.info(f"Generated CSV for {len(color_blocks)} colors")

        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=colors.csv"
            }
        )

    except Exception as e:
        logger.error(f"Error generating CSV: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate CSV: {str(e)}")


@app.post("/api/download-stl")
async def api_download_stl(request: DownloadSTLRequest):
    """
    Generate and download ZIP file containing color-separated STL files

    Args:
        request: DownloadSTLRequest with colorBlocks and parameters

    Returns:
        ZIP file containing STL files
    """
    try:
        # Convert Pydantic models to dicts
        color_blocks = [block.dict() for block in request.colorBlocks]
        image_dimensions = request.imageDimensions.dict()

        # Generate STL ZIP
        zip_content = generate_stl_zip(
            color_blocks=color_blocks,
            layer_height=request.layerHeight,
            pixel_size=request.pixelSize,
            layer_count=request.layerCount,
            image_dimensions=image_dimensions
        )

        logger.info(f"Generated STL ZIP for {len(color_blocks)} colors, "
                   f"{image_dimensions['width']}x{image_dimensions['height']} pixels")

        return Response(
            content=zip_content,
            media_type="application/zip",
            headers={
                "Content-Disposition": "attachment; filename=all_color_blocks.zip"
            }
        )

    except Exception as e:
        logger.error(f"Error generating STL: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate STL: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
