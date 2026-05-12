// Rust Tauri v2 shell — prevents console window on Windows in release builds
#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

fn main() {
    iris_overlay_lib::run();
}
