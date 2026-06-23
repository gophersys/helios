// src-tauri/src/main.rs — the desktop binary entry. The `windows_subsystem` attribute keeps a
// packaged Windows build from spawning a console window; on macOS/Linux it is a no-op. All wiring
// lives in lib.rs (the Tauri 2 split-lib layout, shared with a future mobile entry point).
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    eden_desktop_lib::run()
}
