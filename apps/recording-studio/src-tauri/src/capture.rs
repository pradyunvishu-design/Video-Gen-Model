use crate::{
    model::*,
    platform, process,
    storage::{path_string, Store},
};
use std::{
    io::Write,
    process::{Child, Stdio},
    sync::{
        atomic::{AtomicBool, AtomicU8, Ordering},
        Arc, Mutex,
    },
    time::{Duration, Instant},
};
pub struct Running {
    child: Child,
    input: Arc<Mutex<Option<std::process::ChildStdin>>>,
    id: String,
    title: String,
    path: std::path::PathBuf,
    started: Instant,
    stop_samples: Arc<AtomicBool>,
    #[cfg(windows)]
    samples: Arc<Mutex<Vec<CursorSample>>>,
    #[cfg(windows)]
    fault: Arc<Mutex<Option<String>>>,
}
#[derive(Default)]
pub struct Capture {
    active: Mutex<Option<Running>>,
    transition: AtomicU8,
    error: Mutex<Option<String>>,
    #[cfg(windows)]
    hud: Mutex<Option<isize>>,
}
struct Transition<'a>(&'a AtomicU8);
impl Drop for Transition<'_> {
    fn drop(&mut self) {
        self.0.store(0, Ordering::SeqCst)
    }
}
impl Capture {
    #[cfg(windows)]
    pub fn set_hud(&self, handle: Option<isize>) {
        if let Ok(mut hud) = self.hud.lock() {
            *hud = handle;
        }
    }
    pub fn status(&self) -> RecordingStatus {
        let mut error = self.error.lock().ok().and_then(|e| e.clone());
        if let Ok(mut guard) = self.active.lock() {
            if let Some(r) = guard.as_mut() {
                if let Ok(Some(_)) = r.child.try_wait() {
                    r.stop_samples.store(true, Ordering::Relaxed);
                    error=Some("Capture stopped unexpectedly. Click Stop to recover the partial recording; check capture.log in its project folder.".into());
                }
                #[cfg(windows)]
                if let Ok(fault) = r.fault.lock() {
                    if fault.is_some() {
                        error = fault.clone();
                    }
                }
                return RecordingStatus {
                    status: if error.is_some() {
                        "error"
                    } else {
                        "recording"
                    }
                    .into(),
                    project_id: Some(r.id.clone()),
                    elapsed_seconds: r.started.elapsed().as_secs_f64(),
                    error,
                };
            }
        }
        RecordingStatus {
            status: if self.transition.load(Ordering::SeqCst) == 1 {
                "starting"
            } else if self.transition.load(Ordering::SeqCst) == 2 {
                "stopping"
            } else if error.is_some() {
                "error"
            } else {
                "idle"
            }
            .into(),
            project_id: None,
            elapsed_seconds: 0.0,
            error,
        }
    }
    pub fn start(&self, store: &Store, request: CaptureRequest) -> Result<RecordingStatus, String> {
        if self
            .transition
            .compare_exchange(0, 1, Ordering::SeqCst, Ordering::SeqCst)
            .is_err()
        {
            return Err("Another recording operation is in progress.".into());
        }
        let _transition = Transition(&self.transition);
        if self
            .active
            .lock()
            .map_err(|_| "Capture state unavailable")?
            .is_some()
        {
            return Err("Stop the current recording first.".into());
        }
        if let Ok(mut e) = self.error.lock() {
            *e = None;
        }
        if !process::available("ffmpeg") || !process::available("ffprobe") {
            return Err(
                "Install local FFmpeg and ffprobe, or configure FFMPEG_PATH and FFPROBE_PATH."
                    .into(),
            );
        }
        validate_title(&request.title)?;
        let source = platform::sources()?
            .into_iter()
            .find(|s| s.id == request.source_id)
            .ok_or("Selected source disappeared. Refresh sources and select it again.")?;
        #[cfg(windows)]
        let mut source = source;
        if !["screen", "window", "region"].contains(&request.mode.as_str())
            || (request.mode == "window" && source.kind != "window")
            || (request.mode != "window" && source.kind != "screen")
        {
            return Err("Recording mode does not match the selected source.".into());
        }
        if let Some(mic) = &request.microphone {
            if !platform::microphones()?.contains(mic) {
                return Err(
                    "Microphone is unavailable. Refresh devices or record without audio.".into(),
                );
            }
        }
        #[cfg(windows)]
        let hud = *self.hud.lock().map_err(|_| "HUD state unavailable")?;
        #[cfg(windows)]
        if source.kind == "window" {
            platform::prepare_window(&mut source, hud)?;
        }
        if request.mode == "region" {
            let r = request.region.as_ref().ok_or("Select a region first.")?;
            validate_rect(r, source.width, source.height)?;
            #[cfg(windows)]
            {
                source.x += r.x;
                source.y += r.y;
                source.width = r.width;
                source.height = r.height;
            }
        }
        let id = uuid::Uuid::new_v4().to_string();
        let dir = store.dir(&id)?;
        std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
        let path = dir.join("source.mp4");
        std::fs::write(
            dir.join("capture-request.json"),
            serde_json::to_vec_pretty(&request).map_err(|e| e.to_string())?,
        )
        .map_err(|e| e.to_string())?;
        let mut cmd;
        #[cfg(windows)]
        {
            cmd = process::command(process::tool("ffmpeg"));
            cmd.args([
                "-hide_banner",
                "-loglevel",
                "warning",
                "-y",
                "-thread_queue_size",
                "512",
                "-f",
                "gdigrab",
                "-framerate",
                "30",
                "-draw_mouse",
                "1",
            ]);
            // Capture composed pixels only within the exact selected area. HWND BitBlt
            // can be black for GPU-backed applications such as Chrome.
            cmd.args(composited_input_args(&source));
            std::fs::write(
                dir.join("capture-area.json"),
                serde_json::to_vec_pretty(&source).map_err(|e| e.to_string())?,
            )
            .map_err(|e| e.to_string())?;
            if let Some(m) = &request.microphone {
                cmd.args([
                    "-thread_queue_size",
                    "512",
                    "-f",
                    "dshow",
                    "-i",
                    &format!("audio={m}"),
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "160k",
                ]);
            }
            cmd.args([
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "18",
                "-vf",
                "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                "-pix_fmt",
                "yuv420p",
                "-g",
                "60",
                "-movflags",
                "+frag_keyframe+empty_moov+default_base_moof",
            ])
            .arg(&path);
        }
        #[cfg(target_os = "macos")]
        {
            cmd = process::command(platform::helper());
            cmd.arg("record")
                .arg(dir.join("capture-request.json"))
                .arg(&path)
                .arg(dir.join("cursor.json"));
        }
        #[cfg(not(any(windows, target_os = "macos")))]
        {
            return Err("Capture requires Windows or macOS 15+.".into());
        }
        let log = std::fs::File::create(dir.join("capture.log")).map_err(|e| e.to_string())?;
        cmd.stdin(Stdio::piped()).stdout(Stdio::null()).stderr(log);
        #[cfg(windows)]
        let started = Instant::now();
        let mut child = cmd
            .spawn()
            .map_err(|e| format!("Could not start capture: {e}"))?;
        let input = Arc::new(Mutex::new(child.stdin.take()));
        std::thread::sleep(Duration::from_millis(700));
        if child.try_wait().map_err(|e| e.to_string())?.is_some() {
            return Err(format!("Capture could not start. Check permissions and whether the source is still visible. Details: {}",path_string(&dir.join("capture.log"))));
        }
        #[cfg(target_os = "macos")]
        {
            let deadline = Instant::now() + Duration::from_secs(30);
            while !dir.join("capture.ready").is_file() {
                if child.try_wait().map_err(|e| e.to_string())?.is_some() {
                    return Err("ScreenCaptureKit could not start. Check screen and microphone permissions; capture.log is retained.".into());
                }
                if Instant::now() > deadline {
                    let _ = child.kill();
                    let _ = child.wait();
                    return Err("ScreenCaptureKit permission/startup timed out. Grant screen and microphone permissions in System Settings, then try again.".into());
                }
                std::thread::sleep(Duration::from_millis(100));
            }
        }
        #[cfg(not(windows))]
        let started = Instant::now();
        let stop_samples = Arc::new(AtomicBool::new(false));
        #[cfg(windows)]
        let samples = Arc::new(Mutex::new(Vec::new()));
        #[cfg(windows)]
        let stop = stop_samples.clone();
        #[cfg(windows)]
        let data = samples.clone();
        #[cfg(windows)]
        let fault = Arc::new(Mutex::new(None));
        #[cfg(windows)]
        let capture_fault = fault.clone();
        #[cfg(windows)]
        let stop_input = input.clone();
        #[cfg(windows)]
        std::thread::spawn(move || {
            let _dpi = platform::DpiGuard::new();
            while !stop.load(Ordering::Relaxed) {
                if source.kind == "window" {
                    if let Err(message) = platform::window_capture_safe(&source, hud) {
                        if let Ok(mut fault) = capture_fault.lock() {
                            *fault = Some(message)
                        }
                        stop.store(true, Ordering::Relaxed);
                        quit_input(&stop_input);
                        break;
                    }
                }
                if let Some(s) = platform::cursor(started.elapsed().as_secs_f64(), &source) {
                    if let Ok(mut v) = data.lock() {
                        if v.len() < 864000 {
                            v.push(s)
                        }
                    }
                }
                std::thread::sleep(Duration::from_millis(50));
            }
        });
        *self
            .active
            .lock()
            .map_err(|_| "Capture state unavailable")? = Some(Running {
            child,
            input,
            id,
            title: if request.title.trim().is_empty() {
                "Untitled recording".into()
            } else {
                request.title.trim().into()
            },
            path,
            started,
            stop_samples,
            #[cfg(windows)]
            samples,
            #[cfg(windows)]
            fault,
        });
        Ok(self.status())
    }
    pub fn stop(&self, store: &Store) -> Result<Project, String> {
        if self
            .transition
            .compare_exchange(0, 2, Ordering::SeqCst, Ordering::SeqCst)
            .is_err()
        {
            return Err("Another recording operation is in progress.".into());
        }
        let _transition = Transition(&self.transition);
        let mut r = self
            .active
            .lock()
            .map_err(|_| "Capture state unavailable")?
            .take()
            .ok_or("No recording is running.")?;
        r.stop_samples.store(true, Ordering::Relaxed);
        quit_input(&r.input);
        let deadline = Instant::now() + Duration::from_secs(15);
        loop {
            if r.child.try_wait().map_err(|e| e.to_string())?.is_some() {
                break;
            }
            if Instant::now() > deadline {
                let _ = r.child.kill();
                let _ = r.child.wait();
                break;
            }
            std::thread::sleep(Duration::from_millis(100));
        }
        let dir = store.dir(&r.id)?;
        #[cfg(windows)]
        {
            if let Ok(fault) = r.fault.lock() {
                if let Some(message) = &*fault {
                    std::fs::write(dir.join("capture-warning.txt"), message)
                        .map_err(|e| e.to_string())?;
                }
            }
            let data = r
                .samples
                .lock()
                .map_err(|_| "Cursor metadata unavailable")?;
            std::fs::write(
                dir.join("cursor.json"),
                serde_json::to_vec(&*data).map_err(|e| e.to_string())?,
            )
            .map_err(|e| e.to_string())?;
        }
        let result = (|| {
            let (duration, width, height, has_audio) = process::probe(&r.path)?;
            let poster = dir.join("poster.jpg");
            let poster_path = process::poster(&r.path, &poster)
                .ok()
                .map(|_| path_string(&poster));
            let samples = std::fs::read(dir.join("cursor.json"))
                .ok()
                .and_then(|b| serde_json::from_slice::<Vec<CursorSample>>(&b).ok())
                .unwrap_or_default();
            let mut edits = EditPlan::initial(duration);
            edits.zoom_events = suggest_zooms(&samples, duration);
            let p = Project {
                id: r.id,
                title: r.title,
                created_at: chrono::Utc::now().to_rfc3339(),
                duration,
                width,
                height,
                has_audio,
                source_path: path_string(&r.path),
                poster_path,
                edits,
                exports: vec![],
            };
            store.save(&p)?;
            Ok(p)
        })();
        if let Err(e) = &result {
            if let Ok(mut err) = self.error.lock() {
                *err = Some(format!(
                    "Recording could not be finalized: {e}. Partial source retained at {}",
                    path_string(&r.path)
                ));
            }
        } else if let Ok(mut err) = self.error.lock() {
            *err = None;
        }
        result
    }
}
fn quit_input(input: &Arc<Mutex<Option<std::process::ChildStdin>>>) {
    if let Ok(mut slot) = input.lock() {
        if let Some(mut input) = slot.take() {
            let _ = input.write_all(b"q\n");
            let _ = input.flush();
        }
    }
}
#[cfg(windows)]
fn composited_input_args(source: &CaptureSource) -> Vec<String> {
    vec![
        "-offset_x".into(),
        source.x.to_string(),
        "-offset_y".into(),
        source.y.to_string(),
        "-video_size".into(),
        format!("{}x{}", source.width, source.height),
        "-i".into(),
        "desktop".into(),
    ]
}

#[cfg(test)]
mod tests {
    use super::*;
    #[cfg(windows)]
    #[test]
    fn window_capture_is_bounded_to_exact_composited_client_area() {
        let source = CaptureSource {
            id: "window:1234".into(),
            name: "selected".into(),
            kind: "window".into(),
            x: -1920,
            y: 80,
            width: 1280,
            height: 720,
        };
        let args = composited_input_args(&source);
        assert_eq!(
            args,
            vec![
                "-offset_x",
                "-1920",
                "-offset_y",
                "80",
                "-video_size",
                "1280x720",
                "-i",
                "desktop"
            ]
        );
        assert!(!args.iter().any(|a| a.contains("hwnd=")));
    }
    #[test]
    fn graceful_stop_input_can_be_repeated_without_a_child() {
        let input = Arc::new(Mutex::new(None));
        quit_input(&input);
        quit_input(&input);
        assert!(input.lock().unwrap().is_none());
    }
    #[test]
    fn idle_stop_is_safe_and_does_not_start_capture() {
        let t = tempfile::tempdir().unwrap();
        let store = Store::new(t.path().into()).unwrap();
        let capture = Capture::default();
        assert_eq!(capture.status().status, "idle");
        assert!(capture.stop(&store).unwrap_err().contains("No recording"));
        assert_eq!(capture.status().status, "idle");
        assert!(store.list().unwrap().is_empty());
    }
    #[test]
    fn busy_transition_rejects_duplicate_start_without_devices() {
        let t = tempfile::tempdir().unwrap();
        let store = Store::new(t.path().into()).unwrap();
        let capture = Capture::default();
        capture.transition.store(2, Ordering::SeqCst);
        let request = CaptureRequest {
            source_id: "unused".into(),
            mode: "screen".into(),
            region: None,
            microphone: None,
            title: "test".into(),
        };
        assert!(capture
            .start(&store, request)
            .unwrap_err()
            .contains("in progress"));
        assert_eq!(capture.status().status, "stopping");
        assert!(store.list().unwrap().is_empty());
    }
}
