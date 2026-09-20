use crate::{
    model::*,
    process,
    storage::{path_string, Store},
};
use std::{
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc,
    },
    time::Duration,
};

fn even(v: u32) -> u32 {
    v / 2 * 2
}
fn event_enable(start: f64, end: f64, trim: f64) -> String {
    format!("between(t,{:.4},{:.4})", start - trim, end - trim)
}
pub fn filters(p: &Project, samples: &[CursorSample]) -> String {
    let e = &p.edits;
    let c = e.crop.clone().unwrap_or(Rect {
        x: 0,
        y: 0,
        width: p.width,
        height: p.height,
    });
    let mut f = vec!["setpts=PTS-STARTPTS".to_string(), "fps=30".to_string()];
    // Click markers are transformed with the source, keeping them aligned through crop and zoom.
    if e.cursor_highlight {
        let mut was_down = false;
        for s in samples {
            let click = s.click && !was_down;
            was_down = s.click;
            if click && s.time >= e.trim_start && s.time < e.trim_end {
                let x = (s.x * p.width as f64).round() as i32 - 14;
                let y = (s.y * p.height as f64).round() as i32 - 14;
                f.push(format!(
                    "drawbox=x={x}:y={y}:w=28:h=28:color=0x67e8f9@0.85:t=3:enable='{}'",
                    event_enable(s.time, (s.time + 0.42).min(e.trim_end), e.trim_start)
                ))
            }
        }
    }
    f.push(format!(
        "crop={}:{}:{}:{}",
        even(c.width),
        even(c.height),
        c.x,
        c.y
    ));
    if !e.zoom_events.is_empty() {
        let mut zoom = "1".to_string();
        let mut px = "iw/2".to_string();
        let mut py = "ih/2".to_string();
        for z in e.zoom_events.iter().rev() {
            let s = z.start - e.trim_start;
            let end = z.end - e.trim_start;
            let ramp = ((end - s) / 3.0).min(0.28);
            let cond = format!("between(on/30,{s:.4},{end:.4})");
            let phase =
                format!("max(0,min(1,min((on/30-{s:.4})/{ramp:.4},({end:.4}-on/30)/{ramp:.4})))");
            let ease = format!("(0.5-0.5*cos(PI*({phase})))");
            zoom = format!("if({cond},1+{:.4}*({ease}),{zoom})", z.scale - 1.0);
            let x = (z.x * p.width as f64 - c.x as f64).clamp(0.0, c.width as f64);
            let y = (z.y * p.height as f64 - c.y as f64).clamp(0.0, c.height as f64);
            px = format!("if({cond},{x:.4},{px})");
            py = format!("if({cond},{y:.4},{py})");
        }
        f.push(format!("zoompan=z='{zoom}':x='max(0,min(iw-iw/zoom,({px})-iw/zoom/2))':y='max(0,min(ih-ih/zoom,({py})-ih/zoom/2))':d=1:s={}x{}:fps=30",even(c.width),even(c.height)));
    }
    let inner_w = 1920 - e.padding * 2;
    let inner_h = 1080 - e.padding * 2;
    f.push(format!("scale={inner_w}:{inner_h}:force_original_aspect_ratio=decrease:force_divisible_by=2,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x{},setsar=1",&e.background[1..]));
    for (i, c) in e.callouts.iter().enumerate() {
        f.push(format!("drawtext=textfile=callout-{i}.txt:expansion=none:fontcolor=white:fontsize=38:box=1:boxcolor=black@0.72:boxborderw=16:x='max(18,min(w-tw-18,{:.4}*w-tw/2))':y='max(18,min(h-th-18,{:.4}*h))':enable='{}'",c.x,c.y,event_enable(c.start,c.end,e.trim_start)))
    }
    f.push("format=yuv420p".into());
    f.join(",")
}
pub fn export(
    store: &Store,
    project_id: &str,
    preset: &str,
    cancel: Arc<AtomicBool>,
) -> Result<ExportArtifact, String> {
    if !["h264", "webm"].contains(&preset) {
        return Err("Choose H.264 or WebM.".into());
    }
    let p = store.get(project_id)?;
    validate_edits(&p.edits, &p)?;
    let source = store.trusted_source(&p)?;
    let folder = store
        .dir(project_id)?
        .join("exports")
        .join(uuid::Uuid::new_v4().to_string());
    std::fs::create_dir_all(&folder).map_err(|e| e.to_string())?;
    let samples = std::fs::read(store.dir(project_id)?.join("cursor.json"))
        .ok()
        .and_then(|b| serde_json::from_slice::<Vec<CursorSample>>(&b).ok())
        .unwrap_or_default();
    let filter = filters(&p, &samples);
    std::fs::write(folder.join("filters.txt"), filter).map_err(|e| e.to_string())?;
    for (i, c) in p.edits.callouts.iter().enumerate() {
        std::fs::write(folder.join(format!("callout-{i}.txt")), &c.text)
            .map_err(|e| e.to_string())?;
    }
    let ext = if preset == "h264" { "mp4" } else { "webm" };
    let partial = folder.join(format!("video.partial.{ext}"));
    let output = folder.join(format!("video.{ext}"));
    let mut cmd = process::command(process::tool("ffmpeg"));
    cmd.current_dir(&folder)
        .args([
            "-hide_banner",
            "-loglevel",
            "warning",
            "-y",
            "-ss",
            &format!("{:.6}", p.edits.trim_start),
            "-i",
        ])
        .arg(&source)
        .args([
            "-t",
            &format!("{:.6}", p.edits.trim_end - p.edits.trim_start),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-/filter:v",
            "filters.txt",
            "-r",
            "30",
        ]);
    if preset == "h264" {
        cmd.args([
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-movflags",
            "+faststart",
        ]);
    } else {
        cmd.args([
            "-c:v",
            "libvpx-vp9",
            "-deadline",
            "realtime",
            "-cpu-used",
            "6",
            "-crf",
            "32",
            "-b:v",
            "0",
            "-c:a",
            "libopus",
            "-b:a",
            "128k",
        ]);
    }
    let log = std::fs::File::create(folder.join("export.log")).map_err(|e| e.to_string())?;
    cmd.arg(&partial)
        .stdin(std::process::Stdio::null())
        .stdout(std::process::Stdio::null())
        .stderr(log);
    let mut child = cmd
        .spawn()
        .map_err(|_| "FFmpeg unavailable. Set FFMPEG_PATH or add FFmpeg to PATH.".to_string())?;
    loop {
        if cancel.load(Ordering::Relaxed) {
            let _ = child.kill();
            let _ = child.wait();
            return Err("Export cancelled. Source and edit plan are unchanged; partial output is retained in the project folder.".into());
        }
        if let Some(status) = child.try_wait().map_err(|e| e.to_string())? {
            if !status.success() {
                let log = std::fs::read_to_string(folder.join("export.log")).unwrap_or_default();
                let tail = log
                    .lines()
                    .rev()
                    .take(8)
                    .collect::<Vec<_>>()
                    .into_iter()
                    .rev()
                    .collect::<Vec<_>>()
                    .join("\n");
                return Err(format!(
                    "Export failed. Your source is safe. Details: {}\n{tail}",
                    path_string(&folder.join("export.log"))
                ));
            }
            break;
        }
        std::thread::sleep(Duration::from_millis(100));
    }
    let (_, w, h, _) = process::probe(&partial)?;
    if w != 1920 || h != 1080 {
        return Err("Export validation failed: expected 1920×1080.".into());
    }
    std::fs::rename(&partial, &output).map_err(|e| e.to_string())?;
    let poster = folder.join("poster.jpg");
    process::poster(&output, &poster)?;
    let transcript = folder.join("transcript.txt");
    std::fs::write(&transcript, &p.edits.transcript).map_err(|e| e.to_string())?;
    let summary = folder.join("summary.md");
    let excerpt = p
        .edits
        .transcript
        .split_terminator(['.', '!', '?'])
        .filter(|s| !s.trim().is_empty())
        .take(3)
        .map(|s| format!("{}.", s.trim()))
        .collect::<Vec<_>>()
        .join(" ");
    let summary_text = if excerpt.is_empty() {
        "No transcript supplied. Add a transcript in the editor and export again.".into()
    } else {
        format!("Transcript excerpt (local extractive summary, not AI-generated):\n\n{excerpt}")
    };
    std::fs::write(
        &summary,
        format!(
            "# {}\n\nDuration: {:.1} seconds. Format: {}. Resolution: 1920×1080.\n\n{}\n",
            p.title,
            p.edits.trim_end - p.edits.trim_start,
            preset,
            summary_text
        ),
    )
    .map_err(|e| e.to_string())?;
    let a = ExportArtifact {
        path: path_string(&output),
        poster_path: path_string(&poster),
        summary_path: path_string(&summary),
        transcript_path: path_string(&transcript),
        preset: preset.into(),
    };
    // Reload to preserve edits saved during export; artifact records the frozen plan used above.
    std::fs::write(
        folder.join("edit-plan.json"),
        serde_json::to_vec_pretty(&p.edits).map_err(|e| e.to_string())?,
    )
    .map_err(|e| e.to_string())?;
    store.modify(project_id, |current| {
        current.exports.push(a.clone());
        Ok(())
    })?;
    Ok(a)
}

pub fn synthetic(store: &Store) -> Result<Project, String> {
    let id = uuid::Uuid::new_v4().to_string();
    let dir = store.dir(&id)?;
    std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    let source = dir.join("source.mkv");
    let o = process::command(process::tool("ffmpeg"))
        .args([
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=640x360:rate=30",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000",
            "-t",
            "2",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-c:a",
            "aac",
        ])
        .arg(&source)
        .output()
        .map_err(|e| e.to_string())?;
    process::checked(o, "Synthetic fixture")?;
    let (duration, width, height, has_audio) = process::probe(&source)?;
    let p = Project {
        id,
        title: "SYNTHETIC · automated fixture (not a desktop recording)".into(),
        created_at: chrono::Utc::now().to_rfc3339(),
        duration,
        width,
        height,
        has_audio,
        source_path: path_string(&source),
        poster_path: None,
        edits: EditPlan::initial(duration),
        exports: vec![],
    };
    store.save(&p)?;
    Ok(p)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::Path;
    fn fixture() -> Project {
        Project {
            id: uuid::Uuid::new_v4().to_string(),
            title: "fixture".into(),
            created_at: String::new(),
            duration: 10.0,
            width: 1280,
            height: 720,
            has_audio: false,
            source_path: String::new(),
            poster_path: None,
            edits: EditPlan::initial(10.0),
            exports: vec![],
        }
    }
    #[test]
    fn edit_validation_rejects_bad_values() {
        let p = fixture();
        let mut e = p.edits.clone();
        e.trim_start = f64::NAN;
        assert!(validate_edits(&e, &p).is_err());
        e = p.edits.clone();
        e.background = "#;evil!".into();
        assert!(validate_edits(&e, &p).is_err());
        e = p.edits.clone();
        e.crop = Some(Rect {
            x: -1,
            y: 0,
            width: 100,
            height: 100,
        });
        assert!(validate_edits(&e, &p).is_err());
    }
    #[test]
    fn filters_have_fixed_output_and_no_injected_text() {
        let mut p = fixture();
        p.edits.callouts.push(Callout {
            start: 0.0,
            end: 1.0,
            x: 0.5,
            y: 0.5,
            text: "'; movie=secret".into(),
        });
        let f = filters(&p, &[]);
        assert!(f.contains("pad=1920:1080"));
        assert!(!f.contains("secret"));
        assert!(f.contains("expansion=none"));
        assert_eq!(f, filters(&p, &[]));
    }
    #[test]
    fn sqlite_roundtrip_and_path_guard() {
        let t = tempfile::tempdir().unwrap();
        let s = Store::new(t.path().into()).unwrap();
        let mut p = fixture();
        p.source_path = path_string(&s.dir(&p.id).unwrap().join("source.mp4"));
        s.save(&p).unwrap();
        assert_eq!(s.get(&p.id).unwrap().id, p.id);
        assert_eq!(s.list().unwrap().len(), 1);
        assert!(s.dir("../outside").is_err());
        assert!(s.trusted_source(&p).is_err());
    }
    #[test]
    fn zoom_suggestions_are_click_edges_and_spaced() {
        let samples = (0..10)
            .map(|i| CursorSample {
                time: i as f64 / 5.0,
                x: 0.5,
                y: 0.5,
                click: true,
            })
            .collect::<Vec<_>>();
        let z = suggest_zooms(&samples, 2.0);
        assert_eq!(z.len(), 1);
        assert_eq!(z[0].scale, 1.35);
        assert!(z[0].end <= 2.0);
    }
    #[test]
    #[ignore = "requires local FFmpeg; synthetic media only"]
    fn synthetic_export_end_to_end() {
        let t = tempfile::tempdir().unwrap();
        let s = Store::new(t.path().into()).unwrap();
        let mut p = synthetic(&s).unwrap();
        let before = std::fs::read(&p.source_path).unwrap();
        p.edits.callouts.push(Callout {
            start: 0.2,
            end: 1.5,
            x: 0.5,
            y: 0.2,
            text: "Synthetic QA".into(),
        });
        p.edits.zoom_events.push(ZoomEvent {
            start: 0.1,
            end: 1.7,
            x: 0.4,
            y: 0.4,
            scale: 1.4,
        });
        p.edits.transcript = "A synthetic test. No desktop capture occurred.".into();
        s.save(&p).unwrap();
        for preset in ["h264", "webm"] {
            let a = export(&s, &p.id, preset, Arc::new(AtomicBool::new(false))).unwrap();
            let (d, w, h, audio) = process::probe(Path::new(&a.path)).unwrap();
            assert_eq!((w, h), (1920, 1080));
            assert!((d - (p.edits.trim_end - p.edits.trim_start)).abs() < 0.15);
            assert!(audio);
            assert!(Path::new(&a.poster_path).is_file());
        }
        let cancelled = export(&s, &p.id, "h264", Arc::new(AtomicBool::new(true)));
        assert!(cancelled.unwrap_err().contains("cancelled"));
        assert_eq!(s.get(&p.id).unwrap().exports.len(), 2);
        assert_eq!(before, std::fs::read(&p.source_path).unwrap());
    }
}
