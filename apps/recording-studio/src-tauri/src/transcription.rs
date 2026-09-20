//! Optional, completely local whisper.cpp integration. Never uploads microphone audio.
use crate::{model::Project, process, storage::Store};
use std::{
    path::PathBuf,
    process::Stdio,
    time::{Duration, Instant},
};

fn configured(name: &str) -> Result<PathBuf, String> {
    let path = std::env::var_os(name).filter(|s| !s.is_empty()).map(PathBuf::from)
        .ok_or_else(|| format!("Local transcription is not configured. Set {name} in .env. You can also type a transcript in the editor."))?;
    if !path.is_absolute() || !path.is_file() {
        return Err(format!(
            "{name} must point to an existing absolute file path."
        ));
    }
    Ok(path)
}

pub fn transcribe(store: &Store, id: &str) -> Result<Project, String> {
    let project = store.get(id)?;
    if !project.has_audio {
        return Err("This recording has no microphone audio to transcribe.".into());
    }
    let cli = configured("WHISPER_CLI_PATH")?;
    let model = configured("WHISPER_MODEL_PATH")?;
    let source = store.trusted_source(&project)?;
    let folder = store
        .dir(id)?
        .join("transcripts")
        .join(uuid::Uuid::new_v4().to_string());
    std::fs::create_dir_all(&folder).map_err(|e| e.to_string())?;
    let wav = folder.join("audio.wav");
    let audio = process::command(process::tool("ffmpeg"))
        .args(["-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i"])
        .arg(source)
        .args(["-vn", "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le"])
        .arg(&wav)
        .output()
        .map_err(|e| e.to_string())?;
    process::checked(audio, "Local audio conversion")?;
    let log = std::fs::File::create(folder.join("transcription.log")).map_err(|e| e.to_string())?;
    let prefix = folder.join("transcript");
    let mut child = process::command(cli)
        .arg("-m")
        .arg(model)
        .arg("-f")
        .arg(&wav)
        .args(["-l", "auto", "-otxt", "-of"])
        .arg(&prefix)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(log)
        .spawn()
        .map_err(|e| format!("Could not start local Whisper: {e}"))?;
    let deadline = Instant::now() + Duration::from_secs(1800);
    loop {
        if let Some(status) = child.try_wait().map_err(|e| e.to_string())? {
            if !status.success() {
                return Err("Local transcription failed. Inspect transcription.log in the project folder; the recording is unchanged.".into());
            }
            break;
        }
        if Instant::now() >= deadline {
            let _ = child.kill();
            let _ = child.wait();
            return Err(
                "Local transcription timed out after 30 minutes. Your recording is unchanged."
                    .into(),
            );
        }
        std::thread::sleep(Duration::from_millis(200));
    }
    let text = std::fs::read_to_string(prefix.with_extension("txt"))
        .map_err(|_| "Whisper returned no transcript file.")?;
    if text.trim().is_empty() || text.len() > 200_000 {
        return Err(
            "Transcript was empty or too large. Review microphone audio and try again.".into(),
        );
    }
    // Do not replace newer edits while a slow transcription is running.
    store.modify(id, |current| {
        if current.edits.transcript != project.edits.transcript {
            return Err("Transcript was edited while Whisper was working. Your edits were preserved; generated text is in the project's transcripts folder.".into());
        }
        current.edits.transcript = text.trim().to_owned();
        Ok(())
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn missing_configuration_is_actionable() {
        let error = configured("RECORDING_STUDIO_TEST_NONEXISTENT_SETTING").unwrap_err();
        assert!(error.contains("not configured"));
        assert!(error.contains("type a transcript"));
    }
}
