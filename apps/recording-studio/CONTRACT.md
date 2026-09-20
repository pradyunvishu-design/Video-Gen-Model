# Recording Studio v1 IPC contract

All JSON fields camelCase. All media paths backend-owned. No arbitrary shell commands.
Types shared semantically across Rust serde and frontend TypeScript.

- Rect: `{x:number,y:number,width:number,height:number}`; crop coordinates in source pixels.
- CaptureSource: `{id:string,name:string,kind:'screen'|'window',x:number,y:number,width:number,height:number}`.
- Capabilities: `{platform:string,ffmpegAvailable:boolean,ffprobeAvailable:boolean,dataDir:string,microphoneSupported:boolean,notes:string[]}`.
- CaptureRequest: `{sourceId:string,mode:'screen'|'window'|'region',region:Rect|null,microphone:string|null,title:string}`. Region relative to selected screen origin. Mic device returned by list_microphones; null means off.
- ZoomEvent: `{start:number,end:number,x:number,y:number,scale:number}`. x/y normalized source coordinates.
- Callout: `{start:number,end:number,x:number,y:number,text:string}`. x/y normalized output coordinates.
- EditPlan: `{trimStart:number,trimEnd:number,crop:Rect|null,padding:number,background:string,zoomEvents:ZoomEvent[],cursorHighlight:boolean,callouts:Callout[],transcript:string}`.
- ExportArtifact: `{path:string,posterPath:string,summaryPath:string,transcriptPath:string,preset:'h264'|'webm'}`.
- Project: `{id:string,title:string,createdAt:string,duration:number,width:number,height:number,hasAudio:boolean,sourcePath:string,posterPath:string|null,edits:EditPlan,exports:ExportArtifact[]}`.
- RecordingStatus: `{status:'idle'|'starting'|'recording'|'stopping'|'error',projectId:string|null,elapsedSeconds:number,error:string|null}`.

Commands (Tauri invoke arguments in braces):

- get_capabilities {} -> Capabilities
- list_sources {} -> CaptureSource[]
- list_microphones {} -> string[]
- list_projects {} -> Project[]
- start_recording {request:CaptureRequest} -> RecordingStatus
- stop_recording {} -> Project
- recording_status {} -> RecordingStatus
- save_edits {projectId:string,edits:EditPlan} -> Project
- export_project {projectId:string,preset:'h264'|'webm'} -> ExportArtifact (async; UI stays responsive)
- cancel_export {} -> null
- transcribe_project {projectId:string} -> Project (optional local whisper.cpp, no external API)
- reveal_project {projectId:string} -> null (OS folder containing source/exports)
- project_file_path {projectId:string} -> string (latest export or source; frontend clipboard)

UI uses convertFileSrc for video/poster paths; asset scope is app-owned data only.
Tray Stop calls same stop operation as main UI and emits `recording-stopped`.
Recording HUD is a second always-on-top window at `/?hud=1`, shares recording_status polling.
No capture without explicit source selection/start. System audio is off.
Imported/generated fixtures for automated tests must be explicitly labeled synthetic.
