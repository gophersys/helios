// src-tauri/src/lib.rs — the Eden desktop shell entry (Tauri 2 split-lib layout).
//
// The shell is deliberately thin (ADR-0006): it builds a Tauri app over the SAME SvelteKit web bundle
// the browser serves and registers ONLY the plugins the desktop-only handoffs need. The single
// desktop-specific behaviour is the "Open in VS Code" path: the web app sets
//   window.location.href = "vscode://vscode-remote/ssh-remote+<host><worktreePath>"
// and the OS routes that scheme to the user's native VS Code. The tauri-plugin-shell (scoped in
// capabilities/default.json to the vscode:/vscode-insiders: schemes) lets that external-scheme
// navigation reach the OS handler instead of being blocked by the webview. No Eden business logic
// runs in Rust — all of that stays in the web bundle, over HTTP/SSE to the gateway.

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .run(tauri::generate_context!())
        .expect("error while running the Eden desktop shell");
}
