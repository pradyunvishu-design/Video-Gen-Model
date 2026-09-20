// Browser workflow coverage only. Real capture/export is tested separately in Rust.
import { test, expect } from '@playwright/test';

test('normal browser never pretends to record', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('This browser view cannot record or access your library.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Start recording' })).toBeDisabled();
});

test('record, trim, save and export workflow with a mocked desktop boundary', async ({ page }) => {
  await page.addInitScript(() => {
    const win = window as any;
    let active = false;
    let projects: any[] = [];
    const project = { id: 'test-fixture', title: 'SYNTHETIC browser test ' + 'long recording title '.repeat(4), createdAt: '2026-09-20T00:00:00Z', duration: 12,
      width: 1920, height: 1080, hasAudio: false, sourcePath: '/synthetic-source.mp4', posterPath: null,
      edits: { trimStart: 0, trimEnd: 12, crop: null, padding: 32, background: '#111827', zoomEvents: [], cursorHighlight: true, callouts: [], transcript: '' }, exports: [] as any[] };
    win.isTauri = true;
    win.__TAURI_EVENT_PLUGIN_INTERNALS__ = { unregisterListener() {} };
    win.__TAURI_INTERNALS__ = {
      transformCallback: () => 1,
      convertFileSrc: () => '/synthetic-placeholder.mp4',
      invoke: async (command: string, args: any) => {
        if (command.startsWith('plugin:event|')) return 1;
        switch (command) {
          case 'get_capabilities': return { platform: 'windows', ffmpegAvailable: true, ffprobeAvailable: true, dataDir: 'SYNTHETIC TEST', microphoneSupported: true, notes: [] };
          case 'list_sources': return [{ id: 'screen:test', name: 'Synthetic display', kind: 'screen', x: 0, y: 0, width: 1920, height: 1080 }];
          case 'list_microphones': return [];
          case 'list_projects': return structuredClone(projects);
          case 'recording_status': return { status: active ? 'recording' : 'idle', projectId: active ? project.id : null, elapsedSeconds: active ? 3 : 0, error: null };
          case 'start_recording': active = true; return { status: 'recording', projectId: project.id, elapsedSeconds: 0, error: null };
          case 'stop_recording': active = false; projects = [project]; return structuredClone(project);
          case 'save_edits': project.edits = args.edits; return structuredClone(project);
          case 'export_project': { const artifact = { path: '/synthetic-export.mp4', posterPath: '/poster.jpg', transcriptPath: '/transcript.txt', summaryPath: '/summary.md', preset: args.preset }; project.exports.push(artifact); return artifact; }
          default: throw new Error(`Unexpected test command: ${command}`);
        }
      },
    };
  });
  await page.route('**/synthetic-placeholder.mp4', route => route.fulfill({ status: 204 }));
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Start recording' })).toBeDisabled();
  await page.getByRole('combobox', { name: 'Screen', exact: true }).selectOption('screen:test');
  await page.getByRole('button', { name: 'Start recording' }).click();
  await expect(page.getByLabel('Recording timer')).toBeVisible();
  await page.getByRole('button', { name: 'Stop recording', exact: true }).click();
  await expect(page.getByRole('heading', { name: /^SYNTHETIC browser test/ })).toBeVisible();
  const libraryFits = await page.locator('.project-item').evaluate(button => {
    const bounds = button.getBoundingClientRect();
    const sidebar = button.closest('.sidebar')!.getBoundingClientRect();
    return bounds.right <= sidebar.right && button.scrollWidth <= button.clientWidth + 1;
  });
  expect(libraryFits, 'Long recording names must not overlap the editor').toBe(true);
  await page.getByLabel('Trim end (seconds)').fill('0');
  await expect(page.getByRole('button', { name: 'Save edits' })).toBeDisabled();
  await page.getByLabel('Trim end (seconds)').fill('10');
  await page.getByRole('button', { name: 'Save edits' }).click();
  await expect(page.getByText('All edits saved')).toBeVisible();
  await page.getByRole('button', { name: 'Export video' }).click();
  await expect(page.getByText('Export complete. Your files are ready.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'View latest export' })).toBeVisible();
  await page.screenshot({ path: 'test-results/studio-editor.png', fullPage: true });
});
