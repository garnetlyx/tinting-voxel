/**
 * 3D WebGL preview component using three.js
 * Renders color blocks as layered voxels with orbit controls
 */
import React, { useRef, useEffect, useCallback, useState, useMemo } from 'react';
import * as THREE from 'three';
import { BUG_REPORT_CAPTURE_EVENT } from '../utils/bugReport';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import type { ColorBlock, ImageDimensions, MappedBlockColor, PrintStackInfo } from '../api/types';
import { Eye, EyeOff, RotateCcw, Maximize2, Layers } from 'lucide-react';
import { buildInstancedMeshes, disposePreviewModel, updatePreviewCameraClipping } from './threeDPreviewScene';

interface ThreeDPreviewProps {
  colorBlocks: ColorBlock[];
  mappedBlockColors: MappedBlockColor[];
  imageDimensions: ImageDimensions;
  layerHeight: number;
  pixelSize: number;
  layerCount: number;
  whiteBackingLayers: number;
  basePlateThickness: number;
  doubleSided: boolean;
  printStack: PrintStackInfo;
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

export const ThreeDPreview: React.FC<ThreeDPreviewProps> = ({
  colorBlocks,
  mappedBlockColors,
  imageDimensions,
  layerHeight,
  pixelSize,
  layerCount,
  whiteBackingLayers,
  basePlateThickness,
  doubleSided,
  printStack,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const modelGroupRef = useRef<THREE.Group | null>(null);
  const animFrameRef = useRef<number>(0);
  const boundsRef = useRef(new THREE.Sphere(new THREE.Vector3(), 1));
  const gridRef = useRef<THREE.GridHelper | null>(null);

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

  // Flag models with a high voxel count.
  const isLargeModel = totalPixels > 100000;

  // Rebuild 3D model
  const rebuildModel = useCallback(() => {
    const scene = sceneRef.current;
    if (!scene || colorBlocks.length === 0) return;

    // Remove previous model
    if (modelGroupRef.current) {
      scene.remove(modelGroupRef.current);
      disposePreviewModel(modelGroupRef.current);
    }

    const group = buildInstancedMeshes(
      colorBlocks,
      mappedBlockColors,
      imageDimensions,
      pixelSize,
      layerHeight,
      layerCount,
      whiteBackingLayers,
      basePlateThickness,
      doubleSided,
      visibilityMap,
      showExploded,
    );

    modelGroupRef.current = group;
    scene.add(group);

    const modelWidth = imageDimensions.width * pixelSize;
    const modelDepth = imageDimensions.height * pixelSize;
    const gap = showExploded ? Math.max(layerHeight * 0.5, Math.max(modelWidth, modelDepth) * 0.02) : 0;
    const bottom = doubleSided ? -layerCount * (layerHeight + gap) : 0;
    const top = basePlateThickness + (whiteBackingLayers + layerCount) * layerHeight
      + Math.max(0, whiteBackingLayers + layerCount - 1) * gap;
    new THREE.Box3(
      new THREE.Vector3(-modelWidth / 2, bottom, -modelDepth / 2),
      new THREE.Vector3(modelWidth / 2, top, modelDepth / 2),
    ).getBoundingSphere(boundsRef.current);
    if (gridRef.current) {
      gridRef.current.position.y = bottom - Math.max(layerHeight, Math.max(modelWidth, modelDepth) * 0.005);
    }
    if (cameraRef.current) updatePreviewCameraClipping(cameraRef.current, boundsRef.current);
  }, [colorBlocks, mappedBlockColors, imageDimensions, pixelSize, layerHeight, layerCount, whiteBackingLayers, basePlateThickness, doubleSided, visibilityMap, showExploded]);

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
      renderer = new THREE.WebGLRenderer({
        antialias: true,
        // Thin print layers must remain distinct even at close zoom levels.
        logarithmicDepthBuffer: true,
      });
    } catch {
      setWebglError(true);
      return;
    }
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Lighting
    const ambient = new THREE.AmbientLight(0xffffff, AMBIENT_LIGHT_INTENSITY);
    scene.add(ambient);

    const dirLight = new THREE.DirectionalLight(0xffffff, DIRECTIONAL_LIGHT_INTENSITY);
    dirLight.position.set(5, 10, 5);
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
    gridRef.current = grid;

    // Orbit controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.1;
    controls.minDistance = Math.max(modelWidth, modelDepth) * 0.01;
    controls.maxDistance = Math.max(modelWidth, modelDepth) * 10;
    controlsRef.current = controls;

    // Position camera to see full model
    const maxDim = Math.max(modelWidth, modelDepth);
    const cameraDistance = maxDim * 2;
    camera.position.set(cameraDistance * 0.7, cameraDistance * 0.5, cameraDistance * 0.7);
    camera.lookAt(0, 0, 0);
    controls.target.set(0, 0, 0);
    const updateClipping = () => {
      updatePreviewCameraClipping(camera, boundsRef.current);
      // Keep the ground grid out of the way when viewing the back face.
      grid.visible = camera.position.y > grid.position.y;
    };
    controls.addEventListener('change', updateClipping);

    const captureFrame = () => renderer.render(scene, camera);
    document.addEventListener(BUG_REPORT_CAPTURE_EVENT, captureFrame);

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
      document.removeEventListener(BUG_REPORT_CAPTURE_EVENT, captureFrame);
      cancelAnimationFrame(animFrameRef.current);
      controls.removeEventListener('change', updateClipping);
      controls.dispose();
      if (modelGroupRef.current) {
        disposePreviewModel(modelGroupRef.current);
        modelGroupRef.current = null;
      }
      grid.geometry.dispose();
      grid.material.dispose();
      gridRef.current = null;
      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
      sceneRef.current = null;
      cameraRef.current = null;
      rendererRef.current = null;
      controlsRef.current = null;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [imageDimensions.width, imageDimensions.height, pixelSize]);

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
  const totalHeight = printStack.totalHeightMm.toFixed(2);

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
        <span>Layers: {printStack.opticalLayerCount} + {printStack.whiteBackingLayers}</span>
        <span>{totalPixels.toLocaleString()} voxels</span>
        {isLargeModel && <span className="text-amber-600">Large model</span>}
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
