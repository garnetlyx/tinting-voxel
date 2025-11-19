"""
CSV generation service for color data export
"""
from typing import List, Dict


def generate_csv(color_blocks: List[Dict]) -> str:
    """
    Generate CSV string from color blocks

    Args:
        color_blocks: List of color block dictionaries

    Returns:
        CSV string with header and data rows
    """
    csv_lines = ['Color,R,G,B,Hex,PixelCount']

    for index, color in enumerate(color_blocks):
        csv_lines.append(
            f"Color{index + 1},{color['r']},{color['g']},{color['b']},"
            f"{color['hex']},{color['count']}"
        )

    return '\n'.join(csv_lines)
