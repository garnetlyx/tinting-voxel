import { describe, expect, it, vi } from 'vitest';
import * as THREE from 'three';
import { buildInstancedMeshes, disposePreviewModel, mergePreviewPixels, updatePreviewCameraClipping } from './threeDPreviewScene';
import type { ColorBlock } from '../api/types';

const blocks: ColorBlock[] = [{
  r: 255, g: 0, b: 0, hex: '#ff0000', count: 1, pixels: [{ x: 0, y: 0 }],
}];
const mapped = [{ code: 'MMMM', rgb: [220, 20, 100], hex: '#dc1464' }];
const visibility = new Map([['#dc1464', true]]);

function build(backing = 1, base = 0, doubleSided = false, exploded = false, visible = true) {
  return buildInstancedMeshes(
    blocks, mapped, { width: 2, height: 2 }, 1, 0.08, 4,
    backing, base, doubleSided, visible ? visibility : new Map(), exploded,
  );
}

function firstHit(group: THREE.Group, fromBelow = false) {
  group.updateMatrixWorld(true);
  return new THREE.Raycaster(
    new THREE.Vector3(fromBelow ? 0.5 : -0.5, fromBelow ? -10 : 10, -0.5),
    new THREE.Vector3(0, fromBelow ? 1 : -1, 0),
  ).intersectObject(group, true)[0];
}

describe('3D preview layer visibility', () => {
  it.each([0, 1, 3])('shows the mapped colored face above %i backing layers', backing => {
    const group = build(backing);
    const hit = firstHit(group);
    expect(hit.object).toBeInstanceOf(THREE.InstancedMesh);
    const material = (hit.object as THREE.Mesh).material as THREE.MeshPhongMaterial;
    expect(material.color.getHexString()).toBe('dc1464');
    expect(material.transparent).toBe(false);
    expect(material.opacity).toBe(1);
    disposePreviewModel(group);
  });

  it.each([
    [0, 0, false], [1, 0, false], [3, 0.5, false], [1, 0, true], [3, 0.5, true],
  ] as const)('preserves total thickness (backing=%i, base=%f, double=%s)', (backing, base, double) => {
    const group = build(backing, base, double);
    const bounds = new THREE.Box3().setFromObject(group);
    expect(bounds.max.y - bounds.min.y).toBeCloseTo((4 * (double ? 2 : 1) + backing) * 0.08 + base, 6);
    if (double) expect(firstHit(group, true).object).toBeInstanceOf(THREE.InstancedMesh);
    disposePreviewModel(group);
  });

  it('reveals the backing when a color is hidden', () => {
    const group = build(1, 0, false, false, false);
    expect(firstHit(group).object).not.toBeInstanceOf(THREE.InstancedMesh);
    expect((firstHit(group).object as THREE.Mesh).material).toHaveProperty('opacity', 1);
    disposePreviewModel(group);
  });

  it('keeps every exploded color and backing layer separate', () => {
    const group = build(2, 0.5, true, true);
    const intervals: Array<[number, number]> = [];
    const matrix = new THREE.Matrix4();
    group.updateMatrixWorld(true);
    group.children.forEach(object => {
      if (object instanceof THREE.InstancedMesh) {
        for (let index = 0; index < object.count; index++) {
          object.getMatrixAt(index, matrix);
          const y = matrix.elements[13];
          intervals.push([y - 0.04, y + 0.04]);
        }
      } else {
        const bounds = new THREE.Box3().setFromObject(object);
        intervals.push([bounds.min.y, bounds.max.y]);
      }
    });
    intervals.sort((a, b) => a[0] - b[0]);
    expect(intervals).toHaveLength(11);
    intervals.slice(1).forEach((interval, index) => {
      expect(interval[0]).toBeGreaterThanOrEqual(intervals[index][1] - 1e-6);
    });
    expect(firstHit(group).object).toBeInstanceOf(THREE.InstancedMesh);
    disposePreviewModel(group);
  });
});

describe('3D preview depth precision', () => {
  it.each([1, 4])('separates 0.08 mm layers on a 160 × 200 mm model at zoom distance factor %i', factor => {
    const camera = new THREE.PerspectiveCamera(45, 1.6, 0.01, 1000);
    camera.position.set(280 * factor, 200 * factor, 280 * factor);
    camera.lookAt(0, 0, 0);
    camera.updateMatrixWorld();
    const bounds = new THREE.Box3(new THREE.Vector3(-80, 0, -100), new THREE.Vector3(80, 0.4, 100));
    updatePreviewCameraClipping(camera, bounds.getBoundingSphere(new THREE.Sphere()));
    const depth = (y: number) => new THREE.Vector3(0, y, 0).project(camera).z * 0.5 + 0.5;
    expect(Math.abs(depth(0.32) - depth(0.4)) * (2 ** 24 - 1)).toBeGreaterThan(100);
    for (const x of [-80, 80]) for (const y of [0, 0.4]) for (const z of [-100, 100]) {
      const projected = new THREE.Vector3(x, y, z).project(camera);
      expect(projected.z).toBeGreaterThan(-1);
      expect(projected.z).toBeLessThan(1);
    }
  });

  it('keeps clipping planes valid inside the model bounds during close zoom', () => {
    const camera = new THREE.PerspectiveCamera();
    camera.position.set(0, 2, 0);
    updatePreviewCameraClipping(camera, new THREE.Sphere(new THREE.Vector3(), 130));
    expect(camera.near).toBeGreaterThan(0);
    expect(camera.near).toBeLessThan(1.6);
    expect(camera.far).toBeGreaterThan(200);
  });
});

describe('3D preview resource disposal', () => {
  it('disposes shared resources once and uses fresh materials when rebuilt', () => {
    const group = build(2, 0, true, true);
    const front = group.children[0] as THREE.Mesh;
    const instanceDispose = vi.spyOn(front as THREE.InstancedMesh, 'dispose');
    const geometryDispose = vi.spyOn(front.geometry, 'dispose');
    const materialDispose = vi.spyOn(front.material as THREE.Material, 'dispose');
    disposePreviewModel(group);
    expect(instanceDispose).toHaveBeenCalledTimes(1);
    expect(geometryDispose).toHaveBeenCalledTimes(1);
    expect(materialDispose).toHaveBeenCalledTimes(1);
    const rebuilt = build(2, 0, true, true);
    expect((rebuilt.children[0] as THREE.Mesh).material).not.toBe(front.material);
    disposePreviewModel(rebuilt);
  });
});

describe('3D preview surface merging', () => {
  it('preserves colored pixels, hidden colors and holes across irregular regions', () => {
    const width = 37;
    const height = 29;
    const source = ['#ff0000', '#0000ff', '#00ff00', '#990000'].map(hex => ({
      r: 0, g: 0, b: 0, hex, count: 0, pixels: [] as Array<{ x: number; y: number }>,
    }));
    const expected = new Map<string, string>();
    for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
      if ((x + y) % 11 === 0) continue;
      const index = (Math.floor(x / 4) + Math.floor(y / 3)) % 4;
      source[index].pixels.push({ x, y });
      if (index !== 2) expected.set(`${x},${y}`, index === 3 ? '#ff0000' : source[index].hex);
    }
    const mappedColors = source.map((block, index) => ({
      code: '', rgb: [0, 0, 0], hex: index === 3 ? '#ff0000' : block.hex,
    }));
    const rectangles = mergePreviewPixels(source, mappedColors, { width, height },
      new Map([['#ff0000', true], ['#0000ff', true], ['#00ff00', false]]));
    const actual = new Map<string, string>();
    for (const [hex, regions] of rectangles) for (const region of regions) {
      for (let y = region.y; y < region.y + region.height; y++) {
        for (let x = region.x; x < region.x + region.width; x++) {
          const key = `${x},${y}`;
          expect(actual.has(key)).toBe(false);
          actual.set(key, hex);
        }
      }
    }
    expect(actual).toEqual(expected);
  });

  it('renders a solid 1,250,000-pixel area as one correctly sized block', () => {
    const pixels: Array<{ x: number; y: number }> = [];
    for (let y = 0; y < 1250; y++) for (let x = 0; x < 1000; x++) pixels.push({ x, y });
    const group = buildInstancedMeshes(
      [{ ...blocks[0], count: pixels.length, pixels }], mapped,
      { width: 1000, height: 1250 }, 0.16, 0.08, 4, 1, 0, false, visibility, false,
    );
    const mesh = group.children[0] as THREE.InstancedMesh;
    expect(mesh.count).toBe(1);
    const size = new THREE.Box3().setFromObject(mesh).getSize(new THREE.Vector3());
    expect(size.x).toBeCloseTo(160, 4);
    expect(size.z).toBeCloseTo(200, 4);
    expect(size.y).toBeCloseTo(0.32, 6);
    disposePreviewModel(group);
  });
});
