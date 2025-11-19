from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import StreamingResponse
import io
import numpy as np
from PIL import Image
from sklearn.cluster import KMeans
from stl import mesh
import zipfile

app = FastAPI()

def generate_pixel_mesh(x, y, pixel_size, layer_height, z_offset):
    """Creates a 3D cube mesh for a single pixel."""
    x1, x2 = x * pixel_size, (x + 1) * pixel_size
    y1, y2 = y * pixel_size, (y + 1) * pixel_size
    z1, z2 = z_offset, z_offset + layer_height

    vertices = np.array([
        [x1, y1, z1], [x2, y1, z1], [x2, y2, z1], [x1, y2, z1],
        [x1, y1, z2], [x2, y1, z2], [x2, y2, z2], [x1, y2, z2]
    ])
    faces = np.array([
        [0, 3, 1], [1, 3, 2], [0, 4, 7], [0, 7, 3],
        [4, 5, 6], [4, 6, 7], [5, 1, 2], [5, 2, 6],
        [2, 3, 6], [3, 7, 6], [0, 1, 5], [0, 5, 4]
    ])
    
    cube = mesh.Mesh(np.zeros(faces.shape[0], dtype=mesh.Mesh.dtype))
    for i, f in enumerate(faces):
        for j in range(3):
            cube.vectors[i][j] = vertices[f[j], :]
    return cube

def merge_meshes(meshes):
    """Combines a list of mesh objects into a single one."""
    return mesh.Mesh(np.concatenate([m.data for m in meshes]))

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.post("/api/process-image/")
async def process_image(
    image: UploadFile = File(...),
    maxColors: int = Form(10),
    layerHeight: float = Form(0.08),
    pixelSize: float = Form(1.0), # Changed default for more visible cubes
):
    # 1. Read image
    image_data = await image.read()
    img = Image.open(io.BytesIO(image_data)).convert('RGB')
    
    # 2. Process colors using KMeans
    pixels = np.array(img).reshape(-1, 3)
    kmeans = KMeans(n_clusters=maxColors, random_state=0, n_init=10)
    kmeans.fit(pixels)
    dominant_colors = kmeans.cluster_centers_.astype(int)
    labels = kmeans.labels_
    
    pixel_groups = {i: [] for i in range(len(dominant_colors))}
    width, height = img.size
    for i, label in enumerate(labels):
        x = i % width
        # Invert Y-axis to match image coordinates (top-left origin)
        y = height - 1 - (i // width)
        pixel_groups[label].append((x, y))

    # 3. Generate STLs and Zip them
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # This part is a placeholder for multi-layer logic.
        # For now, we create one layer per color.
        # A more advanced implementation might stack them.
        for i, (color_idx, pixels) in enumerate(pixel_groups.items()):
            if not pixels:
                continue

            color = dominant_colors[color_idx]
            
            # Generate a mesh for each pixel in the group
            pixel_meshes = [generate_pixel_mesh(px, py, pixelSize, layerHeight, i * layerHeight) for px, py in pixels]
            
            # Merge all pixel meshes for this color
            combined_mesh = merge_meshes(pixel_meshes)
            
            # Save mesh to an in-memory file
            stl_buffer = io.BytesIO()
            combined_mesh.save("", fh=stl_buffer)
            stl_buffer.seek(0)
            
            # Add the in-memory STL file to the zip
            filename = f"color_{color[0]}_{color[1]}_{color[2]}.stl"
            zip_file.writestr(filename, stl_buffer.read())

    zip_buffer.seek(0)

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=stls.zip"}
    )
