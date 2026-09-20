import { useEffect, useState } from 'react';
import { convertFileSrc } from '@tauri-apps/api/core';
import { FolderOpen, Copy, Plus, Trash2, Download } from 'lucide-react';
import type { EditPlan, Project, Rect } from './types';
import { clock, validateEdits } from './types';

export function NumberField({ label, value, onChange, step = 'any', min, max }: { label: string; value: number; onChange: (value: number) => void; step?: string; min?: number; max?: number }) {
  return <label className="field">{label}<input type="number" value={Number.isFinite(value) ? value : ''} min={min} max={max} step={step} onChange={event => onChange(event.target.value === '' ? NaN : Number(event.target.value))} /></label>;
}

export function RectFields({ value, onChange, prefix }: { value: Rect; onChange: (value: Rect) => void; prefix: string }) {
  return <div className="fields four">{(['x', 'y', 'width', 'height'] as const).map(key => <NumberField key={key} label={`${prefix} ${key}`} value={value[key]} step="1" onChange={next => onChange({ ...value, [key]: next })} />)}</div>;
}

function VideoPreview({ path, poster, locked, hasExport, onReveal }: { path: string; poster?: string; locked: boolean; hasExport: boolean; onReveal: () => void }) {
  const [state, setState] = useState<'loading' | 'ready' | 'error' | 'slow'>('loading');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (state !== 'loading') return;
    const timeout = setTimeout(() => setState('slow'), 12000);
    return () => clearTimeout(timeout);
  }, [state, attempt]);
  return <div className="preview">
    <video key={attempt} aria-label="Recording preview" controls preload="metadata" src={convertFileSrc(path)} poster={poster ? convertFileSrc(poster) : undefined} onLoadedData={() => setState('ready')} onCanPlay={() => setState('ready')} onError={() => setState('error')} />
    {state === 'loading' && <div className="preview-loading" role="status">Loading local preview…</div>}
    {(state === 'error' || state === 'slow') && <div className="preview-message" role={state === 'error' ? 'alert' : 'status'}><strong>{state === 'error' ? 'Preview could not be loaded' : 'Preview is taking longer than expected'}</strong><p>{state === 'error' ? 'The file may be missing or this video format may not play in the desktop viewer.' : 'The viewer has not loaded a video frame yet.'} {hasExport ? 'Try the latest export below, or open the recording folder.' : 'Open the recording folder to check the file.'} Your editing and export tools are still available.</p><div><button className="secondary" onClick={() => { setState('loading'); setAttempt(previous => previous + 1); }}>Retry preview</button><button className="secondary" disabled={locked} onClick={onReveal}><FolderOpen size={15} />Open recording folder</button></div></div>}
  </div>;
}

interface Props { project: Project; locked: boolean; exporting: boolean; onDirtyChange: (dirty: boolean) => void; onSave: (edits: EditPlan) => Promise<void>; onTranscribe: (edits: EditPlan) => Promise<EditPlan | null>; onExport: (preset: 'h264' | 'webm') => Promise<void>; onCancel: () => void; onCopy: () => void; onReveal: () => void }

export default function Editor({ project, locked, exporting, onDirtyChange, onSave, onTranscribe, onExport, onCancel, onCopy, onReveal }: Props) {
  const [edits, setEdits] = useState<EditPlan>(() => structuredClone(project.edits));
  const [preset, setPreset] = useState<'h264' | 'webm'>('h264');
  const [previewExport, setPreviewExport] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const generateTranscript = async () => {
    if (edits.transcript.trim() && !window.confirm('Replace the current transcript with a locally generated transcript?')) return;
    setTranscribing(true);
    try { const next = await onTranscribe(edits); if (next) setEdits(structuredClone(next)); } finally { setTranscribing(false); }
  };
  const dirty = JSON.stringify(edits) !== JSON.stringify(project.edits);
  useEffect(() => { onDirtyChange(dirty); }, [dirty, onDirtyChange]);
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);
  const validation = validateEdits(edits, project);
  const update = <K extends keyof EditPlan>(key: K, value: EditPlan[K]) => setEdits(previous => ({ ...previous, [key]: value }));
  const artifact = project.exports.at(-1);
  const path = previewExport && artifact ? artifact.path : project.sourcePath;
  return <main className="editor">
    <div className="section-heading"><div><span className="eyebrow">WORKSPACE</span><h2>{project.title}</h2></div><span className="metadata">{project.width} × {project.height} · {clock(project.duration)} · {project.hasAudio ? 'With audio' : 'Silent'}</span></div>
    <VideoPreview key={path} path={path} poster={!previewExport && project.posterPath ? project.posterPath : undefined} locked={locked} hasExport={!!artifact && !previewExport} onReveal={onReveal} />
    <div className="preview-bar"><span>{previewExport ? 'Export preview' : 'Original recording · edits apply on export'}</span>{artifact && <button className="text-button" onClick={() => setPreviewExport(!previewExport)}>{previewExport ? 'View original' : 'View latest export'}</button>}</div>
    <div className="edit-heading"><h3>Make it yours</h3><span className="metadata">Original always preserved</span></div>
    <fieldset disabled={locked} className="edit-controls">
      <details open><summary>01 <span>Trim & frame</span></summary><div className="detail-content">
        <div className="fields"><NumberField label="Trim start (seconds)" value={edits.trimStart} min={0} max={project.duration} onChange={value => update('trimStart', value)} /><NumberField label="Trim end (seconds)" value={edits.trimEnd} min={0} max={project.duration} onChange={value => update('trimEnd', value)} /><NumberField label="Padding (pixels)" value={edits.padding} min={0} max={400} step="1" onChange={value => update('padding', value)} /><label className="field">Background color<input type="color" value={edits.background} onChange={event => update('background', event.target.value)} /></label></div>
        <label className="check"><input type="checkbox" checked={edits.crop !== null} onChange={event => update('crop', event.target.checked ? { x: 0, y: 0, width: project.width, height: project.height } : null)} />Crop source</label>
        {edits.crop && <RectFields value={edits.crop} prefix="Crop" onChange={value => update('crop', value)} />}
        <p className="hint">Export canvas is 1920 × 1080. Framing preserves your source aspect ratio.</p>
      </div></details>
      <details><summary>02 <span>Zoom & cursor</span><small>{edits.zoomEvents.length} zooms</small></summary><div className="detail-content">
        <p className="hint">Times use the original recording. Position 0 is top/left; 1 is bottom/right.</p>
        {edits.zoomEvents.map((zoom, index) => <div className="event-row" key={index}><div className="fields"><NumberField label={`Zoom ${index + 1} start`} value={zoom.start} onChange={value => update('zoomEvents', edits.zoomEvents.map((item, i) => i === index ? { ...item, start: value } : item))} /><NumberField label={`Zoom ${index + 1} end`} value={zoom.end} onChange={value => update('zoomEvents', edits.zoomEvents.map((item, i) => i === index ? { ...item, end: value } : item))} />{(['x', 'y', 'scale'] as const).map(key => <NumberField key={key} label={`Zoom ${index + 1} ${key}`} value={zoom[key]} onChange={value => update('zoomEvents', edits.zoomEvents.map((item, i) => i === index ? { ...item, [key]: value } : item))} />)}</div><button aria-label={`Remove zoom ${index + 1}`} className="icon-button" onClick={() => update('zoomEvents', edits.zoomEvents.filter((_, i) => i !== index))}><Trash2 size={16} /></button></div>)}
        <button className="secondary" onClick={() => update('zoomEvents', [...edits.zoomEvents, { start: edits.trimStart, end: edits.trimEnd, x: 0.5, y: 0.5, scale: 1.5 }])}><Plus size={15} />Add zoom</button>
        <label className="check"><input type="checkbox" checked={edits.cursorHighlight} onChange={event => update('cursorHighlight', event.target.checked)} />Highlight cursor clicks</label>
      </div></details>
      <details><summary>03 <span>Text callouts</span><small>{edits.callouts.length} callouts</small></summary><div className="detail-content">
        <p className="hint">Position is relative to the finished canvas, from 0 to 1. Times use the original recording.</p>
        {edits.callouts.map((callout, index) => <div className="callout-row" key={index}><label className="field">Callout {index + 1} text<input maxLength={160} value={callout.text} onChange={event => update('callouts', edits.callouts.map((item, i) => i === index ? { ...item, text: event.target.value } : item))} /></label><div className="event-row"><div className="fields">{(['start', 'end', 'x', 'y'] as const).map(key => <NumberField key={key} label={`Callout ${index + 1} ${key}`} value={callout[key]} onChange={value => update('callouts', edits.callouts.map((item, i) => i === index ? { ...item, [key]: value } : item))} />)}</div><button aria-label={`Remove callout ${index + 1}`} className="icon-button" onClick={() => update('callouts', edits.callouts.filter((_, i) => i !== index))}><Trash2 size={16} /></button></div></div>)}
        <button className="secondary" onClick={() => update('callouts', [...edits.callouts, { start: edits.trimStart, end: edits.trimEnd, x: 0.1, y: 0.8, text: '' }])}><Plus size={15} />Add callout</button>
      </div></details>
      <details><summary>04 <span>Transcript</span><small>Editable sidecar</small></summary><div className="detail-content"><label className="field">Transcript<textarea rows={6} placeholder="Write or paste a transcript…" value={edits.transcript} onChange={event => update('transcript', event.target.value)} /></label><p className="hint">Saved with your export. No audio is sent to a transcription service.</p><button className="secondary" disabled={!project.hasAudio || !!validation || transcribing} onClick={() => void generateTranscript()}>{transcribing ? 'Transcribing locally…' : 'Generate transcript locally'}</button><p className="hint">{project.hasAudio ? 'Uses your configured local Whisper model. Pending edits are saved first.' : 'This recording has no audio. You can still write a transcript above.'}</p></div></details>
    </fieldset>
    {validation && <p className="validation" role="alert">{validation}</p>}
    <div className="save-row"><span className="metadata">{dirty ? 'Unsaved changes' : 'All edits saved'}</span><button className="secondary" disabled={locked || !dirty} onClick={() => setEdits(structuredClone(project.edits))}>Reset unsaved</button><button className="primary" disabled={locked || !dirty || !!validation} onClick={() => void onSave(edits)}>Save edits</button></div>
    <section className="export-bar" aria-label="Export recording"><div><h3>Ready for the next step</h3><p className="hint">Video, poster, summary and transcript. All local.</p></div><label className="field compact">Format<select disabled={locked} value={preset} onChange={event => setPreset(event.target.value as 'h264' | 'webm')}><option value="h264">MP4 · H.264</option><option value="webm">WebM · VP9</option></select></label>{exporting ? <button className="danger-outline" onClick={onCancel}>Cancel export</button> : <button className="primary" disabled={locked || dirty || !!validation} onClick={() => void onExport(preset)}><Download size={16} />Export video</button>}</section>
    {dirty && <p className="hint">Save your edits before exporting.</p>}
    {exporting && <p className="export-status" role="status"><span className="working-dot" />Rendering locally. You can cancel at any time.</p>}
    <div className="file-actions"><button className="text-button" disabled={locked} onClick={onCopy}><Copy size={15} />Copy {artifact ? 'export' : 'source'} path</button><button className="text-button" disabled={locked} onClick={onReveal}><FolderOpen size={16} />Open folder</button></div>
  </main>;
}
