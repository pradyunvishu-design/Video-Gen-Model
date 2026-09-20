import '@testing-library/jest-dom/vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import type { Project, RecordingStatus } from './types';

const bridge = vi.hoisted(() => ({ invoke: vi.fn(), isTauri: vi.fn(() => true), listen: vi.fn(), events: new Map<string, () => void>() }));
vi.mock('@tauri-apps/api/core', () => ({ invoke: bridge.invoke, isTauri: bridge.isTauri, convertFileSrc: (path: string) => `asset://localhost/${path}` }));
vi.mock('@tauri-apps/api/event', () => ({ listen: bridge.listen }));

const syntheticProject: Project = { id: 'synthetic-test', title: 'Synthetic recording', createdAt: '2026-09-20T12:00:00Z', duration: 10, width: 1920, height: 1080, hasAudio: false, sourcePath: 'synthetic/source.mp4', posterPath: null, edits: { trimStart: 0, trimEnd: 10, crop: null, padding: 0, background: '#f5f4f0', zoomEvents: [], cursorHighlight: false, callouts: [], transcript: '' }, exports: [] };
let saved: Project[];
let recording: RecordingStatus;
beforeEach(() => {
  vi.clearAllMocks(); bridge.events.clear(); bridge.isTauri.mockReturnValue(true); window.history.replaceState(null, '', '/');
  saved = []; recording = { status: 'idle', projectId: null, elapsedSeconds: 0, error: null };
  bridge.listen.mockImplementation(async (event: string, callback: () => void) => { bridge.events.set(event, callback); return () => bridge.events.delete(event); });
  bridge.invoke.mockImplementation(async (command: string, args?: Record<string, any>) => {
    switch (command) {
      case 'get_capabilities': return { platform: 'windows', ffmpegAvailable: true, ffprobeAvailable: true, microphoneSupported: true, dataDir: 'synthetic', notes: [] };
      case 'list_sources': return [{ id: 'screen-1', name: 'Synthetic display', kind: 'screen', x: 0, y: 0, width: 1920, height: 1080 }];
      case 'list_microphones': return ['Synthetic microphone'];
      case 'list_projects': return saved;
      case 'recording_status': return recording;
      case 'start_recording': recording = { status: 'recording', projectId: 'synthetic-test', elapsedSeconds: 3, error: null }; return recording;
      case 'stop_recording': saved = [structuredClone(syntheticProject)]; recording = { status: 'idle', projectId: null, elapsedSeconds: 0, error: null }; return saved[0];
      case 'save_edits': saved = [{ ...saved[0], edits: args?.edits }]; return saved[0];
      case 'transcribe_project': saved = [{ ...saved[0], edits: { ...saved[0].edits, transcript: 'Synthetic local transcript.' } }]; return saved[0];
      case 'export_project': { const artifact = { path: 'synthetic/export.mp4', posterPath: 'synthetic/poster.jpg', transcriptPath: 'synthetic/transcript.txt', summaryPath: 'synthetic/summary.json', preset: args?.preset }; saved = [{ ...saved[0], exports: [artifact] }]; return artifact; }
      case 'cancel_export': return null;
      case 'project_file_path': return 'synthetic/export.mp4';
      case 'reveal_project': return null;
      default: throw new Error(`Unexpected command: ${command}`);
    }
  });
});

describe('Recording Studio', () => {
  it('requires desktop runtime without synthetic production content', () => {
    bridge.isTauri.mockReturnValue(false); render(<App />);
    expect(screen.getByText('Open Recording Studio on your desktop')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Start recording' })).toBeDisabled();
    expect(bridge.invoke).not.toHaveBeenCalled();
  });
  it('requires explicit source choice and supports record, edit and export', async () => {
    const user = userEvent.setup(); render(<App />);
    await screen.findByRole('option', { name: /Synthetic display/ });
    expect(screen.getByRole('button', { name: 'Start recording' })).toBeDisabled();
    await user.selectOptions(screen.getByLabelText('Screen'), 'screen-1');
    await user.click(screen.getByRole('button', { name: 'Start recording' }));
    expect(await screen.findByLabelText('Recording timer')).toHaveTextContent('00:03');
    await user.click(screen.getByRole('button', { name: 'Stop recording' }));
    await screen.findByRole('heading', { name: 'Synthetic recording' });
    expect(screen.getByLabelText('Recording preview')).toHaveAttribute('src', 'asset://localhost/synthetic/source.mp4');
    await user.clear(screen.getByLabelText('Trim start (seconds)')); await user.type(screen.getByLabelText('Trim start (seconds)'), '2');
    expect(screen.getByRole('button', { name: 'Export video' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'Save edits' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Export video' })).toBeEnabled());
    await user.click(screen.getByRole('button', { name: 'Export video' }));
    expect(await screen.findByText('Export complete. Your files are ready.')).toBeInTheDocument();
    expect(bridge.invoke).toHaveBeenCalledWith('save_edits', expect.objectContaining({ projectId: 'synthetic-test', edits: expect.objectContaining({ trimStart: 2 }) }));
    expect(bridge.invoke).toHaveBeenCalledWith('export_project', { projectId: 'synthetic-test', preset: 'h264' });
  });
  it('blocks invalid edits', async () => {
    saved = [structuredClone(syntheticProject)]; const user = userEvent.setup(); render(<App />);
    await user.click(await screen.findByRole('button', { name: /Synthetic recording/ }));
    await user.clear(screen.getByLabelText('Trim end (seconds)')); await user.type(screen.getByLabelText('Trim end (seconds)'), '99');
    expect(screen.getByText(/Trim end must be after start/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Save edits' })).toBeDisabled();
  });
  it('shows recoverable preview errors without blocking edits or export', async () => {
    saved = [structuredClone(syntheticProject)]; const user = userEvent.setup(); render(<App />);
    await user.click(await screen.findByRole('button', { name: /Synthetic recording/ }));
    expect(screen.getByText('Loading local preview…')).toBeInTheDocument();
    fireEvent.error(screen.getByLabelText('Recording preview'));
    expect(screen.getByText('Preview could not be loaded')).toBeInTheDocument();
    expect(screen.getByLabelText('Trim start (seconds)')).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Export video' })).toBeEnabled();
    await user.click(screen.getByRole('button', { name: 'Open recording folder' }));
    expect(bridge.invoke).toHaveBeenCalledWith('reveal_project', { projectId: 'synthetic-test' });
    await user.click(screen.getByRole('button', { name: 'Retry preview' }));
    expect(screen.getByText('Loading local preview…')).toBeInTheDocument();
    fireEvent.loadedData(screen.getByLabelText('Recording preview'));
    expect(screen.queryByText('Loading local preview…')).not.toBeInTheDocument();
    expect(screen.queryByText('Preview could not be loaded')).not.toBeInTheDocument();
  });
  it('keeps editing and recording locked while export is running and permits cancellation', async () => {
    saved = [structuredClone(syntheticProject)];
    const implementation = bridge.invoke.getMockImplementation()!;
    let rejectExport: ((error: Error) => void) | undefined;
    bridge.invoke.mockImplementation((command: string, args?: Record<string, any>) => command === 'export_project' ? new Promise((_, reject) => { rejectExport = reject; }) : implementation(command, args));
    const user = userEvent.setup(); render(<App />);
    await user.selectOptions(await screen.findByLabelText('Screen'), 'screen-1');
    await user.click(await screen.findByRole('button', { name: /Synthetic recording/ }));
    await user.click(screen.getByRole('button', { name: 'Export video' }));
    expect(screen.getByRole('button', { name: 'Start recording' })).toBeDisabled();
    expect(screen.getByLabelText('Trim start (seconds)')).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'Cancel export' }));
    expect(bridge.invoke).toHaveBeenCalledWith('cancel_export');
    await act(async () => { rejectExport?.(new Error('Export cancelled')); });
    expect(await screen.findByText('Export cancelled')).toBeInTheDocument();
    expect(screen.getByLabelText('Trim start (seconds)')).toBeEnabled();
  });
  it('does not overlap status requests and updates the timer after a response', async () => {
    vi.useFakeTimers();
    try {
      window.history.replaceState(null, '', '/?hud=1');
      let resolveStatus: ((status: RecordingStatus) => void) | undefined;
      bridge.invoke.mockImplementation(() => new Promise(resolve => { resolveStatus = resolve; }));
      const view = render(<App />);
      await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
      expect(bridge.invoke).toHaveBeenCalledTimes(1);
      await act(async () => { resolveStatus?.({ status: 'recording', projectId: 'synthetic-test', elapsedSeconds: 9, error: null }); });
      expect(screen.getByLabelText('Recording timer')).toHaveTextContent('00:09');
      await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
      expect(bridge.invoke).toHaveBeenCalledTimes(2);
      view.unmount();
    } finally { vi.useRealTimers(); }
  });
  it('keeps invalid screen regions from starting capture', async () => {
    const user = userEvent.setup(); render(<App />);
    await screen.findByRole('option', { name: /Synthetic display/ });
    await user.selectOptions(screen.getByLabelText('Capture mode'), 'region');
    await user.selectOptions(screen.getByLabelText('Screen'), 'screen-1');
    await user.clear(screen.getByLabelText('Region width')); await user.type(screen.getByLabelText('Region width'), '9000');
    expect(screen.getByText(/Region must fit within/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Start recording' })).toBeDisabled();
  });
  it('refreshes the library after a tray stop', async () => {
    render(<App />); await screen.findByRole('option', { name: /Synthetic display/ });
    saved = [structuredClone(syntheticProject)];
    await act(async () => { bridge.events.get('recording-stopped')?.(); });
    expect(await screen.findByRole('button', { name: /Synthetic recording/ })).toBeInTheDocument();
  });
  it('saves pending edits before local transcription and shows the generated transcript', async () => {
    saved = [{ ...structuredClone(syntheticProject), hasAudio: true }]; const user = userEvent.setup(); render(<App />);
    await user.click(await screen.findByRole('button', { name: /Synthetic recording/ }));
    await user.clear(screen.getByLabelText('Trim start (seconds)')); await user.type(screen.getByLabelText('Trim start (seconds)'), '1');
    await user.click(screen.getByText('Transcript', { selector: 'summary span' }));
    await user.click(screen.getByRole('button', { name: 'Generate transcript locally' }));
    await waitFor(() => expect(screen.getByLabelText('Transcript')).toHaveValue('Synthetic local transcript.'));
    const commands = bridge.invoke.mock.calls.map(call => call[0]);
    expect(commands.indexOf('save_edits')).toBeLessThan(commands.indexOf('transcribe_project'));
    expect(screen.getByLabelText('Trim start (seconds)')).toHaveValue(1);
  });
  it('shows a recoverable local-model error without losing edits', async () => {
    saved = [{ ...structuredClone(syntheticProject), hasAudio: true }];
    const implementation = bridge.invoke.getMockImplementation()!;
    bridge.invoke.mockImplementation((command: string, args?: Record<string, any>) => command === 'transcribe_project' ? Promise.reject(new Error('Local Whisper model not configured. Set STUDIO_WHISPER_MODEL.')) : implementation(command, args));
    const user = userEvent.setup(); render(<App />);
    await user.click(await screen.findByRole('button', { name: /Synthetic recording/ }));
    await user.click(screen.getByText('Transcript', { selector: 'summary span' }));
    await user.click(screen.getByRole('button', { name: 'Generate transcript locally' }));
    expect(await screen.findByText(/Local Whisper model not configured/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Generate transcript locally' })).toBeEnabled();
    expect(screen.getByLabelText('Transcript')).toBeEnabled();
  });
  it('shows the HUD timer and stops through the same command', async () => {
    window.history.replaceState(null, '', '/?hud=1'); recording = { status: 'recording', projectId: 'synthetic-test', elapsedSeconds: 65, error: null };
    const user = userEvent.setup(); render(<App />);
    await waitFor(() => expect(screen.getByLabelText('Recording timer')).toHaveTextContent('01:05'));
    await user.click(screen.getByRole('button', { name: 'Stop' }));
    expect(await screen.findByText('Stopped')).toBeInTheDocument();
    expect(bridge.invoke).toHaveBeenCalledWith('stop_recording');
  });
  it.each(['/', '/?hud=1'])('allows Stop to recover an active failed recording at %s', async location => {
    window.history.replaceState(null, '', location);
    recording = { status: 'error', projectId: 'synthetic-test', elapsedSeconds: 5, error: 'Recorder exited unexpectedly' };
    const user = userEvent.setup(); render(<App />);
    const stop = await screen.findByRole('button', { name: location === '/' ? 'Stop recording' : 'Stop' });
    await waitFor(() => expect(stop).toBeEnabled());
    expect(screen.queryByRole('button', { name: 'Start recording' })).not.toBeInTheDocument();
    await user.click(stop);
    expect(bridge.invoke).toHaveBeenCalledWith('stop_recording');
  });
  it('keeps the library usable if capture sources and microphone enumeration fail', async () => {
    saved = [structuredClone(syntheticProject)];
    const implementation = bridge.invoke.getMockImplementation()!;
    bridge.invoke.mockImplementation((command: string, args?: Record<string, any>) => ['list_sources', 'list_microphones'].includes(command) ? Promise.reject(new Error('Permission denied. Allow screen capture in Settings.')) : implementation(command, args));
    const user = userEvent.setup(); render(<App />);
    await user.click(await screen.findByRole('button', { name: /Synthetic recording/ }));
    expect(await screen.findByRole('heading', { name: 'Synthetic recording' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Export video' })).toBeEnabled();
    expect(screen.getByText(/Capture sources unavailable/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Start recording' })).toBeDisabled();
  });
  it('allows silent capture when microphone enumeration fails', async () => {
    const implementation = bridge.invoke.getMockImplementation()!;
    bridge.invoke.mockImplementation((command: string, args?: Record<string, any>) => command === 'list_microphones' ? Promise.reject(new Error('Microphone permission denied.')) : implementation(command, args));
    const user = userEvent.setup(); render(<App />);
    await screen.findByRole('option', { name: /Synthetic display/ });
    await user.selectOptions(screen.getByLabelText('Screen'), 'screen-1');
    expect(screen.getByRole('button', { name: 'Start recording' })).toBeEnabled();
    expect(screen.getByText(/Microphone unavailable/)).toBeInTheDocument();
  });
});
