import { describe, expect, it } from 'vitest';
import { clock, validRect, validateEdits } from './types';
import type { EditPlan } from './types';

const edits: EditPlan = { trimStart: 0, trimEnd: 10, crop: null, padding: 30, background: '#ededed', zoomEvents: [], cursorHighlight: false, callouts: [], transcript: '' };
const project = { duration: 10, width: 1920, height: 1080 };
describe('non-destructive edit validation', () => {
  it('accepts a valid plan', () => expect(validateEdits(edits, project)).toBeNull());
  it.each([{ trimStart: -1 }, { trimEnd: 11 }, { trimEnd: 0 }, { trimStart: NaN }, { padding: -1 }, { padding: 401 }, { background: 'bad' }, { crop: { x: 1900, y: 0, width: 100, height: 100 } }, { crop: { x: 0.5, y: 0, width: 100, height: 100 } }, { zoomEvents: [{ start: 0, end: 10, x: 0.5, y: 0.5, scale: 5 }] }, { callouts: [{ start: 0, end: 11, x: 0.1, y: 0.1, text: 'Outside trim' }] }, { callouts: [{ start: 0, end: 2, x: 1.1, y: 0, text: 'Outside frame' }] }, { callouts: [{ start: 0, end: 2, x: 0, y: 0, text: '' }] }])('rejects invalid plan %j', partial => expect(validateEdits({ ...edits, ...partial }, project)).toBeTruthy());
  it('bounds region selection', () => { expect(validRect({ x: 0, y: 0, width: 1920, height: 1080 }, 1920, 1080)).toBe(true); expect(validRect({ x: -1, y: 0, width: 100, height: 100 }, 1920, 1080)).toBe(false); });
  it('formats recording time', () => { expect(clock(61.9)).toBe('01:01'); expect(clock(-1)).toBe('00:00'); });
});
