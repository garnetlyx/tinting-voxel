import { afterEach, describe, expect, it } from 'vitest';
import { i18n, setLocale } from './index';
import { localizeMessage } from './messages';

afterEach(() => setLocale('en'));

describe('frontend message compatibility adapter', () => {
  it.each([
    ['Failed to download STL', 'STL 下载失败'],
    ['Unsupported file type: image/avif. Please upload a PNG, JPEG, GIF, WebP, BMP, or SVG image.', '不支持此文件类型：image/avif。请上传 PNG、JPEG、GIF、WebP、BMP 或 SVG 图片。'],
    ['3 file(s) skipped (unsupported format)', '已跳过 3 个不支持格式的文件'],
    ['Maximum 20 images allowed. Extra files were dropped.', '最多允许 20 张图片，已忽略多余文件。'],
    ['Imported 7 preset(s) successfully', '成功导入 7 个预设'],
    ['Imported 2 preset(s). Errors: Failed to parse JSON', '已导入 2 个预设。错误：无法解析 JSON 文件'],
    ['Q and Z are very similar (distance: 2.5)', 'Q 与 Z 的颜色十分接近（距离：2.5）'],
    ['Too many requests. Please try again in 42 seconds.', '请求过于频繁，请在 42 秒后重试。'],
    ['Too many requests. Please try again shortly.', '请求过于频繁，请稍后重试。'],
    ['This image has too much fine detail to export within the model size limit. Reduce the image size, raise the color merge threshold, or use fewer colors.', '图像细节过多，超出了可导出的模型规模。请缩小图像尺寸、提高颜色合并阈值或减少颜色数量。'],
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

  it('explains search admission and time limits in Chinese', () => {
    setLocale('zh-CN');
    expect(localizeMessage('A search is already running. Cancel it or wait for it to finish.', i18n))
      .toBe('另一轮方案比较仍在运行，请稍后重试。');
    expect(localizeMessage('Search stopped after 1800s; 3 of 21 previews completed.', i18n))
      .toBe('本轮搜索在 1800 秒后停止，已生成 3／21 张方案图。');
  });
});
