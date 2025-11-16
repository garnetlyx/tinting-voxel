import React, { useState, useRef } from 'react';
import { Upload, Download, Settings, Palette } from 'lucide-react';

const ImageToSTLConverter = () => {
  const [image, setImage] = useState(null);
  const [originalImage, setOriginalImage] = useState(null);
  const [processing, setProcessing] = useState(false);
  const [colorBlocks, setColorBlocks] = useState([]);
  const [processedImageUrl, setProcessedImageUrl] = useState(null);
  const [maxColors, setMaxColors] = useState(50);
  const [colorThreshold, setColorThreshold] = useState(30);
  const [showSettings, setShowSettings] = useState(false);
  const canvasRef = useRef(null);
  const previewCanvasRef = useRef(null);
  const fileInputRef = useRef(null);

  // Handle image upload
  const handleImageUpload = (e) => {
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
  const colorDistance = (c1, c2) => {
    return Math.sqrt(
      Math.pow(c1.r - c2.r, 2) +
      Math.pow(c1.g - c2.g, 2) +
      Math.pow(c1.b - c2.b, 2)
    );
  };

  // Merge similar colors BUT preserve dark/black colors as outlines
  const mergeSimilarColors = (colors, threshold) => {
    const merged = [];
    const used = new Set();

    colors.forEach((color, idx) => {
      if (used.has(idx)) return;

      // Check if this is a dark/black color (outline)
      const isDark = (color.r + color.g + color.b) < 100;

      const cluster = [color];
      used.add(idx);

      for (let i = idx + 1; i < colors.length; i++) {
        if (used.has(i)) continue;

        const otherColor = colors[i];
        const otherIsDark = (otherColor.r + otherColor.g + otherColor.b) < 100;

        // Never merge dark colors with light colors
        if (isDark !== otherIsDark) continue;

        // Use stricter threshold for dark colors to preserve outlines
        const effectiveThreshold = isDark ? threshold * 0.5 : threshold;

        if (colorDistance(color, otherColor) < effectiveThreshold) {
          cluster.push(otherColor);
          used.add(i);
        }
      }

      // Calculate average color
      const avg = {
        r: Math.round(cluster.reduce((sum, c) => sum + c.r, 0) / cluster.length),
        g: Math.round(cluster.reduce((sum, c) => sum + c.g, 0) / cluster.length),
        b: Math.round(cluster.reduce((sum, c) => sum + c.b, 0) / cluster.length),
        count: cluster.reduce((sum, c) => sum + c.count, 0),
        pixels: cluster.flatMap(c => c.pixels)
      };
      merged.push(avg);
    });

    return merged;
  };

  // Merge only dark colors (all RGB < 100)
  const mergeDarkColors = (colors, threshold) => {
    const merged = [];
    const used = new Set();

    colors.forEach((color, idx) => {
      if (used.has(idx)) return;

      const isDark = color.r < 100 && color.g < 100 && color.b < 100;

      if (!isDark) {
        // Keep non-dark colors as-is
        merged.push(color);
        return;
      }

      const cluster = [color];
      used.add(idx);

      for (let i = idx + 1; i < colors.length; i++) {
        if (used.has(i)) continue;

        const otherColor = colors[i];
        const otherIsDark = otherColor.r < 100 && otherColor.g < 100 && otherColor.b < 100;

        // Only merge if both are dark
        if (!otherIsDark) continue;

        if (colorDistance(color, otherColor) < threshold) {
          cluster.push(otherColor);
          used.add(i);
        }
      }

      // Calculate average color
      const avg = {
        r: Math.round(cluster.reduce((sum, c) => sum + c.r, 0) / cluster.length),
        g: Math.round(cluster.reduce((sum, c) => sum + c.g, 0) / cluster.length),
        b: Math.round(cluster.reduce((sum, c) => sum + c.b, 0) / cluster.length),
        count: cluster.reduce((sum, c) => sum + c.count, 0),
        pixels: cluster.flatMap(c => c.pixels)
      };
      merged.push(avg);
    });

    return merged;
  };

  // Reassign noise colors to nearest major color
  const reassignNoiseColors = (colors, mainColors) => {
    // Identify noise colors (small pixel count)
    const noiseThreshold = 10;
    const noiseColors = [];
    const keepColors = [];

    colors.forEach(color => {
      if (color.count < noiseThreshold) {
        noiseColors.push(color);
      } else {
        keepColors.push(color);
      }
    });

    // If all colors would be removed, keep them
    if (keepColors.length === 0) {
      return colors;
    }

    // Reassign noise pixels to nearest main color
    noiseColors.forEach(noiseColor => {
      noiseColor.pixels.forEach(pixel => {
        // Find nearest main color
        let minDist = Infinity;
        let nearestColorIdx = 0;

        keepColors.forEach((mainColor, idx) => {
          const dist = colorDistance(noiseColor, mainColor);
          if (dist < minDist) {
            minDist = dist;
            nearestColorIdx = idx;
          }
        });

        // Add pixel to nearest color
        keepColors[nearestColorIdx].pixels.push(pixel);
        keepColors[nearestColorIdx].count++;
      });
    });

    return keepColors;
  };

  // Process image to extract color blocks
  const processImage = async (img) => {
    setProcessing(true);

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');

    // Resize for processing
    const maxDim = 400;
    const scale = Math.min(maxDim / img.width, maxDim / img.height);
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

      // Skip transparent pixels
      if (a < 128) continue;

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

    // Step 1: Merge dark colors (all RGB < 100)
    colors = mergeDarkColors(colors, colorThreshold);

    // Step 2: Sort by frequency
    colors.sort((a, b) => b.count - a.count);

    // Step 3: Limit to max colors
    const mainColors = colors.slice(0, maxColors);

    // Step 4: Reassign remaining colors (noise) to nearest main color
    colors = reassignNoiseColors(colors, mainColors);

    setColorBlocks(colors);

    // Generate processed image preview
    generateProcessedPreview(colors, canvas.width, canvas.height);

    setProcessing(false);
  };

  // Generate processed image preview
  const generateProcessedPreview = (colors, width, height) => {
    const previewCanvas = previewCanvasRef.current;
    const ctx = previewCanvas.getContext('2d');
    previewCanvas.width = width;
    previewCanvas.height = height;

    // Create color mapping for each pixel
    const imageData = ctx.createImageData(width, height);
    const pixelColorMap = new Map();

    // Map each pixel to its color
    colors.forEach(color => {
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

  // Fill all empty pixels with nearest color, preserve original edges
  const fillIsolatedPixels = (colors, width, height) => {
    // Create a pixel map for quick lookup
    const pixelMap = new Map();
    const colorPixelSets = colors.map(() => new Set());

    // Identify dark colors (outlines)
    const isDarkColor = colors.map(color =>
      (color.r + color.g + color.b) < 100
    );

    colors.forEach((color, colorIdx) => {
      color.pixels.forEach(({ x, y }) => {
        const key = `${x},${y}`;
        pixelMap.set(key, colorIdx);
        colorPixelSets[colorIdx].add(key);
      });
    });

    // Find all empty pixels
    const emptyPixels = [];
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const key = `${x},${y}`;
        if (!pixelMap.has(key)) {
          emptyPixels.push({ x, y, key });
        }
      }
    }

    // Fill each empty pixel with nearest color using direct distance
    emptyPixels.forEach(({ x, y, key }) => {
      let minDist = Infinity;
      let nearestColorIdx = null;
      let minDarkDist = Infinity;
      let nearestDarkIdx = null;

      // Check distance to each color's pixels
      colors.forEach((color, colorIdx) => {
        // Sample a subset of pixels for performance (every Nth pixel)
        const sampleRate = Math.max(1, Math.floor(color.pixels.length / 100));

        for (let i = 0; i < color.pixels.length; i += sampleRate) {
          const pixel = color.pixels[i];
          const dx = pixel.x - x;
          const dy = pixel.y - y;
          const dist = dx * dx + dy * dy; // Squared distance (faster)

          // Track nearest dark color separately
          if (isDarkColor[colorIdx]) {
            if (dist < minDarkDist) {
              minDarkDist = dist;
              nearestDarkIdx = colorIdx;
            }
          }

          if (dist < minDist) {
            minDist = dist;
            nearestColorIdx = colorIdx;
          }

          // Early exit if very close
          if (dist <= 1) break;
        }
      });

      // Prefer dark color if it's reasonably close (within 2x distance)
      // This preserves black outlines
      if (nearestDarkIdx !== null && minDarkDist < minDist * 4) {
        nearestColorIdx = nearestDarkIdx;
      }

      // Assign to nearest color
      if (nearestColorIdx !== null) {
        pixelMap.set(key, nearestColorIdx);
        colors[nearestColorIdx].pixels.push({ x, y });
        colors[nearestColorIdx].count++;
      }
    });

    return colors;
  };
  const generateSVGPath = (pixels, width, height) => {
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

  // Generate STL file content
  const generateSTL = (color, width, height) => {
    const path = generateSVGPath(color.pixels, width, height);
    const depth = 2; // STL depth in mm

    let stl = 'solid colorblock\n';

    // Simplified STL generation - each pixel becomes a rectangular prism
    color.pixels.forEach(({ x, y }) => {
      const x1 = x, x2 = x + 1;
      const y1 = y, y2 = y + 1;
      const z1 = 0, z2 = depth;

      // Top face
      stl += `facet normal 0 0 1\n  outer loop\n`;
      stl += `    vertex ${x1} ${y1} ${z2}\n    vertex ${x2} ${y1} ${z2}\n    vertex ${x2} ${y2} ${z2}\n  endloop\nendfacet\n`;
      stl += `facet normal 0 0 1\n  outer loop\n`;
      stl += `    vertex ${x1} ${y1} ${z2}\n    vertex ${x2} ${y2} ${z2}\n    vertex ${x1} ${y2} ${z2}\n  endloop\nendfacet\n`;

      // Bottom face
      stl += `facet normal 0 0 -1\n  outer loop\n`;
      stl += `    vertex ${x1} ${y1} ${z1}\n    vertex ${x2} ${y2} ${z1}\n    vertex ${x2} ${y1} ${z1}\n  endloop\nendfacet\n`;
      stl += `facet normal 0 0 -1\n  outer loop\n`;
      stl += `    vertex ${x1} ${y1} ${z1}\n    vertex ${x1} ${y2} ${z1}\n    vertex ${x2} ${y2} ${z1}\n  endloop\nendfacet\n`;
    });

    stl += 'endsolid colorblock\n';
    return stl;
  };

  // Download STL for a specific color
  const downloadSTL = (color, index) => {
    const canvas = canvasRef.current;
    const stlContent = generateSTL(color, canvas.width, canvas.height);
    const blob = new Blob([stlContent], { type: 'application/octet-stream' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `rgb_${String(color.r).padStart(3, '0')}${String(color.g).padStart(3, '0')}${String(color.b).padStart(3, '0')}.stl`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 100);
  };

  // Create a simple ZIP file manually
  const createZipFile = (files) => {
    // Simple ZIP file structure (ZIP64 format)
    const encoder = new TextEncoder();
    let offset = 0;
    const fileRecords = [];
    const chunks = [];

    files.forEach(({ filename, content }) => {
      const filenameBytes = encoder.encode(filename);
      const contentBytes = encoder.encode(content);

      // Local file header
      const localHeader = new Uint8Array(30 + filenameBytes.length);
      const view = new DataView(localHeader.buffer);

      // Local file header signature
      view.setUint32(0, 0x04034b50, true);
      // Version needed to extract
      view.setUint16(4, 20, true);
      // General purpose bit flag
      view.setUint16(6, 0, true);
      // Compression method (0 = no compression)
      view.setUint16(8, 0, true);
      // File modification time
      view.setUint16(10, 0, true);
      // File modification date
      view.setUint16(12, 0, true);
      // CRC-32
      view.setUint32(14, 0, true);
      // Compressed size
      view.setUint32(18, contentBytes.length, true);
      // Uncompressed size
      view.setUint32(22, contentBytes.length, true);
      // Filename length
      view.setUint16(26, filenameBytes.length, true);
      // Extra field length
      view.setUint16(28, 0, true);
      // Filename
      localHeader.set(filenameBytes, 30);

      chunks.push(localHeader);
      chunks.push(contentBytes);

      fileRecords.push({
        filename: filenameBytes,
        offset,
        compressedSize: contentBytes.length,
        uncompressedSize: contentBytes.length
      });

      offset += localHeader.length + contentBytes.length;
    });

    // Central directory
    const centralDirStart = offset;
    fileRecords.forEach(record => {
      const centralHeader = new Uint8Array(46 + record.filename.length);
      const view = new DataView(centralHeader.buffer);

      // Central directory file header signature
      view.setUint32(0, 0x02014b50, true);
      // Version made by
      view.setUint16(4, 20, true);
      // Version needed to extract
      view.setUint16(6, 20, true);
      // General purpose bit flag
      view.setUint16(8, 0, true);
      // Compression method
      view.setUint16(10, 0, true);
      // File modification time
      view.setUint16(12, 0, true);
      // File modification date
      view.setUint16(14, 0, true);
      // CRC-32
      view.setUint32(16, 0, true);
      // Compressed size
      view.setUint32(20, record.compressedSize, true);
      // Uncompressed size
      view.setUint32(24, record.uncompressedSize, true);
      // Filename length
      view.setUint16(28, record.filename.length, true);
      // Extra field length
      view.setUint16(30, 0, true);
      // File comment length
      view.setUint16(32, 0, true);
      // Disk number start
      view.setUint16(34, 0, true);
      // Internal file attributes
      view.setUint16(36, 0, true);
      // External file attributes
      view.setUint32(38, 0, true);
      // Relative offset of local header
      view.setUint32(42, record.offset, true);
      // Filename
      centralHeader.set(record.filename, 46);

      chunks.push(centralHeader);
      offset += centralHeader.length;
    });

    const centralDirSize = offset - centralDirStart;

    // End of central directory record
    const endRecord = new Uint8Array(22);
    const endView = new DataView(endRecord.buffer);

    // End of central directory signature
    endView.setUint32(0, 0x06054b50, true);
    // Number of this disk
    endView.setUint16(4, 0, true);
    // Disk where central directory starts
    endView.setUint16(6, 0, true);
    // Number of central directory records on this disk
    endView.setUint16(8, fileRecords.length, true);
    // Total number of central directory records
    endView.setUint16(10, fileRecords.length, true);
    // Size of central directory
    endView.setUint32(12, centralDirSize, true);
    // Offset of start of central directory
    endView.setUint32(16, centralDirStart, true);
    // Comment length
    endView.setUint16(20, 0, true);

    chunks.push(endRecord);

    // Combine all chunks
    const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
    const zipData = new Uint8Array(totalLength);
    let position = 0;
    chunks.forEach(chunk => {
      zipData.set(chunk, position);
      position += chunk.length;
    });

    return zipData;
  };

  // Download all STLs as a zip
  const downloadAllSTLs = async () => {
    const canvas = canvasRef.current;
    const files = [];

    // Prepare all STL files
    colorBlocks.forEach((color) => {
      const stlContent = generateSTL(color, canvas.width, canvas.height);
      const filename = `rgb_${String(color.r).padStart(3, '0')}${String(color.g).padStart(3, '0')}${String(color.b).padStart(3, '0')}.stl`;
      files.push({ filename, content: stlContent });
    });

    // Create ZIP file
    const zipData = createZipFile(files);
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
              图片转STL色块转换器
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
                  最大颜色数量: {maxColors}
                </label>
                <input
                  type="range"
                  min="10"
                  max="100"
                  value={maxColors}
                  onChange={(e) => setMaxColors(parseInt(e.target.value))}
                  className="w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  颜色合并阈值: {colorThreshold}
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
              {image && (
                <button
                  onClick={() => processImage(image)}
                  className="w-full py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
                >
                  重新处理
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
              <span className="font-medium">点击上传图片</span>
            </button>
          </div>

          <canvas ref={canvasRef} className="hidden" />
          <canvas ref={previewCanvasRef} className="hidden" />

          {processing && (
            <div className="text-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-4 border-purple-200 border-t-purple-600 mx-auto mb-4"></div>
              <p className="text-gray-600">处理中...</p>
            </div>
          )}

          {!processing && colorBlocks.length > 0 && (
            <div>
              {/* Before/After Preview */}
              <div className="mb-8">
                <h2 className="text-xl font-semibold text-gray-800 mb-4">处理前后对比</h2>
                <div className="grid md:grid-cols-2 gap-6">
                  <div>
                    <h3 className="text-sm font-medium text-gray-700 mb-2">原始图片</h3>
                    <div className="border-2 border-gray-200 rounded-lg overflow-hidden">
                      <img
                        src={image.src}
                        alt="Original"
                        className="w-full h-auto"
                      />
                    </div>
                  </div>
                  <div>
                    <h3 className="text-sm font-medium text-gray-700 mb-2">处理后 ({colorBlocks.length}色)</h3>
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
                  提取的颜色 ({colorBlocks.length})
                </h2>
                <div className="flex gap-3">
                  <button
                    onClick={downloadCSV}
                    className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors flex items-center gap-2"
                  >
                    <Download className="w-4 h-4" />
                    下载CSV
                  </button>
                  <button
                    onClick={downloadAllSTLs}
                    className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors flex items-center gap-2"
                  >
                    <Download className="w-4 h-4" />
                    下载所有STL (ZIP)
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
                      {color.count} 像素
                    </div>
                    <button
                      onClick={() => downloadSTL(color, index)}
                      className="w-full py-1 text-xs bg-purple-100 text-purple-700 rounded hover:bg-purple-200 transition-colors"
                    >
                      下载STL
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {image && colorBlocks.length === 0 && !processing && (
            <div className="mt-8">
              <h3 className="text-lg font-semibold text-gray-800 mb-3">原始图片预览</h3>
              <img
                src={image.src}
                alt="Preview"
                className="max-w-full rounded-lg shadow-md"
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ImageToSTLConverter;