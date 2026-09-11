import * as THREE from 'three';
import type { ColorBlock, ImageDimensions, MappedBlockColor } from '../api/types';

interface PreviewRectangle {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** Merge adjacent equal colors without changing the occupied pixels. */
export function mergePreviewPixels(
  colorBlocks: ColorBlock[],
  mappedBlockColors: MappedBlockColor[],
  imageDimensions: ImageDimensions,
  visibilityMap: Map<string, boolean>,
): Map<string, PreviewRectangle[]> {
  const { width, height } = imageDimensions;
  const grid = new Int32Array(width * height).fill(-1);
  const colors = new Map<string, number>();
  const regions = new Map<string, PreviewRectangle[]>();
  colorBlocks.forEach((block, index) => {
    const hex = mappedBlockColors[index]?.hex ?? block.hex;
    if (!visibilityMap.get(hex) || block.pixels.length === 0) return;
    let colorIndex = colors.get(hex);
    if (colorIndex === undefined) {
      colorIndex = colors.size;
      colors.set(hex, colorIndex);
      regions.set(hex, []);
    }
    for (const pixel of block.pixels) grid[pixel.y * width + pixel.x] = colorIndex;
  });
  const rectangles = Array.from(regions.values());
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width;) {
      const color = grid[y * width + x];
      if (color < 0) { x++; continue; }
      let runWidth = 1;
      while (x + runWidth < width && grid[y * width + x + runWidth] === color) runWidth++;
      let runHeight = 1;
      rows: while (y + runHeight < height) {
        for (let dx = 0; dx < runWidth; dx++) {
          if (grid[(y + runHeight) * width + x + dx] !== color) break rows;
        }
        runHeight++;
      }
      rectangles[color].push({ x, y, width: runWidth, height: runHeight });
      for (let dy = 0; dy < runHeight; dy++) {
        grid.fill(-1, (y + dy) * width + x, (y + dy) * width + x + runWidth);
      }
      x += runWidth;
    }
  }
  return regions;
}

/**
 * Build instanced meshes from color blocks for efficient rendering.
 * Groups merged rectangles of each color into a single InstancedMesh.
 */
export function buildInstancedMeshes(
  colorBlocks: ColorBlock[],
  mappedBlockColors: MappedBlockColor[],
  imageDimensions: ImageDimensions,
  pixelSize: number,
  layerHeight: number,
  layerCount: number,
  whiteBackingLayers: number,
  visibilityMap: Map<string, boolean>,
  showExploded: boolean,
): THREE.Group {
  const group = new THREE.Group();

  const blockHeight = layerHeight * layerCount;
  // Exploded view: use individual layer height instead of stacked height
  const geometry = new THREE.BoxGeometry(
    pixelSize,
    showExploded ? layerHeight : blockHeight,
    pixelSize
  );
  // Preview coordinates put the colored face above its white backing.
  const backingThickness = whiteBackingLayers * layerHeight;
  const baseY = backingThickness + blockHeight / 2;
  const materials = new Map<string, THREE.MeshPhongMaterial>();

  // Center offset so model is centered at origin
  const offsetX = (imageDimensions.width * pixelSize) / 2;
  const offsetZ = (imageDimensions.height * pixelSize) / 2;

  // Exploded view gap between layers (mm)
  const explodedGap = showExploded
    ? Math.max(layerHeight * 0.5, Math.max(offsetX, offsetZ) * 0.04)
    : 0;

  const matrix = new THREE.Matrix4();
  const regions = mergePreviewPixels(colorBlocks, mappedBlockColors, imageDimensions, visibilityMap);

  for (const [displayHex, rectangles] of regions) {
    // Share one opaque material between the front and back of each color.
    let material = materials.get(displayHex);
    if (!material) {
      const color = new THREE.Color(displayHex);
      material = new THREE.MeshPhongMaterial({
        color,
        flatShading: true,
      });
      materials.set(displayHex, material);
    }

    // In exploded view, create one instance per layer per rectangle.
    const instanceCount = showExploded ? rectangles.length * layerCount : rectangles.length;
    const mesh = new THREE.InstancedMesh(geometry, material, instanceCount);

    let instanceIdx = 0;
    for (const rectangle of rectangles) {
      const x = (rectangle.x + rectangle.width / 2) * pixelSize - offsetX;
      const z = (rectangle.y + rectangle.height / 2) * pixelSize - offsetZ;
      matrix.makeScale(rectangle.width, 1, rectangle.height);

      if (showExploded) {
        // Keep the individual layers separate in exploded view.
        for (let layer = 0; layer < layerCount; layer++) {
          const layerY = backingThickness
            + whiteBackingLayers * explodedGap
            + layer * (layerHeight + explodedGap) + layerHeight / 2;
          matrix.setPosition(x, layerY, z);
          mesh.setMatrixAt(instanceIdx++, matrix);
        }
      } else {
        // Normal view: merge the stacked layers into one block.
        matrix.setPosition(x, baseY, z);
        mesh.setMatrixAt(instanceIdx++, matrix);
      }
    }

    mesh.instanceMatrix.needsUpdate = true;
    group.add(mesh);
  }

  if (whiteBackingLayers > 0) {
    const plateWidth = imageDimensions.width * pixelSize;
    const plateDepth = imageDimensions.height * pixelSize;
    const whiteMaterial = new THREE.MeshPhongMaterial({
      color: 0xf8f8f8,
      flatShading: true,
    });

    if (showExploded) {
      const backingGeo = new THREE.BoxGeometry(plateWidth, layerHeight, plateDepth);
      for (let layer = 0; layer < whiteBackingLayers; layer++) {
        const backing = new THREE.Mesh(backingGeo, whiteMaterial);
        const y = layer * (layerHeight + explodedGap) + layerHeight / 2;
        backing.position.set(0, y, 0);
        group.add(backing);
      }
    } else {
      const backingThickness = whiteBackingLayers * layerHeight;
      const backingGeo = new THREE.BoxGeometry(plateWidth, backingThickness, plateDepth);
      const backing = new THREE.Mesh(backingGeo, whiteMaterial);
      backing.position.set(0, backingThickness / 2, 0);
      group.add(backing);
    }
  }

  return group;
}

/** Keep depth precision focused on the model as the camera orbits and zooms. */
export function updatePreviewCameraClipping(
  camera: THREE.PerspectiveCamera,
  bounds: THREE.Sphere,
): void {
  const distance = camera.position.distanceTo(bounds.center);
  const radius = Math.max(bounds.radius, 0.01);
  camera.near = Math.max(radius / 1000, distance - radius * 1.1);
  // Include the surrounding grid as well as the model.
  camera.far = Math.max(camera.near * 2, distance + radius * 3);
  camera.updateProjectionMatrix();
}

export function disposePreviewModel(group: THREE.Group): void {
  const geometries = new Set<THREE.BufferGeometry>();
  const materials = new Set<THREE.Material>();
  group.traverse((object) => {
    if (!(object instanceof THREE.Mesh)) return;
    if (object instanceof THREE.InstancedMesh) object.dispose();
    geometries.add(object.geometry);
    for (const material of Array.isArray(object.material) ? object.material : [object.material]) {
      materials.add(material);
    }
  });
  geometries.forEach(geometry => geometry.dispose());
  materials.forEach(material => material.dispose());
}
