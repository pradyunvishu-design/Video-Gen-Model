use std::path::{Path, PathBuf};
use std::process::{Command, Output};
pub fn command(exe: impl AsRef<std::ffi::OsStr>) -> Command {
    let c = Command::new(exe);
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        let mut c = c;
        c.creation_flags(0x08000000);
        c
    }
    #[cfg(not(windows))]
    {
        c
    }
}
pub fn tool(name: &str) -> PathBuf {
    let var = match name {
        "ffmpeg" => "FFMPEG_PATH",
        "ffprobe" => "FFPROBE_PATH",
        _ => "STUDIO_CAPTURE_HELPER",
    };
    std::env::var_os(var)
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(name))
}
pub fn available(name: &str) -> bool {
    command(tool(name))
        .arg("-version")
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false)
}
pub fn checked(output: Output, what: &str) -> Result<Output, String> {
    if output.status.success() {
        Ok(output)
    } else {
        let text = String::from_utf8_lossy(&output.stderr);
        let tail = text
            .lines()
            .rev()
            .take(8)
            .collect::<Vec<_>>()
            .into_iter()
            .rev()
            .collect::<Vec<_>>()
            .join("\n");
        Err(format!("{what} failed. {tail}"))
    }
}
pub fn probe(path: &Path) -> Result<(f64, u32, u32, bool), String> {
    let o = command(tool("ffprobe"))
        .args([
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
        ])
        .arg(path)
        .output()
        .map_err(|_| "ffprobe is missing. Set FFPROBE_PATH or add it to PATH.".to_string())?;
    let o = checked(o, "Media inspection")?;
    let v: serde_json::Value = serde_json::from_slice(&o.stdout).map_err(|e| e.to_string())?;
    let streams = v["streams"].as_array().ok_or("No media streams found.")?;
    let video = streams
        .iter()
        .find(|s| s["codec_type"] == "video")
        .ok_or("No video stream was captured.")?;
    let duration = v["format"]["duration"]
        .as_str()
        .and_then(|s| s.parse::<f64>().ok())
        .filter(|v| v.is_finite() && *v > 0.0)
        .ok_or("Recording has no playable duration.")?;
    Ok((
        duration,
        video["width"].as_u64().unwrap_or(0) as u32,
        video["height"].as_u64().unwrap_or(0) as u32,
        streams.iter().any(|s| s["codec_type"] == "audio"),
    ))
}
pub fn poster(source: &Path, output: &Path) -> Result<(), String> {
    let o = command(tool("ffmpeg"))
        .args(["-hide_banner", "-loglevel", "error", "-y", "-i"])
        .arg(source)
        .args(["-frames:v", "1", "-vf", "scale=960:-2"])
        .arg(output)
        .output()
        .map_err(|e| e.to_string())?;
    checked(o, "Poster generation").map(|_| ())
}
