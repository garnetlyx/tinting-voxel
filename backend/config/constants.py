"""
Application constants
"""

# API Response Messages
API_SUCCESS = "Success"
API_ERROR_UPLOAD = "Failed to upload image"
API_ERROR_PROCESSING = "Failed to process image"
API_ERROR_GENERATION = "Failed to generate files"

# File Formats
SUPPORTED_IMAGE_FORMATS = ["JPEG", "PNG", "BMP", "GIF"]
OUTPUT_STL_FORMAT = "binary"  # binary or ascii
OUTPUT_ZIP_COMPRESSION = "deflated"  # stored or deflated

# Default Parameters
DEFAULT_LAYER_COUNT = 4
DEFAULT_LAYER_HEIGHT = 0.08  # mm
DEFAULT_PIXEL_SIZE = 0.08    # mm
DEFAULT_MAX_COLORS = 10
DEFAULT_COLOR_THRESHOLD = 50.0
