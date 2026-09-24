import { useTranslation } from '../i18n';
/**
 * 3D WebGL preview component using three.js
 * Renders color blocks as layered voxels with orbit controls
 */
import React, { useRef, useEffect, useCallback, useState, useMemo } from 'react';
import * as THREE from 'three';
import { BUG_REPORT_CAPTURE_EVENT } from '../utils/bugReport';
import { track } from '../utils/telemetry';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import type { ColorBlock, FilamentColorConfig, ImageDimensions, MappedBlockColor, PrintStackInfo } from '../api/types';
import { Eye, EyeOff, RotateCcw, Maximize2, Layers } from 'lucide-react';
import { buildInstancedMeshes, disposePreviewModel, resolvePreviewBackingHex, updatePreviewCameraClipping } from './threeDPreviewScene';

interface ThreeDPreviewProps {
  colorBlocks: ColorBlock[];
  mappedBlockColors: MappedBlockColor[];
  filamentColors: FilamentColorConfig[];
  imageDimensions: ImageDimensions;
  layerHeight: number;
  pixelSize: number;
  layerCount: number;
  whiteBackingLayers: number;
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
  filamentColors,
  imageDimensions,
  layerHeight,
  pixelSize,
  layerCount,
  whiteBackingLayers,
  printStack,
}) => {
  const { t } = useTranslation();
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

  const backingHex = useMemo(
    () => resolvePreviewBackingHex(mappedBlockColors, filamentColors, whiteBackingLayers),
    [mappedBlockColors, filamentColors, whiteBackingLayers],
  );

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
      modelGroupRef.current = null;
    }
    if (whiteBackingLayers > 0 && backingHex === null) return;

    const group = buildInstancedMeshes(
      colorBlocks,
      mappedBlockColors,
      imageDimensions,
      pixelSize,
      layerHeight,
      layerCount,
      whiteBackingLayers,
      backingHex,
      visibilityMap,
      showExploded,
    );

    modelGroupRef.current = group;
    scene.add(group);

    const modelWidth = imageDimensions.width * pixelSize;
    const modelDepth = imageDimensions.height * pixelSize;
    const gap = showExploded ? Math.max(layerHeight * 0.5, Math.max(modelWidth, modelDepth) * 0.02) : 0;
    const bottom = 0;
    const top = (whiteBackingLayers + layerCount) * layerHeight
      + Math.max(0, whiteBackingLayers + layerCount - 1) * gap;
    new THREE.Box3(
      new THREE.Vector3(-modelWidth / 2, bottom, -modelDepth / 2),
      new THREE.Vector3(modelWidth / 2, top, modelDepth / 2),
    ).getBoundingSphere(boundsRef.current);
    if (gridRef.current) {
      gridRef.current.position.y = bottom - Math.max(layerHeight, Math.max(modelWidth, modelDepth) * 0.005);
    }
    if (cameraRef.current) updatePreviewCameraClipping(cameraRef.current, boundsRef.current);
  }, [colorBlocks, mappedBlockColors, imageDimensions, pixelSize, layerHeight, layerCount, whiteBackingLayers, backingHex, visibilityMap, showExploded]);

  // Initialize three.js scene
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // CSS sets the viewport size; the renderer follows it.
    const width = container.clientWidth;
    const height = container.clientHeight;

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
      track('webgl_unavailable');
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

    // Follow the container, which also resizes when the settings rail toggles.
    const resizeObserver = new ResizeObserver(() => {
      const newWidth = container.clientWidth;
      const newHeight = container.clientHeight;
      if (newWidth === 0 || newHeight === 0) return;
      camera.aspect = newWidth / newHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(newWidth, newHeight);
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
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
      <div className="rounded-sheet border border-dashed border-rule-strong p-6 text-center text-sm text-ink-muted">
        <Layers className="mx-auto mb-2 h-5 w-5" aria-hidden="true" />{t('preview:3dPreviewUnavailableWebglNotSupported')}</div>
    );
  }

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="tv-heading flex items-center gap-2 text-xl">
          <Layers className="h-5 w-5" aria-hidden="true" />{t('preview:3dPreview')}</h3>
        <div className="flex gap-1">
          <button
            type="button"
            onClick={handleResetView}
            className="tv-btn-ghost tv-btn-sm"
            title={t('preview:resetCamera')}
          >
            <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />{t('common:reset')}</button>
          <button
            type="button"
            onClick={handleFitView}
            className="tv-btn-ghost tv-btn-sm"
            title={t('preview:topDownView')}
          >
            <Maximize2 className="h-3.5 w-3.5" aria-hidden="true" />{t('preview:top')}</button>
          <button
            type="button"
            onClick={() => setShowExploded(!showExploded)}
            aria-pressed={showExploded}
            className="tv-btn-ghost tv-btn-sm aria-pressed:bg-ink aria-pressed:text-paper-raised"
            title={t('preview:toggleExplodedView')}
          >
            <Layers className="h-3.5 w-3.5" aria-hidden="true" />{t('preview:exploded')}</button>
        </div>
      </div>

      {/* Size info */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-xs text-ink-muted">
        <span>{physicalWidth} × {physicalHeight} mm</span>
        <span>{t('preview:height')}{' '}{totalHeight} mm</span>
        <span>{t('preview:layers')}{' '}{printStack.opticalLayerCount} + {printStack.whiteBackingLayers}</span>
        <span>{t('preview:voxels', { count: totalPixels })}</span>
        {isLargeModel && <span className="text-signal-warn">{t('preview:largeModel')}</span>}
      </div>

      {/* WebGL canvas */}
      <div
        ref={containerRef}
        className="h-[360px] w-full overflow-hidden rounded-sheet border border-rule sm:h-[480px]"
      />

      {/* Color visibility toggles */}
      <div className="flex flex-wrap items-center gap-1.5">
        <button
          type="button"
          onClick={toggleAllVisibility}
          className="tv-btn-outline tv-btn-sm"
        >
          {colorVisibility.every(cv => cv.visible) ? t('preview:hideAll') : t('preview:showAll')}
        </button>
        {colorVisibility.map(cv => (
          <button
            key={cv.hex}
            onClick={() => toggleColorVisibility(cv.hex)}
            type="button"
            aria-pressed={cv.visible}
            className={`flex items-center gap-1.5 rounded-sheet border px-2 py-1 font-mono text-xs transition-colors ${
              cv.visible ? 'border-rule-strong bg-paper-raised text-ink hover:border-ink' : 'border-rule bg-transparent text-ink-muted'
            }`}
            title={t('preview:visibility', { action: cv.visible ? t('common:hide') : t('common:show'), hex: cv.hex, count: cv.count })}
          >
            <span
              className="h-3 w-3 border border-ink/40"
              style={{ backgroundColor: cv.hex, opacity: cv.visible ? 1 : 0.3 }}
            />
            {cv.visible ? <Eye className="h-3 w-3" aria-hidden="true" /> : <EyeOff className="h-3 w-3" aria-hidden="true" />}
            <span>{cv.count}</span>
          </button>
        ))}
      </div>

      <p className="tv-help">{t('preview:dragToRotateScrollToZoomRightClickTo')}</p>
    </section>
  );
};
