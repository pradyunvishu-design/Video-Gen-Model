fn main() {
    // Deterministic first-party ICO, generated locally; no downloaded branding/assets.
    std::fs::create_dir_all("icons").expect("create generated icon directory");
    let mut icon = vec![0, 0, 1, 0, 1, 0, 32, 32, 0, 0, 1, 0, 32, 0];
    icon.extend_from_slice(&4264u32.to_le_bytes());
    icon.extend_from_slice(&22u32.to_le_bytes());
    for value in [40u32, 32, 64] {
        icon.extend_from_slice(&value.to_le_bytes());
    }
    icon.extend_from_slice(&[1, 0, 32, 0]);
    for value in [0u32, 4096, 0, 0, 0, 0] {
        icon.extend_from_slice(&value.to_le_bytes());
    }
    for y in 0i32..32 {
        for x in 0i32..32 {
            let inside = (x - 16).pow(2) + (y - 16).pow(2) < 100;
            icon.extend_from_slice(if inside {
                &[238, 211, 34, 255]
            } else {
                &[39, 24, 17, 255]
            });
        }
    }
    icon.extend_from_slice(&[0u8; 128]);
    if std::fs::read("icons/icon.ico").ok().as_deref() != Some(icon.as_slice()) {
        std::fs::write("icons/icon.ico", icon).expect("write generated studio icon");
    }
    #[cfg(target_os = "macos")]
    {
        use std::{path::PathBuf, process::Command};
        let output = PathBuf::from(std::env::var_os("OUT_DIR").expect("Cargo OUT_DIR"))
            .join("studio-capture");
        let target = std::env::var("TARGET").expect("Cargo TARGET");
        let arch = if target.starts_with("aarch64") {
            "arm64-apple-macosx15.0"
        } else {
            "x86_64-apple-macosx15.0"
        };
        let status = Command::new("xcrun")
            .args([
                "swiftc",
                "-parse-as-library",
                "-O",
                "-target",
                arch,
                "-Xlinker",
                "-sectcreate",
                "-Xlinker",
                "__TEXT",
                "-Xlinker",
                "__info_plist",
                "-Xlinker",
                "native/macos/HelperInfo.plist",
                "native/macos/StudioCapture.swift",
                "-o",
            ])
            .arg(&output)
            .status()
            .expect("Install Xcode 16+ command-line tools to build ScreenCaptureKit helper");
        assert!(
            status.success(),
            "ScreenCaptureKit helper compilation failed"
        );
        println!("cargo:rustc-env=STUDIO_HELPER_BINARY={}", output.display());
        println!("cargo:rerun-if-changed=native/macos/StudioCapture.swift");
        println!("cargo:rerun-if-changed=native/macos/HelperInfo.plist");
    }
    tauri_build::build()
}
