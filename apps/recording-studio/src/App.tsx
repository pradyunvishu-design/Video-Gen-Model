import { useCallback, useEffect, useRef, useState } from 'react';
import { invoke, isTauri } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import { Circle, Monitor, Mic, Square, Video, RefreshCw, ShieldCheck, Film, PanelLeft, Scissors, X } from 'lucide-react';
import Editor, { RectFields } from './Editor';
import type { Capabilities, CaptureRequest, CaptureSource, EditPlan, Project, RecordingStatus, Rect } from './types';
import { clock, validRect } from './types';

const idle: RecordingStatus = { status: 'idle', projectId: null, elapsedSeconds: 0, error: null };
const errorText = (error: unknown) => error instanceof Error ? error.message : String(error);

function useRecording(enabled: boolean, onStopped?: () => void) {
  const [status, setStatus] = useState<RecordingStatus>(idle);
  const [error, setError] = useState('');
  const onStoppedRef = useRef(onStopped);
  onStoppedRef.current = onStopped;
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let timeout: ReturnType<typeof setTimeout>;
    let unlisten: (() => void) | undefined;
    let previous = 'idle';
    const poll = async () => {
      try {
        const next = await invoke<RecordingStatus>('recording_status');
        if (cancelled) return;
        setStatus(next);
        setError(next.error ?? '');
        if (previous !== 'idle' && next.status === 'idle') onStoppedRef.current?.();
        previous = next.status;
      } catch (failure) { if (!cancelled) setError(errorText(failure)); }
      if (!cancelled) timeout = setTimeout(() => void poll(), 1000);
    };
    void poll();
    void listen('recording-stopped', () => { if (!cancelled) { setStatus(idle); onStoppedRef.current?.(); } }).then(dispose => { if (cancelled) dispose(); else unlisten = dispose; }).catch(failure => { if (!cancelled) setError(`Tray updates unavailable: ${errorText(failure)}`); });
    return () => { cancelled = true; clearTimeout(timeout); unlisten?.(); };
  }, [enabled]);
  return { status, setStatus, error };
}

function Hud() {
  const { status, setStatus, error } = useRecording(isTauri());
  const [stopping, setStopping] = useState(false);
  const [failure, setFailure] = useState('');
  const stop = async () => {
    setStopping(true);
    try { await invoke('stop_recording'); setStatus(idle); } catch (issue) { setFailure(errorText(issue)); } finally { setStopping(false); }
  };
  return <div className="hud"><span className={`record-dot ${status.status === 'recording' ? 'live' : ''}`} /><span className="hud-label">{status.status === 'idle' ? 'Stopped' : status.status === 'error' ? 'Needs attention' : 'Recording'}</span><output aria-label="Recording timer">{clock(status.elapsedSeconds)}</output><button className="stop" disabled={stopping || (status.status !== 'recording' && !(status.status === 'error' && status.projectId))} onClick={() => void stop()}><Square size={13} fill="currentColor" />{stopping ? 'Stopping…' : 'Stop'}</button>{(failure || error) && <p role="alert">{failure || error}</p>}</div>;
}

export default function App() {
  return new URLSearchParams(window.location.search).get('hud') === '1' ? <Hud /> : <Studio />;
}

function Studio() {
  const desktop = isTauri();
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null);
  const [sources, setSources] = useState<CaptureSource[]>([]);
  const [microphones, setMicrophones] = useState<string[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [request, setRequest] = useState<CaptureRequest>({ sourceId: '', mode: 'screen', region: null, microphone: null, title: '' });
  const [region, setRegion] = useState<Rect>({ x: 0, y: 0, width: 1280, height: 720 });
  const [loading, setLoading] = useState(desktop);
  const [busy, setBusy] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const librarySequence = useRef(0);
  const refreshLibrary = useCallback(async () => {
    const sequence = ++librarySequence.current;
    try { const value = await invoke<Project[]>('list_projects'); if (sequence === librarySequence.current) setProjects(value); } catch (failure) { setError(errorText(failure)); }
  }, []);
  const { status, setStatus, error: recordingError } = useRecording(desktop, () => void refreshLibrary());
  const load = useCallback(async () => {
    if (!desktop) return;
    setLoading(true); setError('');
    try {
      const [caps, available, saved, mics] = await Promise.allSettled([invoke<Capabilities>('get_capabilities'), invoke<CaptureSource[]>('list_sources'), invoke<Project[]>('list_projects'), invoke<string[]>('list_microphones')]);
      const warnings: string[] = [];
      if (caps.status === 'fulfilled') setCapabilities(caps.value); else { setCapabilities(null); warnings.push(`Desktop capabilities unavailable: ${errorText(caps.reason)}`); }
      if (available.status === 'fulfilled') setSources(available.value); else { setSources([]); warnings.push(`Capture sources unavailable: ${errorText(available.reason)}`); }
      if (saved.status === 'fulfilled') setProjects(saved.value); else warnings.push(`Library unavailable: ${errorText(saved.reason)}`);
      if (mics.status === 'fulfilled') setMicrophones(mics.value); else { setMicrophones([]); setRequest(previous => ({ ...previous, microphone: null })); warnings.push(`Microphone unavailable. Silent recording is still available: ${errorText(mics.reason)}`); }
      setError(warnings.join(' '));
    } catch (failure) { setError(errorText(failure)); } finally { setLoading(false); }
  }, [desktop]);
  useEffect(() => { void load(); }, [load]);
  const recording = status.projectId !== null || ['starting', 'recording', 'stopping'].includes(status.status);
  const locked = busy || exporting || recording;
  const selected = projects.find(project => project.id === selectedId);
  const source = sources.find(item => item.id === request.sourceId);
  const sourceChoices = sources.filter(item => item.kind === (request.mode === 'window' ? 'window' : 'screen'));
  const regionError = request.mode === 'region' && source && !validRect(region, source.width, source.height) ? 'Region must fit within the selected screen using whole pixels.' : '';
  const canRecord = desktop && !!capabilities?.ffmpegAvailable && !!capabilities?.ffprobeAvailable && !!source && !regionError && !locked && !loading;
  const run = async (action: () => Promise<void>) => {
    setBusy(true); setError(''); setNotice('');
    try { await action(); } catch (failure) { setError(errorText(failure)); } finally { setBusy(false); }
  };
  const replaceProject = (project: Project) => setProjects(previous => [project, ...previous.filter(item => item.id !== project.id)]);
  const start = () => run(async () => {
    if (dirty && !window.confirm('Start a new recording and discard unsaved edits?')) return;
    const result = await invoke<RecordingStatus>('start_recording', { request: { ...request, title: request.title.trim() || 'Untitled recording', region: request.mode === 'region' ? region : null } });
    setStatus(result);
    setSelectedId(null); setDirty(false);
  });
  const stop = () => run(async () => { const project = await invoke<Project>('stop_recording'); replaceProject(project); setSelectedId(project.id); setStatus(idle); setNotice('Recording saved locally.'); });
  const exportProject = async (preset: 'h264' | 'webm') => {
    if (!selected) return;
    setExporting(true); setError(''); setNotice('');
    try { await invoke('export_project', { projectId: selected.id, preset }); await refreshLibrary(); setNotice('Export complete. Your files are ready.'); } catch (failure) { setError(errorText(failure)); } finally { setExporting(false); }
  };
  const transcribe = async (edits: EditPlan): Promise<EditPlan | null> => {
    if (!selected) return null;
    setBusy(true); setError(''); setNotice('');
    try {
      replaceProject(await invoke<Project>('save_edits', { projectId: selected.id, edits }));
      const project = await invoke<Project>('transcribe_project', { projectId: selected.id });
      replaceProject(project); setNotice('Transcript generated locally. Review it before exporting.');
      return project.edits;
    } catch (failure) { setError(errorText(failure)); return null; } finally { setBusy(false); }
  };
  return <div className="studio-shell">
    <header className="topbar"><div className="brand"><div className="brand-icon"><Video size={21} /></div><span>Recording Studio<small>A local workspace</small></span></div><div className="privacy"><ShieldCheck size={15} /><span>On your device. Under your control.</span></div><span className="version">V1</span></header>
    {!desktop && <div className="desktop-required" role="status"><Monitor size={19} /><div><strong>Open Recording Studio on your desktop</strong><p>This browser view cannot record or access your library. Launch the desktop app to get started.</p></div></div>}
    <div className="workspace">
      <aside className="sidebar">
        <section className="capture"><div className="section-heading"><h2>New recording</h2><button aria-label="Refresh sources and library" className="icon-button" disabled={!desktop || locked || loading} onClick={() => void load()}><RefreshCw size={16} /></button></div>
          <fieldset disabled={!desktop || locked || loading} className="capture-fields"><label className="field">Recording title<input placeholder="A quick product walkthrough" maxLength={120} value={request.title} onChange={event => setRequest({ ...request, title: event.target.value })} /></label>
          <label className="field">Capture mode<select value={request.mode} onChange={event => setRequest({ ...request, mode: event.target.value as CaptureRequest['mode'], sourceId: '' })}><option value="screen">Entire screen</option><option value="window">One window</option><option value="region">Screen region</option></select></label>
          <label className="field">{request.mode === 'window' ? 'Window' : 'Screen'}<select value={request.sourceId} onChange={event => { setRequest({ ...request, sourceId: event.target.value }); const next = sources.find(item => item.id === event.target.value); if (next) setRegion({ x: 0, y: 0, width: next.width, height: next.height }); }}><option value="">Choose a {request.mode === 'window' ? 'window' : 'screen'}…</option>{sourceChoices.map(item => <option key={item.id} value={item.id}>{item.name} · {item.width} × {item.height}</option>)}</select></label>
          {request.mode === 'region' && <><RectFields prefix="Region" value={region} onChange={setRegion} /><p className="hint">Coordinates are relative to the selected screen.</p></>}
          <label className="field"><span className="inline-label"><Mic size={14} />Microphone</span><select disabled={!capabilities?.microphoneSupported} value={request.microphone ?? ''} onChange={event => setRequest({ ...request, microphone: event.target.value || null })}><option value="">Off · silent recording</option>{microphones.map(name => <option key={name} value={name}>{name}</option>)}</select></label>
          <p className="hint">System audio is off. Check your screen for private information before recording.</p></fieldset>
          {regionError && <p role="alert" className="validation">{regionError}</p>}
          {recording ? <div className="recording-controls"><div className="live-status"><span className="record-dot live" /><span>{status.status === 'starting' ? 'Starting…' : status.status === 'stopping' ? 'Saving…' : status.status === 'error' ? 'Needs attention · stop to recover' : 'Recording'}</span><output aria-label="Recording timer">{clock(status.elapsedSeconds)}</output></div><button className="stop full" disabled={busy || (status.status !== 'recording' && !(status.status === 'error' && status.projectId))} onClick={() => void stop()}><Square size={14} fill="currentColor" />Stop recording</button></div> : <button className="record-button full" disabled={!canRecord} onClick={() => void start()}><Circle size={14} fill="currentColor" />{busy ? 'Working…' : 'Start recording'}</button>}
          {capabilities && (!capabilities.ffmpegAvailable || !capabilities.ffprobeAvailable) && <p className="validation" role="alert">FFmpeg and FFprobe are required. Install them, then refresh.</p>}
          {capabilities?.notes.map(note => <p className="hint" key={note}>{note}</p>)}
        </section>
        <section className="library"><div className="section-heading"><h2><Film size={16} />Your recordings</h2><span className="count">{projects.length}</span></div>{loading && <p className="hint" role="status">Loading your workspace…</p>}{!loading && projects.length === 0 && <p className="library-empty">Your first recording will appear here.<br /><span>Nothing leaves this device.</span></p>}<div className="project-list">{projects.map(project => <button disabled={locked} className={`project-item ${selectedId === project.id ? 'selected' : ''}`} key={project.id} onClick={() => { if (selectedId === project.id || (dirty && !window.confirm('Discard unsaved edits and open this recording?'))) return; setDirty(false); setSelectedId(project.id); }}><span className="project-icon"><Video size={18} /></span><span><strong>{project.title}</strong><small>{clock(project.duration)} · {new Date(project.createdAt).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</small></span><span className="project-arrow">↗</span></button>)}</div></section>
        <div className="sidebar-foot"><span className="local-dot" />Local storage{capabilities && <span title={capabilities.dataDir}>{capabilities.dataDir}</span>}</div>
      </aside>
      <div className="main-column">{(error || recordingError) && <div className="error-banner" role="alert"><span>{error || recordingError}</span><button className="text-button" disabled={locked || loading} onClick={() => void load()}>Retry</button>{error && <button aria-label="Dismiss error" className="icon-button" onClick={() => setError('')}><X size={15} /></button>}</div>}{notice && <div className="notice" role="status">{notice}</div>}
        {selected ? <Editor key={selected.id} project={selected} locked={locked} exporting={exporting} onDirtyChange={setDirty} onTranscribe={transcribe} onSave={edits => run(async () => { replaceProject(await invoke<Project>('save_edits', { projectId: selected.id, edits })); setNotice('Edits saved. Original recording preserved.'); })} onExport={exportProject} onCancel={() => void run(async () => { await invoke('cancel_export'); setNotice('Cancellation requested.'); })} onCopy={() => void run(async () => { const path = await invoke<string>('project_file_path', { projectId: selected.id }); await navigator.clipboard.writeText(path); setNotice('File path copied.'); })} onReveal={() => void run(async () => { await invoke('reveal_project', { projectId: selected.id }); })} /> : <main className="empty-workspace"><div className="empty-preview"><div className="viewfinder"><span /><span /><Monitor size={45} strokeWidth={1} /><span /><span /></div><span className="eyebrow">YOUR SCREEN. YOUR STORY.</span></div><h1>A little less setup.<br />A little more showing.</h1><p>Choose a screen or window to capture.<br />Then trim, frame and export it right here.</p><div className="workflow"><span><PanelLeft size={16} />Choose a source</span><i>→</i><span><Circle size={14} />Record</span><i>→</i><span><Scissors size={16} />Make it yours</span></div><p className="empty-note">No account. No upload. Just your work.</p></main>}
      </div>
    </div>
  </div>;
}
