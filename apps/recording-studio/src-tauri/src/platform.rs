#[cfg(windows)]
use crate::model::CursorSample;
use crate::{model::CaptureSource, process};
#[cfg(windows)]
pub struct DpiGuard(windows::Win32::UI::HiDpi::DPI_AWARENESS_CONTEXT);
#[cfg(windows)]
impl DpiGuard {
    pub fn new() -> Self {
        use windows::Win32::UI::HiDpi::{
            SetThreadDpiAwarenessContext, DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2,
        };
        // SAFETY: A thread-local DPI context is restored by Drop on the same thread.
        Self(unsafe { SetThreadDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2) })
    }
}
#[cfg(windows)]
impl Drop for DpiGuard {
    fn drop(&mut self) {
        if !self.0 .0.is_null() {
            // SAFETY: The saved context came from SetThreadDpiAwarenessContext on this thread.
            unsafe {
                windows::Win32::UI::HiDpi::SetThreadDpiAwarenessContext(self.0);
            }
        }
    }
}
pub fn microphones() -> Result<Vec<String>, String> {
    #[cfg(windows)]
    {
        let o = process::command(process::tool("ffmpeg"))
            .args([
                "-hide_banner",
                "-list_devices",
                "true",
                "-f",
                "dshow",
                "-i",
                "dummy",
            ])
            .output()
            .map_err(|_| "FFmpeg is required to list microphones.".to_string())?;
        let text = String::from_utf8_lossy(&o.stderr);
        Ok(text
            .lines()
            .filter(|l| l.contains("(audio)"))
            .filter_map(|l| l.split('"').nth(1).map(String::from))
            .collect())
    }
    #[cfg(target_os = "macos")]
    {
        helper_list("microphones")
    }
    #[cfg(not(any(windows, target_os = "macos")))]
    {
        Ok(vec![])
    }
}
#[cfg(target_os = "macos")]
static HELPER: std::sync::OnceLock<std::path::PathBuf> = std::sync::OnceLock::new();
#[cfg(target_os = "macos")]
pub fn install_helper(root: &std::path::Path) -> Result<(), String> {
    use std::os::unix::fs::PermissionsExt;
    let dir = root.join("native");
    std::fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    let path = dir.join("studio-capture");
    std::fs::write(&path, include_bytes!(env!("STUDIO_HELPER_BINARY")))
        .map_err(|e| e.to_string())?;
    std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o700))
        .map_err(|e| e.to_string())?;
    let _ = HELPER.set(path);
    Ok(())
}
#[cfg(target_os = "macos")]
pub fn helper() -> std::path::PathBuf {
    if let Some(p) = std::env::var_os("STUDIO_CAPTURE_HELPER") {
        return p.into();
    }
    HELPER
        .get()
        .cloned()
        .unwrap_or_else(|| "studio-capture".into())
}
#[cfg(target_os = "macos")]
fn helper_list<T: serde::de::DeserializeOwned>(action: &str) -> Result<T, String> {
    let o = process::command(helper())
        .arg(action)
        .output()
        .map_err(|_| {
            "Native capture helper missing. Build native/macos with Xcode 16+ on macOS 15+."
                .to_string()
        })?;
    let o = process::checked(o, "ScreenCaptureKit source listing")?;
    serde_json::from_slice(&o.stdout).map_err(|e| e.to_string())
}
#[cfg(target_os = "macos")]
pub fn sources() -> Result<Vec<CaptureSource>, String> {
    helper_list("sources")
}
#[cfg(windows)]
fn window_handle(source: &CaptureSource) -> Result<windows::Win32::Foundation::HWND, String> {
    let raw = source
        .id
        .strip_prefix("window:")
        .and_then(|s| s.parse::<isize>().ok())
        .filter(|v| *v > 0)
        .ok_or("Invalid selected window identifier.")?;
    Ok(windows::Win32::Foundation::HWND(
        raw as *mut std::ffi::c_void,
    ))
}
#[cfg(windows)]
fn protected_hud(h: windows::Win32::Foundation::HWND, hud: Option<isize>) -> bool {
    use windows::Win32::UI::WindowsAndMessaging::GetWindowThreadProcessId;
    let mut pid = 0;
    // SAFETY: OS receives a valid writable PID buffer; invalid handles return zero.
    unsafe {
        GetWindowThreadProcessId(h, Some(&mut pid));
        pid == std::process::id() && hud == Some(h.0 as isize)
    }
}
#[cfg(windows)]
fn window_rect(source: &CaptureSource) -> Result<(i32, i32, u32, u32), String> {
    use windows::Win32::{
        Foundation::{POINT, RECT},
        Graphics::Gdi::ClientToScreen,
        UI::WindowsAndMessaging::{GetClientRect, IsIconic, IsWindowVisible},
    };
    let h = window_handle(source)?;
    let mut rect = RECT::default();
    let mut origin = POINT::default();
    // SAFETY: Handle is obtained from native source enumeration; OS validates liveness, buffers are valid.
    unsafe {
        if !IsWindowVisible(h).as_bool()
            || IsIconic(h).as_bool()
            || GetClientRect(h, &mut rect).is_err()
            || !ClientToScreen(h, &mut origin).as_bool()
        {
            return Err("Selected window disappeared or was minimized. Restore it, refresh sources, and try again.".into());
        }
    }
    if rect.right - rect.left < 16 || rect.bottom - rect.top < 16 {
        return Err("Selected window has no recordable client area.".into());
    }
    Ok((
        origin.x,
        origin.y,
        (rect.right - rect.left) as u32,
        (rect.bottom - rect.top) as u32,
    ))
}
#[cfg(windows)]
pub fn prepare_window(source: &mut CaptureSource, hud: Option<isize>) -> Result<(), String> {
    use windows::Win32::UI::WindowsAndMessaging::{BringWindowToTop, SetForegroundWindow};
    let _dpi = DpiGuard::new();
    let h = window_handle(source)?;
    window_rect(source)?;
    // SAFETY: Foreground only the explicitly selected native window; never change its size or position.
    unsafe {
        let _ = BringWindowToTop(h);
        let _ = SetForegroundWindow(h);
    }
    std::thread::sleep(std::time::Duration::from_millis(200));
    let (x, y, w, h) = window_rect(source)?;
    source.x = x;
    source.y = y;
    source.width = w;
    source.height = h;
    window_capture_safe(source, hud)
}
#[cfg(windows)]
pub fn window_capture_safe(source: &CaptureSource, hud: Option<isize>) -> Result<(), String> {
    use windows::Win32::{
        Foundation::POINT,
        UI::WindowsAndMessaging::{GetAncestor, WindowFromPoint, GA_ROOT},
    };
    let _dpi = DpiGuard::new();
    let h = window_handle(source)?;
    let rect = window_rect(source)?;
    if rect != (source.x, source.y, source.width, source.height) {
        return Err("Selected window moved or resized. Capture stopped to preserve its original bounds; click Stop to save, then start again.".into());
    }
    // Focus can belong to a non-overlapping window. Actual occlusion, not focus,
    // determines whether this fixed client rectangle remains safe to capture.
    // SAFETY: Only query native hit-test handles. These calls do not read window contents.
    unsafe {
        for fx in [0.05, 0.5, 0.95] {
            for fy in [0.05, 0.5, 0.95] {
                let point = POINT {
                    x: source.x + (source.width as f64 * fx) as i32,
                    y: source.y + (source.height as f64 * fy) as i32,
                };
                let hit = GetAncestor(WindowFromPoint(point), GA_ROOT);
                if hit != h && !protected_hud(hit, hud) {
                    return Err("Another window covers the selected capture area. Remove overlays; click Stop to save the captured portion.".into());
                }
            }
        }
    }
    Ok(())
}
#[cfg(not(any(windows, target_os = "macos")))]
pub fn sources() -> Result<Vec<CaptureSource>, String> {
    Err("Capture supports Windows and macOS 15+.".into())
}
#[cfg(windows)]
pub fn sources() -> Result<Vec<CaptureSource>, String> {
    let _dpi = DpiGuard::new();
    use windows::Win32::{
        Foundation::{BOOL, HWND, LPARAM, POINT, RECT},
        Graphics::Gdi::{ClientToScreen, EnumDisplayMonitors, HDC, HMONITOR},
        UI::WindowsAndMessaging::{
            EnumWindows, GetClientRect, GetWindowTextW, GetWindowThreadProcessId, IsWindowVisible,
        },
    };
    // SAFETY: OS invokes callbacks synchronously; LPARAM points to a live Vec for the enumeration duration.
    unsafe extern "system" fn monitor(h: HMONITOR, _: HDC, r: *mut RECT, p: LPARAM) -> BOOL {
        let v = &mut *(p.0 as *mut Vec<CaptureSource>);
        let r = *r;
        v.push(CaptureSource {
            id: format!("screen:{}", h.0 as isize),
            name: format!(
                "Display {} · {}×{}",
                v.len() + 1,
                r.right - r.left,
                r.bottom - r.top
            ),
            kind: "screen".into(),
            x: r.left,
            y: r.top,
            width: (r.right - r.left) as u32,
            height: (r.bottom - r.top) as u32,
        });
        BOOL(1)
    }
    // SAFETY: The callback accesses only valid OS handles and a live caller-owned Vec.
    unsafe extern "system" fn window(h: HWND, p: LPARAM) -> BOOL {
        if !IsWindowVisible(h).as_bool() {
            return BOOL(1);
        }
        let mut pid = 0;
        GetWindowThreadProcessId(h, Some(&mut pid));
        if pid == std::process::id() {
            return BOOL(1);
        }
        let mut title = [0u16; 512];
        let n = GetWindowTextW(h, &mut title);
        let mut r = RECT::default();
        let mut origin = POINT::default();
        if n > 0
            && GetClientRect(h, &mut r).is_ok()
            && ClientToScreen(h, &mut origin).as_bool()
            && r.right - r.left >= 16
            && r.bottom - r.top >= 16
        {
            let v = &mut *(p.0 as *mut Vec<CaptureSource>);
            v.push(CaptureSource {
                id: format!("window:{}", h.0 as isize),
                name: String::from_utf16_lossy(&title[..n as usize]),
                kind: "window".into(),
                x: origin.x,
                y: origin.y,
                width: (r.right - r.left) as u32,
                height: (r.bottom - r.top) as u32,
            })
        }
        BOOL(1)
    }
    let mut out = Vec::new();
    unsafe {
        let p = LPARAM(&mut out as *mut _ as isize);
        let _ = EnumDisplayMonitors(HDC::default(), None, Some(monitor), p);
        EnumWindows(Some(window), p).map_err(|e| e.to_string())?;
    }
    Ok(out)
}
#[cfg(windows)]
pub fn cursor(time: f64, source: &CaptureSource) -> Option<CursorSample> {
    use windows::Win32::{
        Foundation::POINT,
        UI::{
            Input::KeyboardAndMouse::{GetAsyncKeyState, VK_LBUTTON},
            WindowsAndMessaging::GetCursorPos,
        },
    };
    let mut p = POINT::default();
    // SAFETY: GetCursorPos writes to a valid POINT; GetAsyncKeyState reads the OS key state.
    unsafe {
        if GetCursorPos(&mut p).is_err() {
            return None;
        }
        let click = GetAsyncKeyState(VK_LBUTTON.0 as i32) < 0;
        let x = (p.x - source.x) as f64 / source.width as f64;
        let y = (p.y - source.y) as f64 / source.height as f64;
        if !(0.0..=1.0).contains(&x) || !(0.0..=1.0).contains(&y) {
            return None;
        }
        Some(CursorSample { time, x, y, click })
    }
}
