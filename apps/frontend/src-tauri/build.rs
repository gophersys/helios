// src-tauri/build.rs — the Tauri build hook. It generates the capability/permission glue
// (gen/schemas/*) from tauri.conf.json + capabilities/ at compile time, so the cargo build sees a
// complete context. Standard Tauri 2 boilerplate; no Eden-specific logic here.
fn main() {
    tauri_build::build()
}
