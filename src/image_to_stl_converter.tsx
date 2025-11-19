import React, { useState, useRef } from 'react';
import { Upload, Download, Settings, Palette } from 'lucide-react';
import JSZip from "jszip";

const ImageToSTLConverter = () => {
  const [image, setImage] = useState(null);
  const [processing, setProcessing] = useState(false);
  const [colorBlocks, setColorBlocks] = useState([]);
  const [processedImageUrl, setProcessedImageUrl] = useState(null);
  const [maxColors, setMaxColors] = useState(50);
  const [colorThreshold, setColorThreshold] = useState(50);
  const [maxCanvasLength, setMaxLength] = useState(400);
  const [layerHeight, setLayerDepth] = useState(0.1);
  const [pixelSize, setPixelSize] = useState(1);
  const [showSettings, setShowSettings] = useState(true);
  const canvasRef = useRef(null);
  const previewCanvasRef = useRef(null);
  const fileInputRef = useRef(null);
  type Vec3 = [number, number, number];
  type Face = [number, number, number];


  // Handle image upload
  const handleImageUpload = (e: { target: { files: any[]; }; }) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        const img = new Image();
        img.onload = () => {
          setImage(img);
          processImage(img);
        };
        img.src = event.target.result;
      };
      reader.readAsDataURL(file);
    }
  };

  // Color distance calculation
  const colorDistance = (c1: { r: number; g: number; b: number; }, c2: { r: number; g: number; b: number; }) => {
    return Math.sqrt(
      Math.pow(c1.r - c2.r, 2) +
      Math.pow(c1.g - c2.g, 2) +
      Math.pow(c1.b - c2.b, 2)
    );
  };

  const clusterAvgColor = (cluster: any[]) => {
    return {
      r: Math.round(cluster.reduce((sum, c) => sum + c.r, 0) / cluster.length),
      g: Math.round(cluster.reduce((sum, c) => sum + c.g, 0) / cluster.length),
      b: Math.round(cluster.reduce((sum, c) => sum + c.b, 0) / cluster.length),
      count: cluster.reduce((sum, c) => sum + c.count, 0),
      pixels: cluster.flatMap(c => c.pixels)
    };
  };

  // Merge similar colors
  const mergeSimilarColors = (colors: any[], threshold: number) => {
    const merged: { r: number; g: number; b: number; count: any; pixels: any[]; }[] = [];
    const used = new Set();
    const dark: any[] = [];


    colors.forEach((color, idx) => {
      if (used.has(idx)) return;
      used.add(idx);

      if (isDarkNeutralColor(color)) {
        dark.push(color);

        for (let i = idx + 1; i < colors.length; i++) {
          if (used.has(i)) continue;

          const otherColor = colors[i];

          if (isDarkNeutralColor(otherColor)) {
            dark.push(otherColor);
            used.add(i);
          }
        }

        // Calculate average color
        const avg = clusterAvgColor(dark);
        merged.push(avg);
      } else {
        const cluster = [color];

        for (let i = idx + 1; i < colors.length; i++) {
          if (used.has(i)) continue;

          const otherColor = colors[i];

          if (colorDistance(color, otherColor) < threshold) {
            cluster.push(otherColor);
            used.add(i);
          }
        }

        // Calculate average color
        const avg = clusterAvgColor(cluster);
        merged.push(avg);
      }

    });

    return merged;
  };

  const isDarkNeutralColor = (color: { r: number; g: number; b: number; },
    neutralThreshold = 35, darkThreshold = 150) => {
    const dim = (color.r + color.g + color.b) < darkThreshold;
    const max = Math.max(color.r, color.g, color.b);
    const min = Math.min(color.r, color.g, color.b);
    const netural = (max - min) < neutralThreshold;
    return dim && netural;
  };


  // Reassign noise colors to nearest major color
  const reassignColors = (mainColors: any[], restColors: any[]) => {

    // Reassign rest color to nearest main color
    restColors.forEach((tbdColor: { pixels: any[]; }) => {
      tbdColor.pixels.forEach((pixel: any) => {
        // Find nearest main color
        let minDist = Infinity;
        let nearestColorIdx = 0;

        mainColors.forEach((mainColor: any, idx: number) => {
          const dist = colorDistance(tbdColor, mainColor);
          if (dist < minDist) {
            minDist = dist;
            nearestColorIdx = idx;
          }
        });

        // Add pixel to nearest color
        mainColors[nearestColorIdx].pixels.push(pixel);
        mainColors[nearestColorIdx].count++;
      });
    });

    return mainColors;
  };

  // Process image to extract color blocks
  const processImage = async (img: HTMLImageElement) => {
    setProcessing(true);

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');

    // Resize for processing
    // const scale = Math.min(maxCanvasLength / img.width, maxCanvasLength / img.height);
    const scale = 1;
    canvas.width = img.width * scale;
    canvas.height = img.height * scale;

    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const pixels = imageData.data;

    // Extract unique colors with pixel positions
    const colorMap = new Map();

    for (let i = 0; i < pixels.length; i += 4) {
      const r = pixels[i];
      const g = pixels[i + 1];
      const b = pixels[i + 2];
      const a = pixels[i + 3];

      const key = `${r},${g},${b}`;
      const x = (i / 4) % canvas.width;
      const y = Math.floor((i / 4) / canvas.width);

      if (!colorMap.has(key)) {
        colorMap.set(key, { r, g, b, count: 0, pixels: [] });
      }
      const color = colorMap.get(key);
      color.count++;
      color.pixels.push({ x, y });
    }

    // Convert to array
    let colors = Array.from(colorMap.values());

    // Step 1: Merge similar colors
    colors = mergeSimilarColors(colors, colorThreshold);

    // Step 2: Sort by frequency
    colors.sort((a, b) => b.count - a.count);

    // Step 3: Limit to max colors
    const mainColors = colors.slice(0, maxColors);
    const restColors = colors.slice(maxColors);

    // Step 4: Reassign remaining colors (noise) to nearest main color
    colors = reassignColors(mainColors, restColors);

    setColorBlocks(colors);

    // Generate processed image preview
    generateProcessedPreview(colors, canvas.width, canvas.height);

    setProcessing(false);
  };

  // Generate processed image preview
  const generateProcessedPreview = (colors: any[], width: number, height: number) => {
    const previewCanvas = previewCanvasRef.current;
    const ctx = previewCanvas.getContext('2d');
    previewCanvas.width = width;
    previewCanvas.height = height;

    // Create color mapping for each pixel
    const imageData = ctx.createImageData(width, height);
    const pixelColorMap = new Map();

    // Map each pixel to its color
    colors.forEach((color: { pixels: { x: any; y: any; }[]; }) => {
      color.pixels.forEach(({ x, y }) => {
        pixelColorMap.set(`${x},${y}`, color);
      });
    });

    // Fill the preview canvas
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const key = `${x},${y}`;
        const color = pixelColorMap.get(key);
        const i = (y * width + x) * 4;

        if (color) {
          imageData.data[i] = color.r;
          imageData.data[i + 1] = color.g;
          imageData.data[i + 2] = color.b;
          imageData.data[i + 3] = 255;
        } else {
          imageData.data[i + 3] = 0; // transparent
        }
      }
    }

    ctx.putImageData(imageData, 0, 0);
    setProcessedImageUrl(previewCanvas.toDataURL());
  };

  const generateSVGPath = (pixels: { x: any; y: any; }[], width: number, height: number) => {
    // Create a grid map
    const grid = Array(height).fill(null).map(() => Array(width).fill(false));
    pixels.forEach(({ x, y }) => {
      if (y < height && x < width) grid[y][x] = true;
    });

    // Simple contour following (could be improved with marching squares)
    let path = '';
    const visited = Array(height).fill(null).map(() => Array(width).fill(false));

    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        if (grid[y][x] && !visited[y][x]) {
          // Start a new path
          path += `M ${x} ${y} `;
          let cx = x, cy = y;
          visited[cy][cx] = true;

          // Draw rectangle for each pixel (simplified)
          path += `L ${x + 1} ${y} L ${x + 1} ${y + 1} L ${x} ${y + 1} Z `;
        }
      }
    }

    return path;
  };

  function generateSTLByColor(color: never) {
    const stls: ArrayBuffer[] = [];

    color.pixels.forEach(({ x, y }) => {
      const x1 = x, x2 = x + pixelSize;
      const y1 = y, y2 = y + pixelSize;
      const z1 = 0, z2 = layerHeight;
      const xrange = [x1, x2];
      const yrange = [y1, y2];
      const zrange = [z1, z2];
      const buffer = generateBoxSTL(xrange, yrange, zrange);
      stls.push(buffer);
    });
    return mergeSTL(stls);
  }


  // Merge multiple STL ArrayBuffers into a single valid STL
  function mergeSTL(buffers: ArrayBuffer[]): ArrayBuffer {
    // Skip empty
    const validBuffers = buffers.filter(b => b.byteLength >= 84);

    // Count total triangles
    let totalTriangles = 0;
    const parts: Uint8Array[] = [];

    for (const buf of validBuffers) {
      const view = new DataView(buf);
      const triCount = view.getUint32(80, true);
      totalTriangles += triCount;

      // extract triangle data part (after 84-byte header)
      const body = new Uint8Array(buf, 84);
      parts.push(body);
    }

    // Allocate new STL buffer
    const totalBytes = 84 + totalTriangles * 50;
    const output = new ArrayBuffer(totalBytes);
    const outView = new DataView(output);

    // Write header (80 bytes are blank)
    // Write total triangle count
    outView.setUint32(80, totalTriangles, true);

    // Write all triangle bodies
    let offset = 84;
    const outputArray = new Uint8Array(output);

    for (const p of parts) {
      outputArray.set(p, offset);
      offset += p.byteLength;
    }

    return output;
  }

  function generateBoxSTL(
    xrange: [number, number],
    yrange: [number, number],
    zrange: [number, number]
  ): ArrayBuffer {

    const [x1, x2] = xrange;
    const [y1, y2] = yrange;
    const [z1, z2] = zrange;

    // 8 vertices
    const vertices: Vec3[] = [
      [x1, y1, z1],
      [x2, y1, z1],
      [x2, y2, z1],
      [x1, y2, z1],
      [x1, y1, z2],
      [x2, y1, z2],
      [x2, y2, z2],
      [x1, y2, z2]
    ];

    // 12 triangular faces
    const faces: Face[] = [
      [0, 3, 1], [1, 3, 2],    // bottom
      [0, 4, 7], [0, 7, 3],    // left
      [4, 5, 6], [4, 6, 7],    // top
      [5, 1, 2], [5, 2, 6],    // right
      [2, 3, 6], [3, 7, 6],    // back
      [0, 1, 5], [0, 5, 4]     // front
    ];

    // STL binary header: 80 bytes + uint32 triangle count
    const tris = faces.length;
    const buffer = new ArrayBuffer(84 + tris * 50);
    const view = new DataView(buffer);

    // Write triangle count
    view.setUint32(80, tris, true);

    let offset = 84;

    // Calculate normal of a triangle
    function computeNormal(a: Vec3, b: Vec3, c: Vec3): Vec3 {
      const u: Vec3 = [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
      const v: Vec3 = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
      const nx = u[1] * v[2] - u[2] * v[1];
      const ny = u[2] * v[0] - u[0] * v[2];
      const nz = u[0] * v[1] - u[1] * v[0];
      const len = Math.sqrt(nx * nx + ny * ny + nz * nz) || 1;
      return [nx / len, ny / len, nz / len];
    }

    // Write each triangle
    for (const f of faces) {
      const v1 = vertices[f[0]];
      const v2 = vertices[f[1]];
      const v3 = vertices[f[2]];

      const normal = computeNormal(v1, v2, v3);

      // Write normal vector
      for (let i = 0; i < 3; i++) {
        view.setFloat32(offset, normal[i], true);
        offset += 4;
      }

      // Write 3 vertices
      for (const v of [v1, v2, v3]) {
        for (let i = 0; i < 3; i++) {
          view.setFloat32(offset, v[i], true);
          offset += 4;
        }
      }

      // Attribute byte count (unused)
      view.setUint16(offset, 0, true);
      offset += 2;
    }
    return buffer;
  }


  // Download all STLs as a zip
  const downloadAllSTLs = async () => {
    const canvas = canvasRef.current;
    const files = [];
    const zip = new JSZip();

    // Prepare all STL files
    colorBlocks.forEach((color) => {
      const stlContent = generateSTLByColor(color);
      const filename = `rgb_${String(color.r).padStart(3, '0')}${String(color.g).padStart(3, '0')}${String(color.b).padStart(3, '0')}.stl`;
      files.push({ filename, content: [stlContent] });
      zip.file(filename, stlContent);
    });

    // Create ZIP file
    const zipData = await zip.generateAsync({ type: "arraybuffer" });
    const blob = new Blob([zipData], { type: 'application/zip' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'all_color_blocks.zip';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 100);
  };

  // Download CSV with color data
  const downloadCSV = () => {
    let csv = 'Color,R,G,B,Hex,PixelCount\n';
    colorBlocks.forEach((color, index) => {
      const hex = `#${color.r.toString(16).padStart(2, '0')}${color.g.toString(16).padStart(2, '0')}${color.b.toString(16).padStart(2, '0')}`;
      csv += `Color${index + 1},${color.r},${color.g},${color.b},${hex},${color.count}\n`;
    });

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'colors.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 100);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-50 to-blue-50 p-8">
      <div className="max-w-6xl mx-auto">
        <div className="bg-white rounded-2xl shadow-xl p-8">
          <div className="flex items-center justify-between mb-8">
            <h1 className="text-3xl font-bold text-gray-800 flex items-center gap-3">
              <Palette className="w-8 h-8 text-purple-600" />
              Image to STL Color Block Converter
            </h1>
            <button
              onClick={() => setShowSettings(!showSettings)}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <Settings className="w-6 h-6 text-gray-600" />
            </button>
          </div>

          {showSettings && (
            <div className="mb-6 p-4 bg-gray-50 rounded-lg space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Max Colors: {maxColors}
                </label>
                <input
                  type="range"
                  min="2"
                  max="100"
                  value={maxColors}
                  onChange={(e) => setMaxColors(parseInt(e.target.value))}
                  className="w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Color Merge Threshold: {colorThreshold}
                </label>
                <input
                  type="range"
                  min="10"
                  max="100"
                  value={colorThreshold}
                  onChange={(e) => setColorThreshold(parseInt(e.target.value))}
                  className="w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Max Plate Size: {maxCanvasLength} mm
                </label>
                <input
                  type="range"
                  min="100"
                  max="500"
                  value={maxCanvasLength}
                  onChange={(e) => setMaxLength(parseInt(e.target.value))}
                  className="w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Layer Height: {layerHeight} mm
                </label>
                <input
                  type="range"
                  min="0.04"
                  max="0.28"
                  value={layerHeight}
                  onChange={(e) => setLayerDepth(parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Pixel Size: {pixelSize} mm
                </label>
                <input
                  type="range"
                  min="1"
                  max="2"
                  value={pixelSize}
                  onChange={(e) => setPixelSize(parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>
              {image && (
                <button
                  onClick={() => processImage(image)}
                  className="w-full py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
                >
                  Reprocess
                </button>
              )}
            </div>
          )}

          <div className="mb-8">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleImageUpload}
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="w-full py-4 border-2 border-dashed border-gray-300 rounded-xl hover:border-purple-400 hover:bg-purple-50 transition-all flex items-center justify-center gap-3 text-gray-600 hover:text-purple-600"
            >
              <Upload className="w-6 h-6" />
              <span className="font-medium">Click to Upload Image</span>
            </button>
          </div>

          <canvas ref={canvasRef} className="hidden" />
          <canvas ref={previewCanvasRef} className="hidden" />

          {processing && (
            <div className="text-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-4 border-purple-200 border-t-purple-600 mx-auto mb-4"></div>
              <p className="text-gray-600">Processing...</p>
            </div>
          )}

          {!processing && colorBlocks.length > 0 && (
            <div>
              {/* Before/After Preview */}
              <div className="mb-8">
                <h2 className="text-xl font-semibold text-gray-800 mb-4">Before and After Comparison</h2>
                <div className="grid md:grid-cols-2 gap-6">
                  <div>
                    <h3 className="text-sm font-medium text-gray-700 mb-2">Original Image</h3>
                    <div className="border-2 border-gray-200 rounded-lg overflow-hidden">
                      <img
                        src={image.src}
                        alt="Original"
                        className="w-full h-auto"
                      />
                    </div>
                  </div>
                  <div>
                    <h3 className="text-sm font-medium text-gray-700 mb-2">Processed ({colorBlocks.length} colors)</h3>
                    <div className="border-2 border-gray-200 rounded-lg overflow-hidden">
                      {processedImageUrl && (
                        <img
                          src={processedImageUrl}
                          alt="Processed"
                          className="w-full h-auto"
                        />
                      )}
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-semibold text-gray-800">
                  Extracted Colors ({colorBlocks.length})
                </h2>
                <div className="flex gap-3">
                  <button
                    onClick={downloadCSV}
                    className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center gap-2"
                  >
                    <Download className="w-4 h-4" />
                    Download CSV
                  </button>
                  <button
                    onClick={downloadAllSTLs}
                    className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors flex items-center gap-2"
                  >
                    <Download className="w-4 h-4" />
                    Download All STLs (ZIP)
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                {colorBlocks.map((color, index) => (
                  <div
                    key={index}
                    className="border rounded-lg p-3 hover:shadow-lg transition-shadow"
                  >
                    <div
                      className="w-full h-20 rounded-md mb-2"
                      style={{ backgroundColor: `rgb(${color.r},${color.g},${color.b})` }}
                    />
                    <div className="text-xs text-gray-600 mb-1">
                      RGB({color.r},{color.g},{color.b})
                    </div>
                    <div className="text-xs text-gray-500 mb-2">
                      {color.count} pixels
                    </div>
                    <button
                      onClick={() => downloadSTL(color, index)}
                      className="w-full py-1 text-xs bg-purple-100 text-purple-700 rounded hover:bg-purple-200 transition-colors"
                    >
                      Download STL
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {image && colorBlocks.length === 0 && !processing && (
            <div className="mt-8">
              <h3 className="text-lg font-semibold text-gray-800 mb-3">Original Image Preview</h3>
              <img
                src={image.src}
                alt="Preview"
                className="max-w-full rounded-lg shadow-md"
              />
            </div>
          )}
        </div>
      </div >
    </div >
  );
};

export default ImageToSTLConverter;