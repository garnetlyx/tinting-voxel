"""
CSV generation service for color data export
"""
import csv
import io


def generate_csv(color_blocks: list[dict]) -> str:
    """
    Generate CSV string from color blocks

    Args:
        color_blocks: List of color block dictionaries

    Returns:
        CSV string with header and data rows
    """
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)
    writer.writerow(['Color', 'R', 'G', 'B', 'Hex', 'PixelCount'])

    for index, color in enumerate(color_blocks):
        writer.writerow([
            f"Color{index + 1}",
            color['r'],
            color['g'],
            color['b'],
            color['hex'],
            color['count'],
        ])

    return output.getvalue().rstrip('\r\n')
