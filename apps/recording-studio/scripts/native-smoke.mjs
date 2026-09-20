// Explicit opt-in Windows native acceptance against our synthetic window only.
// Starts a dedicated WebView2 debugging endpoint for this test-owned app process.
import { chromium } from '@playwright/test';
import { spawn, spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';

if (process.platform !== 'win32' || process.env.STUDIO_NATIVE_TEST !== '1') {
  throw new Error('Set STUDIO_NATIVE_TEST=1 on Windows to test a dedicated synthetic window.');
}
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const projectTitle = `SYNTHETIC native acceptance ${Date.now()}`;
mkdirSync(join(root, 'test-results'), { recursive: true });
writeFileSync(join(root, 'test-results/native-smoke.json'), JSON.stringify({ passed: false, status: 'running', fixtureOnly: true }));
const exe = join(root, 'src-tauri/target/debug/recording-studio.exe');
if (!existsSync(exe)) throw new Error('Build the debug executable first.');
const endpoint = 'http://127.0.0.1:9237';
try { await fetch(endpoint + '/json/version'); throw new Error('Test debugging port is already occupied.'); }
catch (error) { if (error.message.includes('already occupied')) throw error; }
const fixture = await chromium.launch({ channel: 'chrome', headless: false, args: ['--window-size=1040,700', '--window-position=0,0'] });
const fixturePage = await fixture.newPage({ viewport: { width: 960, height: 540 } });
await fixturePage.setContent('<!doctype html><title>Recording Studio Synthetic Fixture</title><style>body{background:#141b1f;color:white;font:28px system-ui;margin:48px} .shape{width:120px;height:120px;background:#8bbeaa;animation:move 3s ease-in-out infinite alternate}@keyframes move{to{transform:translateX(450px)}}</style><h1>SYNTHETIC CAPTURE TEST</h1><p>Test-owned window. No personal data. Microphone off.</p><div class="shape"></div>');
const app = spawn(exe, [], { cwd: root, windowsHide: true, stdio: 'ignore',
  env: { ...process.env, WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS: '--remote-debugging-port=9237' } });
let browser;
let started = false;
let main;
try {
  for (let i = 0; i < 90; i++) {
    try { const response = await fetch(endpoint + '/json/version'); if (response.ok) break; } catch {}
    await delay(500);
  }
  browser = await chromium.connectOverCDP(endpoint);
  for (let i = 0; i < 90; i++) {
    const pages = browser.contexts().flatMap(context => context.pages());
    main = pages.find(page => !page.url().includes('hud=1') && /127\.0\.0\.1:1420|tauri\.localhost|tauri:\/\//.test(page.url()));
    if (main) break;
    await delay(500);
  }
  if (!main) throw new Error('Native main window did not load. Start npm run web:dev before this debug test.');
  await main.getByRole('combobox', { name: 'Capture mode', exact: true }).selectOption('window');
  await main.getByRole('button', { name: 'Refresh sources and library' }).click();
  const source = main.getByRole('combobox', { name: 'Window', exact: true });
  await source.locator('option').filter({ hasText: /^Recording Studio Synthetic Fixture/ }).waitFor({ state: 'attached' });
  const value = await source.locator('option').filter({ hasText: /^Recording Studio Synthetic Fixture/ }).getAttribute('value');
  if (!value) throw new Error('Synthetic fixture unavailable; refusing any fallback capture.');
  await source.selectOption(value);
  await main.getByRole('textbox', { name: 'Recording title' }).fill(projectTitle);
  await main.getByRole('button', { name: 'Start recording', exact: true }).click();
  started = true;
  let recording;
  for (let i = 0; i < 30; i++) {
    recording = await main.evaluate(() => window.__TAURI_INTERNALS__.invoke('recording_status'));
    if (recording.status === 'recording' && recording.elapsedSeconds >= 3) break;
    const alerts = await main.getByRole('alert').allTextContents();
    if (recording.error || alerts.length) throw new Error(`Capture startup failed: ${recording.error || alerts.join(' ')}`);
    await delay(400);
  }
  if (recording?.status !== 'recording') throw new Error(`Capture never became active: ${JSON.stringify(recording)}`);
  const hud = browser.contexts().flatMap(context => context.pages()).find(page => page.url().includes('hud=1'));
  if (!hud) throw new Error('Recording HUD missing.');
  const timer = await hud.getByLabel('Recording timer').textContent();
  if (timer === '00:00') throw new Error('Recording timer did not advance.');
  await hud.getByRole('button', { name: 'Stop', exact: true }).click();
  await main.getByRole('button', { name: new RegExp(projectTitle) }).click();
  started = false;
  await main.getByRole('heading', { name: projectTitle, exact: true }).waitFor();
  const sourceVideo = main.getByLabel('Recording preview');
  await sourceVideo.evaluate(async video => { await video.play(); });
  await delay(300);
  const sourcePlayback = await sourceVideo.evaluate(video => ({ ready: video.readyState, width: video.videoWidth, height: video.videoHeight, duration: video.duration }));
  if (sourcePlayback.ready < 2 || sourcePlayback.width < 16) throw new Error('Native source preview did not decode.');
  const sourcePath = await main.evaluate(async title => (await window.__TAURI_INTERNALS__.invoke('list_projects')).find(project => project.title === title).sourcePath, projectTitle);
  const pixels = spawnSync(process.env.FFMPEG_PATH || 'ffmpeg', ['-v', 'error', '-ss', '0.5', '-i', sourcePath, '-vf', 'scale=160:90', '-frames:v', '1', '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1'], { windowsHide: true, timeout: 20000 });
  if (pixels.status !== 0 || pixels.stdout.length !== 160 * 90 * 3) throw new Error('Pixel verification could not decode the recorded fixture.');
  const rgb = pixels.stdout;
  const sample = { bright: 0, mint: 0 };
  for (let i = 0; i < rgb.length; i += 3) {
    if (rgb[i] > 180 && rgb[i + 1] > 180 && rgb[i + 2] > 180) sample.bright++;
    if (rgb[i + 1] > rgb[i] + 25 && rgb[i + 1] > rgb[i + 2] + 10) sample.mint++;
  }
  if (sample.bright < 20 || sample.mint < 10) throw new Error(`Capture decoded but synthetic text/shape missing (black or wrong pixels): ${JSON.stringify(sample)}`);
  await main.getByRole('button', { name: 'Export video', exact: true }).click();
  await main.getByText('Export complete. Your files are ready.').waitFor({ timeout: 120000 });
  await main.getByRole('button', { name: 'View latest export' }).click();
  await sourceVideo.evaluate(async video => { await video.play(); });
  await delay(300);
  const exportPlayback = await sourceVideo.evaluate(video => ({ ready: video.readyState, width: video.videoWidth, height: video.videoHeight, duration: video.duration }));
  if (exportPlayback.width !== 1920 || exportPlayback.height !== 1080) throw new Error('Native export is not 1080p.');
  const results = join(root, 'test-results'); mkdirSync(results, { recursive: true });
  await main.screenshot({ path: join(results, 'native-studio.png'), fullPage: true });
  const report = { passed: true, fixtureOnly: true, microphone: false, timer, sourcePlayback, exportPlayback, sample, checked: ['actual Win32 window capture', 'synthetic pixels present (not black)', 'Tauri IPC', 'HUD stop', 'SQLite save', 'source WebView2 playback', 'FFmpeg H264 export', 'export WebView2 playback'] };
  writeFileSync(join(results, 'native-smoke.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report));
} catch (error) {
  if (main) await main.screenshot({ path: join(root, 'test-results/native-failure.png'), fullPage: true }).catch(() => {});
  writeFileSync(join(root, 'test-results/native-smoke.json'), JSON.stringify({ passed: false, error: error.message, fixtureOnly: true }, null, 2));
  throw error;
} finally {
  if (started && main) {
    await main.evaluate(() => window.__TAURI_INTERNALS__.invoke('stop_recording')).catch(() => {});
  }
  await browser?.close().catch(() => {});
  app.kill(); await fixture.close();
}
