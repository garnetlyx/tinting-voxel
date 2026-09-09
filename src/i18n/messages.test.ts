import { afterEach, describe, expect, it } from 'vitest';
import { i18n, setLocale } from './index';
import { localizeMessage } from './messages';

afterEach(() => setLocale('en'));

describe('frontend message compatibility adapter', () => {
  it.each([
    ['Failed to download STL', 'STL 下载失败'],
    ['Image too large (9000x6000). Maximum dimension is 8192px.', '图片过大（9000 × 6000）。最长边不得超过 8192 像素。'],
    ['Unsupported file type: image/avif. Please upload a PNG, JPEG, GIF, WebP, or BMP image.', '不支持此文件类型：image/avif。请上传 PNG、JPEG、GIF、WebP 或 BMP 图片。'],
    ['3 file(s) skipped (unsupported format)', '已跳过 3 个不支持格式的文件'],
    ['Maximum 20 images allowed. Extra files were dropped.', '最多允许 20 张图片，已忽略多余文件。'],
    ['Imported 7 preset(s) successfully', '成功导入 7 个预设'],
    ['Imported 2 preset(s). Errors: Failed to parse JSON', '已导入 2 个预设。错误：无法解析 JSON 文件'],
    ['Q and Z are very similar (distance: 2.5)', 'Q 与 Z 的颜色十分接近（距离：2.5）'],
  ])('adapts %s without changing the source message', (source, expected) => {
    setLocale('zh-CN');
    expect(localizeMessage(source, i18n)).toBe(expected);
    setLocale('en');
    expect(localizeMessage(source, i18n)).toBe(source);
  });

  it('matches legacy messages independently of editable English display copy', () => {
    const isolated = i18n.cloneInstance({ lng: 'en', forkResourceStore: true });
    isolated.addResource('en', 'errors', 'failedToDownloadSTL', 'Please try the STL download again.');
    expect(localizeMessage('Failed to download STL', isolated)).toBe('Please try the STL download again.');
  });

  it('preserves unknown server details and arbitrary names', () => {
    setLocale('zh-CN');
    expect(localizeMessage('Custom material Q-42: unsupported profile', i18n)).toBe('Custom material Q-42: unsupported profile');
    expect(localizeMessage(null, i18n)).toBe('');
  });
});
