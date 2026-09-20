mod capture;
mod export;
mod model;
mod platform;
mod process;
mod storage;
mod transcription;
use model::*;
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc,
};
use tauri::{Emitter, Manager};
#[derive(Clone)]
struct Studio {
    store: storage::Store,
    capture: Arc<capture::Capture>,
    exporting: Arc<AtomicBool>,
    cancel: Arc<AtomicBool>,
    transcribing: Arc<AtomicBool>,
}
#[derive(serde::Serialize)]
#[serde(rename_all = "camelCase")]
struct Capabilities {
    platform: String,
    ffmpeg_available: bool,
    ffprobe_available: bool,
    data_dir: String,
    microphone_supported: bool,
    notes: Vec<String>,
}
#[tauri::command]
async fn get_capabilities(state: tauri::State<'_, Studio>) -> Result<Capabilities, String> {
    let root = state.store.root.clone();
    tauri::async_runtime::spawn_blocking(move||Capabilities{platform:std::env::consts::OS.into(),ffmpeg_available:process::available("ffmpeg"),ffprobe_available:process::available("ffprobe"),data_dir:storage::path_string(&root),microphone_supported:cfg!(any(windows,target_os="macos")),notes:vec!["Local only. System audio is not captured. Sources are never overwritten by edits.".into(),if cfg!(windows){"Windows records composed screen pixels cropped to the selected window or region. Keep that window visible, unobstructed, and at a fixed size/position; capture stops when these checks fail. Optional DirectShow microphone; no system audio.".into()}else{"macOS requires 15+, the bundled ScreenCaptureKit helper, and screen/microphone permissions. macOS build is not verified on Windows.".into()},"Zoom/callout times use the original source timeline. Exports are 1920×1080 at 30 fps.".into(),"Transcript can be entered manually or generated with optional local Whisper. Summary is an extractive excerpt, not an AI-generated summary.".into()]}).await.map_err(|e|e.to_string())
}
#[tauri::command]
async fn list_sources() -> Result<Vec<CaptureSource>, String> {
    tauri::async_runtime::spawn_blocking(platform::sources)
        .await
        .map_err(|e| e.to_string())?
}
#[tauri::command]
async fn list_microphones() -> Result<Vec<String>, String> {
    tauri::async_runtime::spawn_blocking(platform::microphones)
        .await
        .map_err(|e| e.to_string())?
}
#[tauri::command]
fn list_projects(state: tauri::State<'_, Studio>) -> Result<Vec<Project>, String> {
    state.store.list()
}
#[tauri::command]
fn recording_status(state: tauri::State<'_, Studio>) -> RecordingStatus {
    state.capture.status()
}
#[tauri::command]
async fn start_recording(
    app: tauri::AppHandle,
    state: tauri::State<'_, Studio>,
    request: CaptureRequest,
) -> Result<RecordingStatus, String> {
    let state = state.inner().clone();
    #[cfg(windows)]
    state.capture.set_hud(
        app.get_webview_window("hud")
            .and_then(|w| w.hwnd().ok())
            .map(|h| h.0 as isize),
    );
    if state.capture.status().project_id.is_some() {
        return Err("Stop the current recording first.".into());
    }
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.hide();
    }
    // Show before SCK enumerates exclusions so the HUD exists in the content snapshot.
    if let Some(w) = app.get_webview_window("hud") {
        let _ = w.show();
    }
    let result =
        tauri::async_runtime::spawn_blocking(move || state.capture.start(&state.store, request))
            .await
            .map_err(|e| e.to_string())
            .and_then(|r| r);
    if result.is_err() {
        if let Some(w) = app.get_webview_window("hud") {
            let _ = w.hide();
        }
        if let Some(w) = app.get_webview_window("main") {
            let _ = w.show();
        }
    }
    result
}
async fn stop_impl(app: tauri::AppHandle, state: Studio) -> Result<Project, String> {
    let p = tauri::async_runtime::spawn_blocking(move || state.capture.stop(&state.store))
        .await
        .map_err(|e| e.to_string())?;
    if let Some(w) = app.get_webview_window("hud") {
        let _ = w.hide();
    }
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.show();
        let _ = w.set_focus();
    }
    if let Ok(project) = &p {
        let _ = app.emit("recording-stopped", project);
    }
    p
}
#[tauri::command]
async fn stop_recording(
    app: tauri::AppHandle,
    state: tauri::State<'_, Studio>,
) -> Result<Project, String> {
    stop_impl(app, state.inner().clone()).await
}
#[tauri::command]
fn save_edits(
    state: tauri::State<'_, Studio>,
    project_id: String,
    edits: EditPlan,
) -> Result<Project, String> {
    state.store.modify(&project_id, |p| {
        validate_edits(&edits, p)?;
        p.edits = edits;
        Ok(())
    })
}
#[tauri::command]
async fn export_project(
    state: tauri::State<'_, Studio>,
    project_id: String,
    preset: String,
) -> Result<ExportArtifact, String> {
    let state = state.inner().clone();
    if state.exporting.swap(true, Ordering::SeqCst) {
        return Err("An export is already running.".into());
    }
    state.cancel.store(false, Ordering::SeqCst);
    let busy = state.exporting.clone();
    let result = tauri::async_runtime::spawn_blocking(move || {
        export::export(&state.store, &project_id, &preset, state.cancel)
    })
    .await
    .map_err(|e| e.to_string());
    busy.store(false, Ordering::SeqCst);
    result?
}
#[tauri::command]
fn cancel_export(state: tauri::State<'_, Studio>) {
    state.cancel.store(true, Ordering::SeqCst);
}
#[tauri::command]
async fn transcribe_project(
    state: tauri::State<'_, Studio>,
    project_id: String,
) -> Result<Project, String> {
    if state.transcribing.swap(true, Ordering::SeqCst) {
        return Err("Local transcription is already running.".into());
    }
    let store = state.store.clone();
    let busy = state.transcribing.clone();
    let result = tauri::async_runtime::spawn_blocking(move || {
        transcription::transcribe(&store, &project_id)
    })
    .await
    .map_err(|e| e.to_string());
    busy.store(false, Ordering::SeqCst);
    result?
}
#[tauri::command]
fn project_file_path(
    state: tauri::State<'_, Studio>,
    project_id: String,
) -> Result<String, String> {
    let p = state.store.get(&project_id)?;
    p.exports
        .iter()
        .rev()
        .map(|a| &a.path)
        .chain(std::iter::once(&p.source_path))
        .find(|path| std::path::Path::new(path).is_file())
        .cloned()
        .ok_or("Media is missing. Open the project folder to restore the source or export.".into())
}
#[tauri::command]
fn reveal_project(state: tauri::State<'_, Studio>, project_id: String) -> Result<(), String> {
    state.store.get(&project_id)?;
    let dir = state.store.dir(&project_id)?;
    #[cfg(windows)]
    let mut cmd = process::command("explorer.exe");
    #[cfg(target_os = "macos")]
    let mut cmd = process::command("open");
    #[cfg(not(any(windows, target_os = "macos")))]
    let mut cmd = process::command("xdg-open");
    cmd.arg(dir).spawn().map_err(|e| e.to_string())?;
    Ok(())
}
pub fn run() {
    let _ = dotenvy::dotenv();
    #[cfg(windows)]
    if let Some(index) = std::env::args().position(|a| a == "--capture-test-window") {
        let result = (|| {
            let title = std::env::args()
                .nth(index + 1)
                .ok_or("Supply an exact synthetic fixture window title.")?;
            if std::env::var("STUDIO_TEST_CAPTURE").as_deref() != Ok("1")
                || !title.starts_with("Recording Studio Synthetic Fixture")
            {
                return Err("Test capture requires STUDIO_TEST_CAPTURE=1 and an exact title beginning Recording Studio Synthetic Fixture.".into());
            }
            let source = platform::sources()?
                .into_iter()
                .find(|s| s.kind == "window" && s.name == title)
                .ok_or("Exact synthetic fixture window not found. No recording was started.")?;
            let root = std::env::temp_dir().join(format!(
                "recording-studio-window-test-{}",
                uuid::Uuid::new_v4()
            ));
            let store = storage::Store::new(root)?;
            let capture = capture::Capture::default();
            capture.start(
                &store,
                CaptureRequest {
                    source_id: source.id,
                    mode: "window".into(),
                    region: None,
                    microphone: None,
                    title: "SYNTHETIC · native window capture test".into(),
                },
            )?;
            std::thread::sleep(std::time::Duration::from_secs(2));
            let p = capture.stop(&store)?;
            let a = export::export(&store, &p.id, "h264", Arc::new(AtomicBool::new(false)))?;
            std::fs::write(
                store.root.join("test-result.json"),
                serde_json::to_vec_pretty(&a).map_err(|e| e.to_string())?,
            )
            .map_err(|e| e.to_string())?;
            println!("SYNTHETIC_WINDOW_CAPTURE_PASSED {}", a.path);
            Ok::<(), String>(())
        })();
        if let Err(e) = result {
            eprintln!("{e}");
            std::process::exit(1)
        }
        return;
    }
    if std::env::args().any(|a| a == "--self-test") {
        let result = (|| {
            let root = std::env::temp_dir().join(format!(
                "recording-studio-synthetic-{}",
                uuid::Uuid::new_v4()
            ));
            let s = storage::Store::new(root)?;
            let p = export::synthetic(&s)?;
            let a = export::export(&s, &p.id, "h264", Arc::new(AtomicBool::new(false)))?;
            println!("SYNTHETIC_SELF_TEST_PASSED {}", a.path);
            Ok::<(), String>(())
        })();
        if let Err(e) = result {
            eprintln!("{e}");
            std::process::exit(1)
        }
        return;
    }
    let result = tauri::Builder::default()
        .setup(|app| {
            let store =
                storage::Store::new(app.path().app_data_dir()?).map_err(std::io::Error::other)?;
            #[cfg(target_os = "macos")]
            platform::install_helper(&store.root).map_err(std::io::Error::other)?;
            app.manage(Studio {
                store,
                capture: Arc::new(capture::Capture::default()),
                exporting: Arc::new(AtomicBool::new(false)),
                cancel: Arc::new(AtomicBool::new(false)),
                transcribing: Arc::new(AtomicBool::new(false)),
            });
            tauri::WebviewWindowBuilder::new(
                app,
                "hud",
                tauri::WebviewUrl::App("index.html?hud=1".into()),
            )
            .title("Recording · Stop")
            .inner_size(310.0, 100.0)
            .position(20.0, 20.0)
            .always_on_top(true)
            .decorations(false)
            .resizable(false)
            .content_protected(true)
            .skip_taskbar(true)
            .visible(false)
            .build()?;
            let stop =
                tauri::menu::MenuItem::with_id(app, "stop", "Stop recording", true, None::<&str>)?;
            let show =
                tauri::menu::MenuItem::with_id(app, "show", "Open studio", true, None::<&str>)?;
            let quit =
                tauri::menu::MenuItem::with_id(app, "quit", "Quit studio", true, None::<&str>)?;
            let menu = tauri::menu::Menu::with_items(app, &[&show, &stop, &quit])?;
            let icon = tauri::image::Image::new_owned([34u8, 211, 238, 255].repeat(256), 16, 16);
            tauri::tray::TrayIconBuilder::new()
                .icon(icon)
                .tooltip("Local Recording Studio")
                .menu(&menu)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "stop" => {
                        let app = app.clone();
                        let state = app.state::<Studio>().inner().clone();
                        tauri::async_runtime::spawn(async move {
                            if let Err(e) = stop_impl(app.clone(), state).await {
                                let _ = app.emit("recording-error", e);
                            }
                        });
                    }
                    "show" => {
                        if let Some(w) = app.get_webview_window("main") {
                            let _ = w.show();
                            let _ = w.set_focus();
                        }
                    }
                    "quit" => {
                        let state = app.state::<Studio>();
                        let status = state.capture.status();
                        if status.project_id.is_none()
                            && !matches!(status.status.as_str(), "starting" | "stopping")
                            && !state.exporting.load(Ordering::SeqCst)
                            && !state.transcribing.load(Ordering::SeqCst)
                        {
                            app.exit(0);
                        } else {
                            if let Some(w) = app.get_webview_window("main") {
                                let _ = w.show();
                                let _ = w.set_focus();
                            }
                            let _ = app.emit(
                                "recording-error",
                                "Stop recording and finish or cancel active jobs before quitting.",
                            );
                        }
                    }
                    _ => {}
                })
                .build(app)?;
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                if window.label() == "hud" {
                    api.prevent_close();
                } else {
                    let state = window.state::<Studio>();
                    let status = state.capture.status();
                    if status.project_id.is_some()
                        || matches!(status.status.as_str(), "starting" | "stopping")
                        || state.exporting.load(Ordering::SeqCst)
                        || state.transcribing.load(Ordering::SeqCst)
                    {
                        api.prevent_close();
                        let _ = window.hide();
                    } else {
                        // A hidden HUD is still a window; explicitly exit when idle.
                        window.app_handle().exit(0);
                    }
                }
            }
        })
        .invoke_handler(tauri::generate_handler![
            get_capabilities,
            list_sources,
            list_microphones,
            list_projects,
            start_recording,
            stop_recording,
            recording_status,
            save_edits,
            export_project,
            cancel_export,
            transcribe_project,
            reveal_project,
            project_file_path
        ])
        .run(tauri::generate_context!());
    if let Err(e) = result {
        eprintln!("Studio could not start: {e}");
    }
}
