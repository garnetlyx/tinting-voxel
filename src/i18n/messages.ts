import type { i18n as I18n } from 'i18next';
import { useTranslation } from './index';
import errors from './locales/en/errors.json';

// Compatibility adapter for canonical frontend/API messages. Never rewrite state or transport data.
// Keep transport matching independent from editable English display copy.
const exactMessages = new Map<string, keyof typeof errors>([
  ["Failed to process image", "failedToProcessImage"],
  ["Failed to simulate print preview", "failedToSimulatePrintPreview"],
  ["Failed to download CSV", "failedToDownloadCSV"],
  ["Failed to get filament presets", "failedToGetFilamentPresets"],
  ["Failed to download STL", "failedToDownloadSTL"],
  ["Failed to get filament preview", "failedToGetFilamentPreview"],
  ["Failed to download 3MF", "failedToDownload3MF"],
  ["Failed to download print settings", "failedToDownloadPrintSettings"],
  ["Failed to process batch", "failedToProcessBatch"],
  ["Failed to download batch STL", "failedToDownloadBatchSTL"],
  ["Failed to load palette library", "failedToLoadPaletteLibrary"],
  ["Failed to load palettes", "failedToLoadPalettes"],
  ["Failed to load preview", "failedToLoadPreview"],
  ["Failed to start parameter search", "failedToStartParameterSearch"],
  ["A search is already running. Cancel it or wait for it to finish.", "searchAlreadyRunning"],
  ["Optimization failed. Please try again.", "optimizationFailedPleaseTryAgain"],
  ["Too many reports. Please try again in an hour.", "tooManyReportsPleaseTryAgainInAnHour"],
  ["Could not send your report. Please try again.", "couldNotSendYourReportPleaseTryAgain"],
  ["The server did not confirm your report. Please try again.", "theServerDidNotConfirmYourReportPleaseTryAgain"],
  ["Sending timed out. Please try again.", "sendingTimedOutPleaseTryAgain"],
  ["Could not capture the page. Uncheck the screenshot option to send the report without it.", "couldNotCaptureThePageUncheckTheScreenshotOptionToSendTheReportWithoutIt"],
  ["Failed to get 2D canvas context", "failedToGet2DCanvasContext"],
  ["Failed to load image. The file may be corrupted or not a valid image.", "failedToLoadImageTheFileMayBeCorruptedOrNotAValidImage"],
  ["Failed to read file.", "failedToReadFile"],
  ["Failed to read file", "failedToReadFileMessage"],
  ["CSV download is only available in Pixel mode", "csvDownloadIsOnlyAvailableInPixelMode"],
  ["Invalid filament color configuration", "invalidFilamentColorConfiguration"],
  ["Failed to refresh simulated preview", "failedToRefreshSimulatedPreview"],
  ["Failed to export presets", "failedToExportPresets"],
  ["File too large (max 1MB)", "fileTooLargeMax1MB"],
  ["Invalid format: expected an array of presets", "invalidFormatExpectedAnArrayOfPresets"],
  ["Failed to parse JSON", "failedToParseJSON"],
  ["An internal error occurred", "anInternalErrorOccurred"],
  ["Failed to fetch", "failedToFetch"],
  ["NetworkError when attempting to fetch resource.", "networkerrorWhenAttemptingToFetchResource"],
  ["Load failed", "loadFailed"],
  ["Screenshot is too large", "screenshotIsTooLarge"],
  ["Too many requests. Please try again shortly.", "tooManyRequestsTryAgainShortly"],
]);
const patterns: readonly [RegExp, keyof typeof errors, readonly string[]][] = [
  [/^Search stopped after (\d+)s; (\d+) of (\d+) previews completed\.$/, 'searchStoppedAtLimit', ['seconds', 'completed', 'total']],
  [/^Too many requests\. Please try again in (\d+) seconds\.$/, 'tooManyRequestsRetryIn', ['seconds']],
  [/^Image too large \((\d+)x(\d+)\)\. Maximum dimension is (\d+)px\.$/, 'imageTooLarge', ['width', 'height', 'max']],
  [/^Unsupported file type: (.*?)\. Please upload a PNG, JPEG, GIF, WebP, or BMP image\.$/, 'unsupportedType', ['type']],
  [/^(\d+) file\(s\) skipped \(unsupported format\)$/, 'skippedFiles', ['count']],
  [/^Maximum (\d+) images allowed\. Extra files were dropped\.$/, 'tooManyImages', ['max']],
  [/^Imported (\d+) preset\(s\) successfully$/, 'imported', ['count']],
  [/^Imported (\d+) preset\(s\)\. Errors: (.+)$/, 'importedWithErrors', ['count', 'details']],
  [/^Preset at index (\d+) is invalid and was skipped$/, 'invalidPreset', ['index']],
  [/^(.+) and (.+) are very similar \(distance: ([\d.]+)\)$/, 'similarColors', ['first', 'second', 'distance']],
];

export function localizeMessage(message: string | null | undefined, instance: I18n): string {
  if (!message) return '';
  const t = instance.getFixedT(null, 'errors');
  const key = exactMessages.get(message);
  if (key) return t(key);
  for (const [pattern, messageKey, names] of patterns) {
    const match = message.match(pattern);
    if (!match) continue;
    const values = Object.fromEntries(names.map((name, index) => [name, name === 'count' ? Number(match[index + 1]) : match[index + 1]]));
    if (typeof values.details === 'string') {
      values.details = values.details.split(', ').map(detail => localizeMessage(detail, instance)).join('; ');
    }
    return t(messageKey, values);
  }
  // Unknown server details and user-authored content must remain intact.
  return message;
}

export function useLocalizedMessage(): (message: string | null | undefined) => string {
  const { i18n } = useTranslation();
  return message => localizeMessage(message, i18n);
}
