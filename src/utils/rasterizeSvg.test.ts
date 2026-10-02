import { describe, it, expect } from 'vitest';
import { isSvgFile, rasterSize, sizeSvgMarkup, svgIntrinsicSize } from './rasterizeSvg';

const svgRoot = (attrs: string) =>
  new DOMParser().parseFromString(`<svg xmlns="http://www.w3.org/2000/svg" ${attrs}/>`, 'image/svg+xml').documentElement;

describe('isSvgFile', () => {
  it('accepts the SVG media type and untyped .svg files only', () => {
    expect(isSvgFile(new File([''], 'logo.svg', { type: 'image/svg+xml' }))).toBe(true);
    expect(isSvgFile(new File([''], 'LOGO.SVG', { type: '' }))).toBe(true);
    expect(isSvgFile(new File([''], 'logo.svg', { type: 'text/plain' }))).toBe(false);
    expect(isSvgFile(new File([''], 'photo.png', { type: 'image/png' }))).toBe(false);
  });
});

describe('svgIntrinsicSize', () => {
  it('takes the viewBox when width and height are absent', () => {
    expect(svgIntrinsicSize(svgRoot('viewBox="0 0 64 32"'))).toEqual({ width: 64, height: 32 });
  });

  it('prefers absolute width and height, converting units to px', () => {
    expect(svgIntrinsicSize(svgRoot('width="2in" height="96px" viewBox="0 0 1 1"'))).toEqual({ width: 192, height: 96 });
  });

  it('derives a missing side from the viewBox ratio', () => {
    expect(svgIntrinsicSize(svgRoot('width="100" viewBox="0 0 4 2"'))).toEqual({ width: 100, height: 50 });
  });

  it('ignores percentage sizes and falls back to the browser default', () => {
    expect(svgIntrinsicSize(svgRoot('width="100%" height="100%"'))).toEqual({ width: 300, height: 150 });
  });
});

describe('rasterSize', () => {
  it('scales the longest side to the target and keeps the aspect ratio', () => {
    expect(rasterSize({ width: 64, height: 64 }, 2048)).toEqual({ width: 2048, height: 2048 });
    expect(rasterSize({ width: 300, height: 150 }, 2048)).toEqual({ width: 2048, height: 1024 });
    expect(rasterSize({ width: 10, height: 4000 }, 1000)).toEqual({ width: 3, height: 1000 });
  });
});

describe('sizeSvgMarkup', () => {
  it('writes explicit pixel dimensions onto a viewBox-only SVG', () => {
    const { markup, size } = sizeSvgMarkup(
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><path d="M0 0h64v64z"/></svg>',
      2048,
    );
    expect(size).toEqual({ width: 2048, height: 2048 });
    const svg = new DOMParser().parseFromString(markup, 'image/svg+xml').documentElement;
    expect(svg.getAttribute('width')).toBe('2048');
    expect(svg.getAttribute('height')).toBe('2048');
    expect(svg.getAttribute('viewBox')).toBe('0 0 64 64');
    expect(svg.getElementsByTagName('path')).toHaveLength(1);
  });

  it('adds a viewBox so content scales with the new size', () => {
    const { markup } = sizeSvgMarkup('<svg xmlns="http://www.w3.org/2000/svg" width="20" height="10"/>', 200);
    const svg = new DOMParser().parseFromString(markup, 'image/svg+xml').documentElement;
    expect(svg.getAttribute('viewBox')).toBe('0 0 20 10');
    expect(svg.getAttribute('width')).toBe('200');
    expect(svg.getAttribute('height')).toBe('100');
  });

  it('rejects markup that is not an SVG document', () => {
    expect(() => sizeSvgMarkup('<svg', 100)).toThrow();
    expect(() => sizeSvgMarkup('<html xmlns="http://www.w3.org/1999/xhtml"/>', 100)).toThrow();
  });
});
