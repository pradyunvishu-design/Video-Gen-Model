export interface Rect { x: number; y: number; width: number; height: number }
export interface CaptureSource extends Rect { id: string; name: string; kind: 'screen' | 'window' }
export interface Capabilities { platform: string; ffmpegAvailable: boolean; ffprobeAvailable: boolean; dataDir: string; microphoneSupported: boolean; notes: string[] }
export interface CaptureRequest { sourceId: string; mode: 'screen' | 'window' | 'region'; region: Rect | null; microphone: string | null; title: string }
export interface ZoomEvent { start: number; end: number; x: number; y: number; scale: number }
export interface Callout { start: number; end: number; x: number; y: number; text: string }
export interface EditPlan { trimStart: number; trimEnd: number; crop: Rect | null; padding: number; background: string; zoomEvents: ZoomEvent[]; cursorHighlight: boolean; callouts: Callout[]; transcript: string }
export interface ExportArtifact { path: string; posterPath: string; summaryPath: string; transcriptPath: string; preset: 'h264' | 'webm' }
export interface Project { id: string; title: string; createdAt: string; duration: number; width: number; height: number; hasAudio: boolean; sourcePath: string; posterPath: string | null; edits: EditPlan; exports: ExportArtifact[] }
export interface RecordingStatus { status: 'idle' | 'starting' | 'recording' | 'stopping' | 'error'; projectId: string | null; elapsedSeconds: number; error: string | null }

export function clock(seconds: number): string {
  const value = Math.max(0, Math.floor(seconds));
  return `${String(Math.floor(value / 60)).padStart(2, '0')}:${String(value % 60).padStart(2, '0')}`;
}

export function validRect(rect: Rect, width: number, height: number): boolean {
  return Object.values(rect).every(Number.isFinite) && Object.values(rect).every(Number.isInteger) && rect.x >= 0 && rect.y >= 0 && rect.width >= 16 && rect.height >= 16 && rect.x + rect.width <= width && rect.y + rect.height <= height;
}

export function validateEdits(edits: EditPlan, project: Pick<Project, 'duration' | 'width' | 'height'>): string | null {
  if (!Number.isFinite(edits.trimStart) || !Number.isFinite(edits.trimEnd) || edits.trimStart < 0 || edits.trimEnd > project.duration + 0.001 || edits.trimEnd - edits.trimStart < 0.05) return 'Trim end must be after start, at least 0.05 seconds later, and within the recording duration.';
  if (edits.crop && !validRect(edits.crop, project.width, project.height)) return 'Crop must use whole pixels, be at least 16 × 16, and fit inside the source image.';
  if (!Number.isInteger(edits.padding) || edits.padding < 0 || edits.padding > 400) return 'Padding must be a whole number from 0 to 400 pixels.';
  if (!/^#[0-9a-f]{6}$/i.test(edits.background)) return 'Background must be a six-digit hex color.';
  if (edits.zoomEvents.length > 24 || edits.callouts.length > 32 || new TextEncoder().encode(edits.transcript).length > 200000) return 'Use at most 24 zooms, 32 callouts and a transcript under 200 KB.';
  for (const event of [...edits.zoomEvents, ...edits.callouts]) {
    if (![event.start, event.end, event.x, event.y].every(Number.isFinite) || event.start < 0 || event.end > project.duration || event.end <= event.start) return 'Every zoom and callout must have a valid time range inside the source recording.';
    if (event.x < 0 || event.x > 1 || event.y < 0 || event.y > 1) return 'Zoom and callout positions must be between 0 and 1.';
  }
  if (edits.zoomEvents.some(event => !Number.isFinite(event.scale) || event.scale < 1 || event.scale > 3)) return 'Zoom scale must be between 1 and 3.';
  if (edits.callouts.some(event => !event.text.trim() || Array.from(event.text).length > 160 || event.text.includes('\0'))) return 'Each callout needs text, up to 160 characters, without null characters.';
  return null;
}
