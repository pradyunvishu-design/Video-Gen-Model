use serde::{Deserialize, Serialize};
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Rect {
    pub x: i32,
    pub y: i32,
    pub width: u32,
    pub height: u32,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CaptureSource {
    pub id: String,
    pub name: String,
    pub kind: String,
    pub x: i32,
    pub y: i32,
    pub width: u32,
    pub height: u32,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CaptureRequest {
    pub source_id: String,
    pub mode: String,
    pub region: Option<Rect>,
    pub microphone: Option<String>,
    pub title: String,
}
pub fn validate_title(title: &str) -> Result<(), String> {
    if title.chars().count() > 120 || title.contains('\0') {
        Err("Title must be at most 120 characters and contain no null character.".into())
    } else {
        Ok(())
    }
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ZoomEvent {
    pub start: f64,
    pub end: f64,
    pub x: f64,
    pub y: f64,
    pub scale: f64,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Callout {
    pub start: f64,
    pub end: f64,
    pub x: f64,
    pub y: f64,
    pub text: String,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct EditPlan {
    pub trim_start: f64,
    pub trim_end: f64,
    pub crop: Option<Rect>,
    pub padding: u32,
    pub background: String,
    pub zoom_events: Vec<ZoomEvent>,
    pub cursor_highlight: bool,
    pub callouts: Vec<Callout>,
    pub transcript: String,
}
impl EditPlan {
    pub fn initial(duration: f64) -> Self {
        Self {
            trim_start: 0.0,
            trim_end: duration,
            crop: None,
            padding: 32,
            background: "#111827".into(),
            zoom_events: vec![],
            cursor_highlight: true,
            callouts: vec![],
            transcript: String::new(),
        }
    }
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ExportArtifact {
    pub path: String,
    pub poster_path: String,
    pub summary_path: String,
    pub transcript_path: String,
    pub preset: String,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Project {
    pub id: String,
    pub title: String,
    pub created_at: String,
    pub duration: f64,
    pub width: u32,
    pub height: u32,
    pub has_audio: bool,
    pub source_path: String,
    pub poster_path: Option<String>,
    pub edits: EditPlan,
    pub exports: Vec<ExportArtifact>,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RecordingStatus {
    pub status: String,
    pub project_id: Option<String>,
    pub elapsed_seconds: f64,
    pub error: Option<String>,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CursorSample {
    pub time: f64,
    pub x: f64,
    pub y: f64,
    pub click: bool,
}
pub fn suggest_zooms(samples: &[CursorSample], duration: f64) -> Vec<ZoomEvent> {
    let mut events = Vec::new();
    let mut previous_down = false;
    let mut last = -10.0;
    for s in samples {
        let clicked = s.click && !previous_down;
        previous_down = s.click;
        if clicked
            && s.time.is_finite()
            && s.x.is_finite()
            && s.y.is_finite()
            && (0.0..=1.0).contains(&s.x)
            && (0.0..=1.0).contains(&s.y)
            && s.time - last >= 2.0
            && s.time >= 0.0
            && s.time < duration
            && events.len() < 24
        {
            let start = (s.time - 0.2).max(0.0);
            let end = (s.time + 1.4).min(duration);
            if end - start >= 0.3 {
                events.push(ZoomEvent {
                    start,
                    end,
                    x: s.x,
                    y: s.y,
                    scale: 1.35,
                });
                last = s.time;
            }
        }
    }
    events
}
pub fn validate_edits(e: &EditPlan, p: &Project) -> Result<(), String> {
    if !e.trim_start.is_finite()
        || !e.trim_end.is_finite()
        || e.trim_start < 0.0
        || e.trim_end > p.duration + 0.05
        || e.trim_end - e.trim_start < 0.05
    {
        return Err("Trim must be within the source and at least 0.05 seconds long.".into());
    }
    if e.padding > 400 {
        return Err("Padding must be at most 400 pixels.".into());
    }
    if e.background.len() != 7
        || !e.background.starts_with('#')
        || !e.background[1..].bytes().all(|b| b.is_ascii_hexdigit())
    {
        return Err("Background must be a hex color.".into());
    }
    if let Some(c) = &e.crop {
        validate_rect(c, p.width, p.height)?;
    }
    if e.zoom_events.len() > 24 || e.callouts.len() > 32 || e.transcript.len() > 200_000 {
        return Err("Too many edits or transcript is too long.".into());
    }
    let time = |s: f64, end: f64| {
        s.is_finite() && end.is_finite() && s >= 0.0 && end > s && end <= p.duration + 0.05
    };
    let point = |x: f64, y: f64| {
        x.is_finite() && y.is_finite() && (0.0..=1.0).contains(&x) && (0.0..=1.0).contains(&y)
    };
    for z in &e.zoom_events {
        if !time(z.start, z.end)
            || !point(z.x, z.y)
            || !z.scale.is_finite()
            || !(1.0..=3.0).contains(&z.scale)
        {
            return Err("Invalid zoom; use source times, normalized points, and scale 1–3.".into());
        }
    }
    for c in &e.callouts {
        if !time(c.start, c.end)
            || !point(c.x, c.y)
            || c.text.trim().is_empty()
            || c.text.chars().count() > 160
            || c.text.contains('\0')
        {
            return Err("Invalid callout; use source times and at most 160 characters.".into());
        }
    }
    Ok(())
}
pub fn validate_rect(r: &Rect, w: u32, h: u32) -> Result<(), String> {
    if r.x < 0
        || r.y < 0
        || r.width < 16
        || r.height < 16
        || r.x as u64 + r.width as u64 > w as u64
        || r.y as u64 + r.height as u64 > h as u64
    {
        Err("Region must fit inside the selected source and be at least 16×16.".into())
    } else {
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn project() -> Project {
        Project {
            id: uuid::Uuid::new_v4().to_string(),
            title: "test".into(),
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
    fn trim_rejects_nonfinite_negative_reversed_and_outside() {
        let p = project();
        for (start, end) in [
            (f64::NAN, 1.0),
            (0.0, f64::INFINITY),
            (-0.1, 2.0),
            (4.0, 3.0),
            (0.0, 10.2),
            (0.0, 0.01),
        ] {
            let mut e = p.edits.clone();
            e.trim_start = start;
            e.trim_end = end;
            assert!(validate_edits(&e, &p).is_err(), "{start}..{end}")
        }
        assert!(validate_edits(&p.edits, &p).is_ok());
    }
    #[test]
    fn crop_rejects_overflow_negative_small_and_outside() {
        for r in [
            Rect {
                x: -1,
                y: 0,
                width: 50,
                height: 50,
            },
            Rect {
                x: 0,
                y: 0,
                width: 15,
                height: 50,
            },
            Rect {
                x: i32::MAX,
                y: 0,
                width: u32::MAX,
                height: 50,
            },
            Rect {
                x: 1200,
                y: 0,
                width: 100,
                height: 50,
            },
        ] {
            assert!(validate_rect(&r, 1280, 720).is_err())
        }
        assert!(validate_rect(
            &Rect {
                x: 0,
                y: 0,
                width: 1280,
                height: 720
            },
            1280,
            720
        )
        .is_ok());
    }
    #[test]
    fn padding_color_and_collection_limits() {
        let p = project();
        let mut e = p.edits.clone();
        e.padding = 401;
        assert!(validate_edits(&e, &p).is_err());
        for c in ["red", "#1234567", "#gggggg", "#🙂a"] {
            e = p.edits.clone();
            e.background = c.into();
            assert!(validate_edits(&e, &p).is_err())
        }
        e = p.edits.clone();
        e.transcript = "x".repeat(200001);
        assert!(validate_edits(&e, &p).is_err());
    }
    #[test]
    fn zoom_and_callout_boundaries() {
        let p = project();
        let good = ZoomEvent {
            start: 0.0,
            end: 10.0,
            x: 0.5,
            y: 0.5,
            scale: 1.35,
        };
        for z in [
            ZoomEvent {
                scale: 3.1,
                ..good.clone()
            },
            ZoomEvent {
                x: f64::NAN,
                ..good.clone()
            },
            ZoomEvent {
                y: -0.1,
                ..good.clone()
            },
            ZoomEvent {
                end: 11.0,
                ..good.clone()
            },
            ZoomEvent {
                scale: f64::INFINITY,
                ..good.clone()
            },
        ] {
            let mut e = p.edits.clone();
            e.zoom_events = vec![z];
            assert!(validate_edits(&e, &p).is_err())
        }
        let mut e = p.edits.clone();
        e.zoom_events = vec![good; 25];
        assert!(validate_edits(&e, &p).is_err());
        e = p.edits.clone();
        for text in [String::new(), "x".repeat(161), "null\0text".into()] {
            e.callouts = vec![Callout {
                start: 0.0,
                end: 1.0,
                x: 0.5,
                y: 0.5,
                text,
            }];
            assert!(validate_edits(&e, &p).is_err())
        }
    }
    #[test]
    fn titles_are_bounded_but_allow_unicode() {
        assert!(validate_title(&"x".repeat(121)).is_err());
        assert!(validate_title("a\0b").is_err());
        assert!(validate_title("日本語 title").is_ok());
    }
    #[test]
    fn zoom_suggestions_ignore_offscreen_holds_and_limit_duration() {
        let samples = vec![
            CursorSample {
                time: 0.1,
                x: -1.0,
                y: 0.5,
                click: true,
            },
            CursorSample {
                time: 0.2,
                x: 0.5,
                y: 0.5,
                click: false,
            },
            CursorSample {
                time: 0.3,
                x: 0.5,
                y: 0.5,
                click: true,
            },
            CursorSample {
                time: 0.4,
                x: 0.5,
                y: 0.5,
                click: true,
            },
            CursorSample {
                time: 0.5,
                x: 0.5,
                y: 0.5,
                click: false,
            },
            CursorSample {
                time: 0.6,
                x: 0.5,
                y: 0.5,
                click: true,
            },
            CursorSample {
                time: 2.7,
                x: 0.5,
                y: 0.5,
                click: false,
            },
            CursorSample {
                time: 2.8,
                x: 0.5,
                y: 0.5,
                click: true,
            },
        ];
        let z = suggest_zooms(&samples, 3.0);
        assert_eq!(z.len(), 2);
        assert!(z[1].start - z[0].start >= 2.0);
        assert!(z.iter().all(|z| z.start >= 0.0 && z.end <= 3.0));
        assert!(suggest_zooms(&[], 3.0).is_empty());
    }
}
