/**
 * 3D WebGL preview component using three.js
 * Renders color blocks as layered voxels with orbit controls
 */
import React, { useRef, useEffect, useCallback, useState, useMemo } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import type { ColorBlock, ImageDimensions, MappedBlockColor } from '../api/types';
import { Eye, EyeOff, RotateCcw, Maximize2, Layers } from 'lucide-react';

interface ThreeDPreviewProps {
  colorBlocks: ColorBlock[];
  mappedBlockColors: MappedBlockColor[];
  imageDimensions: ImageDimensions;
  layerHeight: number;
  pixelSize: number;
  layerCount: number;
  basePlateThickness: number;
  doubleSided: boolean;
}

interface ColorVisibility {
  hex: string;
  visible: boolean;
  count: number;
}

const BACKGROUND_COLOR = 0xf0f0f0;
const GRID_COLOR = 0xcccccc;
const AMBIENT_LIGHT_INTENSITY = 0.6;
const DIRECTIONAL_LIGHT_INTENSITY = 0.8;

/**
 * Build instanced meshes from color blocks for efficient rendering.
 * Groups all pixels of each color into a single InstancedMesh.
 */
function buildInstancedMeshes(
  colorBlocks: ColorBlock[],
  mappedBlockColors: MappedBlockColor[],
  imageDimensions: ImageDimensions,
  pixelSize: number,
  layerHeight: number,
  layerCount: number,
  basePlateThickness: number,
  doubleSided: boolean,
  visibilityMap: Map<string, boolean>,
  showExploded: boolean,
  materialCacheRef: React.MutableRefObject<Map<string, THREE.MeshPhongMaterial>>,
): THREE.Group {
  const group = new THREE.Group();

  const blockHeight = layerHeight * layerCount;
  // Exploded view: use individual layer height instead of stacked height
  const geometry = new THREE.BoxGeometry(
    pixelSize,
    showExploded ? layerHeight : blockHeight,
    pixelSize
  );
  const baseY = basePlateThickness + blockHeight / 2;

  // Center offset so model is centered at origin
  const offsetX = (imageDimensions.width * pixelSize) / 2;
  const offsetZ = (imageDimensions.height * pixelSize) / 2;

  // Exploded view gap between layers (mm)
  const explodedGap = layerHeight * 0.5;

  const matrix = new THREE.Matrix4();

  for (const [index, block] of colorBlocks.entries()) {
    const mappedColor = mappedBlockColors[index];
    const displayHex = mappedColor?.hex ?? block.hex;
    if (!visibilityMap.get(displayHex)) continue;
    if (block.pixels.length === 0) continue;

    // Get or create cached material for this color
    let material = materialCacheRef.current.get(displayHex);
    if (!material) {
      const color = new THREE.Color(displayHex);
      material = new THREE.MeshPhongMaterial({
        color,
        flatShading: true,
        transparent: true,
        opacity: 0.92,
      });
      materialCacheRef.current.set(displayHex, material);
    }

    // In exploded view, create one instance per layer per pixel
    const instanceCount = showExploded ? block.pixels.length * layerCount : block.pixels.length;
    const mesh = new THREE.InstancedMesh(geometry, material, instanceCount);
    mesh.castShadow = true;
    mesh.receiveShadow = true;

    let instanceIdx = 0;
    for (let i = 0; i < block.pixels.length; i++) {
      const px = block.pixels[i];
      const x = px.x * pixelSize - offsetX + pixelSize / 2;
      const z = px.y * pixelSize - offsetZ + pixelSize / 2;

      if (showExploded) {
        // In exploded view, create separate voxel for each layer
        for (let layer = 0; layer < layerCount; layer++) {
          const layerY = basePlateThickness + (layer + 1) * layerHeight + layer * explodedGap + layerHeight / 2;
          matrix.makeTranslation(x, layerY, z);
          mesh.setMatrixAt(instanceIdx++, matrix);
        }
      } else {
        // Normal stacked view: single tall voxel
        matrix.makeTranslation(x, baseY, z);
        mesh.setMatrixAt(instanceIdx++, matrix);
      }
    }

    mesh.instanceMatrix.needsUpdate = true;
    group.add(mesh);
  }

  // Double-sided: mirror on back
  if (doubleSided) {
    const mirrorBaseY = -(basePlateThickness + blockHeight / 2);
    for (const [index, block] of colorBlocks.entries()) {
      const mappedColor = mappedBlockColors[index];
      const displayHex = mappedColor?.hex ?? block.hex;
      if (!visibilityMap.get(displayHex)) continue;
      if (block.pixels.length === 0) continue;

      const color = new THREE.Color(displayHex);
      const material = new THREE.MeshPhongMaterial({
        color,
        flatShading: true,
        transparent: true,
        opacity: 0.92,
      });

      const instanceCount = showExploded ? block.pixels.length * layerCount : block.pixels.length;
      const mesh = new THREE.InstancedMesh(geometry, material, instanceCount);
      mesh.castShadow = true;
      mesh.receiveShadow = true;

      let instanceIdx = 0;
      for (let i = 0; i < block.pixels.length; i++) {
        const px = block.pixels[i];
        // Mirror X for back side
        const x = -(px.x * pixelSize - offsetX + pixelSize / 2);
        const z = px.y * pixelSize - offsetZ + pixelSize / 2;

        if (showExploded) {
          // In exploded view, mirror each layer separately
          for (let layer = 0; layer < layerCount; layer++) {
            const mirrorLayerY = -(basePlateThickness + (layer + 1) * layerHeight + layer * explodedGap + layerHeight / 2);
            matrix.makeTranslation(x, mirrorLayerY, z);
            mesh.setMatrixAt(instanceIdx++, matrix);
          }
        } else {
          matrix.makeTranslation(x, mirrorBaseY, z);
          mesh.setMatrixAt(instanceIdx++, matrix);
        }
      }

      mesh.instanceMatrix.needsUpdate = true;
      group.add(mesh);
    }
  }

  // Base plate
  if (basePlateThickness > 0) {
    const plateWidth = imageDimensions.width * pixelSize;
    const plateDepth = imageDimensions.height * pixelSize;
    const plateGeo = new THREE.BoxGeometry(plateWidth, basePlateThickness, plateDepth);
    const plateMat = new THREE.MeshPhongMaterial({
      color: 0xeeeeee,
      flatShading: true,
      transparent: true,
      opacity: 0.85,
    });
    const plate = new THREE.Mesh(plateGeo, plateMat);
    plate.position.set(0, basePlateThickness / 2, 0);
    plate.receiveShadow = true;
    group.add(plate);

    if (doubleSided) {
      const backPlate = new THREE.Mesh(plateGeo, plateMat.clone());
      backPlate.position.set(0, -basePlateThickness / 2, 0);
      backPlate.receiveShadow = true;
      group.add(backPlate);
    }
  }

  return group;
}

export const ThreeDPreview: React.FC<ThreeDPreviewProps> = ({
  colorBlocks,
  mappedBlockColors,
  imageDimensions,
  layerHeight,
  pixelSize,
  layerCount,
  basePlateThickness,
  doubleSided,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const modelGroupRef = useRef<THREE.Group | null>(null);
  const animFrameRef = useRef<number>(0);
  const materialCacheRef = useRef<Map<string, THREE.MeshPhongMaterial>>(new Map());

  const [showExploded, setShowExploded] = useState(false);
  const [colorVisibility, setColorVisibility] = useState<ColorVisibility[]>([]);
  const [webglError, setWebglError] = useState(false);

  // Compute visibility map
  const visibilityMap = useMemo(() => {
    const map = new Map<string, boolean>();
    for (const cv of colorVisibility) {
      map.set(cv.hex, cv.visible);
    }
    return map;
  }, [colorVisibility]);

  // Initialize color visibility when colorBlocks change
  useEffect(() => {
    const visibilityByHex = new Map<string, ColorVisibility>();
    colorBlocks.forEach((block, index) => {
      const displayHex = mappedBlockColors[index]?.hex ?? block.hex;
      const existing = visibilityByHex.get(displayHex);
      if (existing) {
        existing.count += block.count;
      } else {
        visibilityByHex.set(displayHex, {
          hex: displayHex,
          visible: true,
          count: block.count,
        });
      }
    });
    setColorVisibility(Array.from(visibilityByHex.values()));
  }, [colorBlocks, mappedBlockColors]);

  const totalPixels = useMemo(
    () => colorBlocks.reduce((sum, b) => sum + b.pixels.length, 0),
    [colorBlocks]
  );

  // Check if we should simplify for performance (>100k pixels)
  const isLargeModel = totalPixels > 100000;

  // Rebuild 3D model
  const rebuildModel = useCallback(() => {
    const scene = sceneRef.current;
    if (!scene || colorBlocks.length === 0) return;

    // Remove previous model
    if (modelGroupRef.current) {
      scene.remove(modelGroupRef.current);
      // Track shared geometries to only dispose once
      const disposedGeometries = new Set<THREE.BufferGeometry>();
      modelGroupRef.current.traverse((obj) => {
        if (obj instanceof THREE.Mesh || obj instanceof THREE.InstancedMesh) {
          // Only dispose geometry if not already disposed (handles shared geometry)
          if (!disposedGeometries.has(obj.geometry)) {
            obj.geometry.dispose();
            disposedGeometries.add(obj.geometry);
          }
          if (Array.isArray(obj.material)) {
            obj.material.forEach(m => m.dispose());
          } else {
            obj.material.dispose();
          }
        }
      });
    }

    const group = buildInstancedMeshes(
      colorBlocks,
      mappedBlockColors,
      imageDimensions,
      pixelSize,
      layerHeight,
      layerCount,
      basePlateThickness,
      doubleSided,
      visibilityMap,
      showExploded,
      materialCacheRef,
    );

    modelGroupRef.current = group;
    scene.add(group);
  }, [colorBlocks, mappedBlockColors, imageDimensions, pixelSize, layerHeight, layerCount, basePlateThickness, doubleSided, visibilityMap, showExploded]);

  // Initialize three.js scene
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const width = container.clientWidth;
    const height = 480;

    // Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(BACKGROUND_COLOR);
    sceneRef.current = scene;

    // Camera
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.01, 1000);
    cameraRef.current = camera;

    // Renderer
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: !isLargeModel });
    } catch {
      setWebglError(true);
      return;
    }
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = !isLargeModel;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Lighting
    const ambient = new THREE.AmbientLight(0xffffff, AMBIENT_LIGHT_INTENSITY);
    scene.add(ambient);

    const dirLight = new THREE.DirectionalLight(0xffffff, DIRECTIONAL_LIGHT_INTENSITY);
    dirLight.position.set(5, 10, 5);
    dirLight.castShadow = !isLargeModel;
    if (dirLight.shadow) {
      dirLight.shadow.mapSize.width = 1024;
      dirLight.shadow.mapSize.height = 1024;
    }
    scene.add(dirLight);

    const fillLight = new THREE.DirectionalLight(0xffffff, 0.3);
    fillLight.position.set(-5, 3, -5);
    scene.add(fillLight);

    // Grid helper
    const modelWidth = imageDimensions.width * pixelSize;
    const modelDepth = imageDimensions.height * pixelSize;
    const gridSize = Math.max(modelWidth, modelDepth) * 1.5;
    const gridDivisions = 10;
    const grid = new THREE.GridHelper(gridSize, gridDivisions, GRID_COLOR, GRID_COLOR);
    grid.material.opacity = 0.3;
    grid.material.transparent = true;
    scene.add(grid);

    // Orbit controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.1;
    controls.minDistance = 0.1;
    controls.maxDistance = 500;
    controlsRef.current = controls;

    // Position camera to see full model
    const maxDim = Math.max(modelWidth, modelDepth);
    const cameraDistance = maxDim * 2;
    camera.position.set(cameraDistance * 0.7, cameraDistance * 0.5, cameraDistance * 0.7);
    camera.lookAt(0, 0, 0);
    controls.target.set(0, 0, 0);

    // Animation loop
    const animate = () => {
      animFrameRef.current = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    // Resize handler
    const handleResize = () => {
      const newWidth = container.clientWidth;
      camera.aspect = newWidth / height;
      camera.updateProjectionMatrix();
      renderer.setSize(newWidth, height);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animFrameRef.current);
      controls.dispose();
      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
      // Dispose cached materials
      materialCacheRef.current.forEach(material => material.dispose());
      materialCacheRef.current.clear();
      sceneRef.current = null;
      cameraRef.current = null;
      rendererRef.current = null;
      controlsRef.current = null;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [imageDimensions.width, imageDimensions.height, pixelSize]);
  // Note: isLargeModel intentionally excluded from deps to prevent scene teardown flash when crossing 100k threshold

  // Rebuild model whenever parameters change
  useEffect(() => {
    rebuildModel();
  }, [rebuildModel]);

  const handleResetView = useCallback(() => {
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (!camera || !controls) return;

    const modelWidth = imageDimensions.width * pixelSize;
    const modelDepth = imageDimensions.height * pixelSize;
    const maxDim = Math.max(modelWidth, modelDepth);
    const cameraDistance = maxDim * 2;

    camera.position.set(cameraDistance * 0.7, cameraDistance * 0.5, cameraDistance * 0.7);
    controls.target.set(0, 0, 0);
    controls.update();
  }, [imageDimensions, pixelSize]);

  const handleFitView = useCallback(() => {
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (!camera || !controls) return;

    // Top-down view
    const modelWidth = imageDimensions.width * pixelSize;
    const modelDepth = imageDimensions.height * pixelSize;
    const maxDim = Math.max(modelWidth, modelDepth);

    camera.position.set(0, maxDim * 1.5, 0);
    controls.target.set(0, 0, 0);
    controls.update();
  }, [imageDimensions, pixelSize]);

  const toggleColorVisibility = useCallback((hex: string) => {
    setColorVisibility(prev =>
      prev.map(cv => cv.hex === hex ? { ...cv, visible: !cv.visible } : cv)
    );
  }, []);

  const toggleAllVisibility = useCallback(() => {
    const allVisible = colorVisibility.every(cv => cv.visible);
    setColorVisibility(prev =>
      prev.map(cv => ({ ...cv, visible: !allVisible }))
    );
  }, [colorVisibility]);

  const physicalWidth = (imageDimensions.width * pixelSize).toFixed(1);
  const physicalHeight = (imageDimensions.height * pixelSize).toFixed(1);
  const totalHeight = (layerHeight * layerCount + basePlateThickness).toFixed(2);

  if (webglError) {
    return (
      <div className="mt-6 p-4 bg-gray-50 rounded-lg text-center text-gray-500 text-sm">
        <Layers className="w-5 h-5 mx-auto mb-2 text-gray-400" />
        3D Preview unavailable (WebGL not supported)
      </div>
    );
  }

  return (
    <div className="mt-6 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
          <Layers className="w-5 h-5 text-purple-600" />
          3D Preview
        </h3>
        <div className="flex gap-2">
          <button
            onClick={handleResetView}
            className="px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors flex items-center gap-1"
            title="Reset camera"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Reset
          </button>
          <button
            onClick={handleFitView}
            className="px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors flex items-center gap-1"
            title="Top-down view"
          >
            <Maximize2 className="w-3.5 h-3.5" />
            Top
          </button>
          <button
            onClick={() => setShowExploded(!showExploded)}
            className={`px-3 py-1.5 text-sm rounded-lg transition-colors flex items-center gap-1 ${
              showExploded ? 'bg-purple-100 text-purple-700' : 'bg-gray-100 hover:bg-gray-200'
            }`}
            title="Toggle exploded view"
          >
            <Layers className="w-3.5 h-3.5" />
            Exploded
          </button>
        </div>
      </div>

      {/* Size info */}
      <div className="text-xs text-gray-500 flex gap-4">
        <span>{physicalWidth} x {physicalHeight} mm</span>
        <span>Height: {totalHeight} mm</span>
        <span>{totalPixels.toLocaleString()} voxels</span>
        {isLargeModel && <span className="text-amber-600">Large model - simplified rendering</span>}
      </div>

      {/* WebGL canvas */}
      <div
        ref={containerRef}
        className="w-full rounded-lg border-2 border-gray-200 shadow-inner overflow-hidden"
        style={{ height: 480 }}
      />

      {/* Color visibility toggles */}
      <div className="flex flex-wrap gap-2 items-center">
        <button
          onClick={toggleAllVisibility}
          className="px-2 py-1 text-xs bg-gray-100 hover:bg-gray-200 rounded transition-colors"
        >
          {colorVisibility.every(cv => cv.visible) ? 'Hide All' : 'Show All'}
        </button>
        {colorVisibility.map(cv => (
          <button
            key={cv.hex}
            onClick={() => toggleColorVisibility(cv.hex)}
            className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs transition-colors ${
              cv.visible ? 'bg-gray-100 hover:bg-gray-200' : 'bg-gray-50 text-gray-400'
            }`}
            title={`${cv.visible ? 'Hide' : 'Show'} ${cv.hex} (${cv.count} pixels)`}
          >
            <span
              className="w-3 h-3 rounded-sm border border-gray-300"
              style={{ backgroundColor: cv.hex, opacity: cv.visible ? 1 : 0.3 }}
            />
            {cv.visible ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
            <span>{cv.count}</span>
          </button>
        ))}
      </div>

      <p className="text-xs text-gray-400">
        Drag to rotate, scroll to zoom, right-click to pan
      </p>
    </div>
  );
};
