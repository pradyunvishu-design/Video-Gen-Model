# Local Recording Studio

A local-first recording and editing workspace alongside the existing video pipeline. Built with **Tauri 2, React, TypeScript, Rust, FFmpeg and SQLite**. No accounts, uploads, telemetry or hosted control plane.

## Start locally

From this directory, after installing the prerequisites below, run:

```sh
npm run dev
```

The bootstrap checks tools, installs the locked JavaScript dependencies if missing, and starts the native app. The first Rust build takes several minutes. A browser-only preview cannot capture or open your recording library; use the desktop window.

### Windows prerequisites

- Windows 10/11 with Microsoft Edge WebView2 Runtime.
- Node.js 22.16+ (24 LTS recommended).
- Rust through rustup with `stable-x86_64-pc-windows-msvc` installed.
- Visual Studio Build Tools, **Desktop development with C++**, and Windows SDK.
- FFmpeg and FFprobe on PATH, including `gdigrab`, `dshow`, `libx264`, `libvpx-vp9` and `drawtext` support.

The bootstrap chooses MSVC only for its child processes; it does not change your global Rust toolchain. If microphone access is blocked, enable desktop app microphone access in Windows Privacy settings.

### macOS prerequisites

- **macOS 15 or newer**, Apple Silicon or Intel.
- Node.js 22.16+, Rust, and Xcode 16+ command-line tools with the macOS 15 SDK.
- FFmpeg/FFprobe with H.264, VP9 and drawtext support (`brew install ffmpeg` if you use Homebrew).
- Grant **Screen & System Audio Recording** permission to the recording helper/app when prompted. Microphone permission is needed only if you select a microphone. System audio remains disabled.

Cargo compiles the native Swift ScreenCaptureKit helper and embeds it in the app. The helper is installed in the app-owned local data directory at startup. This is a personal development build, not a signed/notarized distribution. Do not bypass organizational application-control rules.

Apple's permission dialogs and physical microphone/screen capture must be validated on a real Mac. A successful CI build alone is not that validation.

## Record, edit, export

1. Name your recording. Choose a screen, window or numeric screen region explicitly.
2. Leave the microphone off or select an available device. Close private tabs/notifications before starting.
3. Start recording. A separate always-on-top timer provides Stop; the tray menu also provides Stop.
4. After stopping, select the saved recording. Set trim, crop, padding, zoom events, cursor-click highlights and text callouts. Times refer to the original recording. Changes are saved separately from source media.
5. Save edits, then export H.264 MP4 or VP9 WebM. Exports are exactly 1920×1080 at 30 fps. Source aspect ratio is preserved within the padded frame.
6. Use **Copy file path** or **Open folder**. The export folder also contains a poster, transcript, Markdown summary, frozen edit plan and local render log.

The editor shows the original capture until an export is available; it is not a live WYSIWYG effects preview. Window capture on Windows requires the target to remain visible/unminimized; protected content can be black. Source recordings are immutable. Repeated exports create separate folders.

## Optional local transcription

Copy `.env.example` to `.env` and supply absolute paths to a local [whisper.cpp](https://github.com/ggml-org/whisper.cpp) CLI and model:

```dotenv
WHISPER_CLI_PATH=/absolute/path/to/whisper-cli
WHISPER_MODEL_PATH=/absolute/path/to/ggml-base.bin
```

On Windows, forward slashes in absolute paths are supported. No model or external executable is downloaded automatically. In the editor, choose **Generate transcript locally**. The app converts audio locally and runs Whisper locally; transcription is optional, and manual text is supported. Missing tools/models produce an actionable error. The Markdown summary is explicitly labeled as a short extract of the transcript, not an AI-generated summary. Empty transcripts are disclosed, never fabricated.

Credentials are unnecessary. `.env` is ignored by Git. Never put secrets in `VITE_*` variables because those are browser-visible. Optional FFmpeg/FFprobe executable paths can also be set in `.env`.

## Architecture

```text
React editor --typed Tauri commands--> Rust coordinator
                                       |-- SQLite project/edit records
                                       |-- Windows FFmpeg gdigrab + DirectShow microphone
                                       |-- macOS Swift ScreenCaptureKit helper
                                       |-- cursor samples / non-destructive edit plan
                                       `-- FFmpeg export + local sidecars
```

- `src/`: React interface, validation and UI tests.
- `src-tauri/src/`: commands, recording lifecycle, storage, render filters and optional transcription.
- `src-tauri/native/macos/`: ScreenCaptureKit source and permission metadata.
- `CONTRACT.md`: shared command and document shapes.
- `scripts/dev.mjs`: local prerequisite/bootstrap command.
- `e2e/`: real-browser UI workflow with a mocked desktop boundary, not native-capture proof.

Commands use argument arrays rather than shell interpolation. Project folders use UUIDs, not user-supplied titles. Media is served only from app-owned data. Export cancellation does not alter sources; partial files and logs remain available for diagnosis.

## Local data and backup

The exact location appears at the bottom of the sidebar. Typical locations:

- Windows: `%APPDATA%/local.magichour.recording-studio`
- macOS: `~/Library/Application Support/local.magichour.recording-studio`

The folder contains `studio.sqlite3` (including SQLite WAL sidecars while open), `projects/<uuid>/source.*`, metadata, cursor samples, posters and versioned exports. macOS also stores the embedded helper under `native/`.

To back up, stop recording/exporting, close the app, and copy the **whole data directory**, not just the database. Restore to the same location on the same machine. Cross-machine relocation is not yet a migration feature because records contain absolute media paths. Never delete originals to clean up exports. Nothing is uploaded automatically.

## Tests and builds

```sh
npm run doctor
npm run test:bootstrap
npm test
npm run build
npm run test:e2e
cargo fmt --manifest-path src-tauri/Cargo.toml --check
cargo test --manifest-path src-tauri/Cargo.toml --locked
cargo test --manifest-path src-tauri/Cargo.toml --locked synthetic_export_end_to_end -- --ignored --nocapture
cargo clippy --manifest-path src-tauri/Cargo.toml --locked -- -D warnings
npm run desktop:build
```

For direct Cargo commands on Windows, set `RUSTUP_TOOLCHAIN=stable-x86_64-pc-windows-msvc` in the current terminal first. `npm run dev` and `desktop:build` handle this automatically. Browser tests default to installed Chrome; use `STUDIO_TEST_BROWSER=chromium` after installing Playwright Chromium to use that engine.

The synthetic export test generates its own video/audio, exercises edits and both codecs, checks 1080p output/sidecars, and verifies original source bytes are unchanged. It does **not** record a user's desktop. The GitHub workflow builds/tests on Windows and macOS; native permission, tray and real microphone tests remain separate from CI.

## Deliberate boundaries

- No public sharing, cloud workers, billing, analytics, accounts, SSO or workspaces.
- No AI voice cloning or paid provider requests in the recorder.
- No automatic integration into episode production yet: export a clip and use its path in the existing pipeline.
- No system audio capture, timeline drag editor, live rendered effects preview or signed installers in this first version.

See `VERIFICATION.md` for measured results and remaining platform checks. General platform requirements: [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/), [FFmpeg capture devices](https://ffmpeg.org/ffmpeg-devices.html), [Apple ScreenCaptureKit](https://developer.apple.com/documentation/screencapturekit).
