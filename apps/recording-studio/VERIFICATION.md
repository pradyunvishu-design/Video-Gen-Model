# Recording Studio verification

This is a first local desktop implementation, not a claim of Screen Studio feature parity.

## Verified on the Windows development machine (2026-09-20)

- TypeScript checking and Vite production build: passed.
- React interface/validation tests: 31 passed.
- Bootstrap/prerequisite tests: 3 passed.
- Chrome browser workflow: 2 passed. The capture boundary is mocked in these two tests; they are not evidence of native recording.
- Native Rust tests including the opt-in FFmpeg integration: 22 passed. Synthetic H.264 and WebM exports exercise zoom, callouts, audio, duration, exact 1920×1080 output, cancellation and original source preservation.
- Source-export safety tests: 4 passed. Desktop source/lock files are included; runtime builds, dependencies, media and secrets are excluded.
- Windows MSVC compile check: passed.
- Strict Clippy (`--all-targets -- -D warnings`) and debug executable build: passed.

Actual native UI/capture smoke-test results and final build checks are recorded below when complete. Native microphone and macOS permission flows are not verified by the synthetic tests.

Native visual testing caught an important distinction: hardware-accelerated Chrome windows produced black pixels through direct `gdigrab hwnd` capture even though the files decoded. The Windows window backend was changed to capture the desktop-composited pixels within the selected client rectangle, with visibility/occlusion/geometry guards. The smoke test now inspects actual fixture pixels before reporting success. Initial macOS CI compiled the Swift helper but exposed a missing generated PNG app icon; this is tracked as a build defect, not a passing Mac result.

## Exact local commands

Run from `apps/recording-studio` unless marked otherwise:

```powershell
npm.cmd run doctor
npm.cmd run test:bootstrap
npm.cmd test
npm.cmd run build
npm.cmd run test:e2e
$env:RUSTUP_TOOLCHAIN='stable-x86_64-pc-windows-msvc'
cargo check --manifest-path src-tauri/Cargo.toml
cargo fmt --manifest-path src-tauri/Cargo.toml --check
cargo test --manifest-path src-tauri/Cargo.toml --lib -- --include-ignored
cargo clippy --manifest-path src-tauri/Cargo.toml --all-targets -- -D warnings
cargo build --manifest-path src-tauri/Cargo.toml
```

Source-export tests, from the project root:

```powershell
& 'C:\Users\kanag\AppData\Local\Programs\Python\Python312\python.exe' -m pytest tests/test_source_export.py -q --basetemp='C:\Users\kanag\AppData\Local\Temp\studio-export-tests-20260920-a' -o cache_dir='C:\Users\kanag\AppData\Local\Temp\studio-pytest-cache-20260920'
```

The first exporter-test attempt encountered an existing locked pytest temp directory; a fresh dedicated temporary directory passed all four tests. No permissions were changed. Native rendering tests exposed a removed FFmpeg option; switching to current file-loaded filter arguments was re-tested with both codecs. Browser testing exposed an overly broad development file watcher; Rust build directories are now excluded.

## Manual native acceptance checklist

- Windows and macOS: screen/window/region; source moves/disappears; microphone off/on and permission denied.
- Start, observe advancing HUD timer, stop from HUD, repeat using tray Stop.
- Close main window during capture: recording stays stoppable, no orphan session.
- Screen/region capture: verify HUD is not burned into captured pixels. Windows asks for OS capture exclusion; this needs a pixel-level check on supported OS versions.
- Retina/multi-monitor scaling and region boundaries on macOS; mixed-DPI displays on Windows.
- Reopen application and verify library/edit persistence.
- Preview original and export; verify trim endpoints, cursor alignment, callout readability and complete sentences.
- Physical microphone intelligibility, audio/video sync and optional Whisper model accuracy.
- Interrupt export; verify source is unchanged and a new export succeeds.

## macOS and CI scope

The Swift ScreenCaptureKit implementation targets macOS 15+. The GitHub Actions matrix builds/tests Windows and macOS; workflow results must be checked separately. A build does not grant macOS privacy permissions or prove microphone/HUD behavior on a real Mac. Those remain required before declaring native Mac recording verified.

## Quality review

The UI uses local fonts, a neutral/green restrained palette, a stable video area, explicit original-versus-export preview labels, source-selection gating, pending/error/success states and recoverable preview failures. No fake transcript, media, capture status or completed export is used in production. Independent review prompted narrower media scope and validation of all stored preview/export paths. Third-party dependency code and generated runtime artifacts are not copied into GitHub source.
