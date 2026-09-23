"""CSV download endpoint."""
import logging

from fastapi import APIRouter, Request
from fastapi.responses import Response

from api.error_handlers import handle_api_errors
from api.rate_limiter import limiter
from api.models import DownloadCSVRequest
from services.csv_generator import generate_csv

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Downloads"])

@router.post("/download-csv")
@limiter.limit("20/minute")
@handle_api_errors("generating CSV")
async def api_download_csv(request: Request, body: DownloadCSVRequest):
    """Generate and download CSV file with color data."""
    color_blocks = [block.model_dump() for block in body.colorBlocks]
    csv_content = generate_csv(color_blocks)

    logger.info("Generated CSV for %d colors", len(color_blocks))

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=colors.csv"}
    )
