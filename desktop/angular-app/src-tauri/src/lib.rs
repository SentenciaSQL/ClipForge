use std::net::TcpStream;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use std::time::Duration;

use tauri::Manager;

struct BackendState(Mutex<Option<Child>>);

fn backend_healthy() -> bool {
  TcpStream::connect_timeout(
    &"127.0.0.1:8000".parse().expect("valid addr"),
    Duration::from_millis(400),
  )
  .is_ok()
}

fn sidecar_candidates() -> Vec<PathBuf> {
  let mut paths = Vec::new();
  if let Ok(exe) = std::env::current_exe() {
    if let Some(dir) = exe.parent() {
      paths.push(dir.join("sidecars").join("ai-video-clipper-api.exe"));
      paths.push(dir.join("sidecars").join("ai-video-clipper-api"));
      paths.push(dir.join("ai-video-clipper-api.exe"));
      paths.push(dir.join("resources").join("sidecars").join("ai-video-clipper-api.exe"));
      paths.push(dir.join("resources").join("sidecars").join("ai-video-clipper-api"));
    }
  }
  paths
}

fn spawn_sidecar_backend(state: &BackendState) -> Result<(), String> {
  if backend_healthy() {
    log::info!("Backend already reachable on 127.0.0.1:8000");
    return Ok(());
  }

  let sidecar = sidecar_candidates().into_iter().find(|p| p.exists());
  let Some(path) = sidecar else {
    log::warn!("No sidecar binary found; expecting an external backend on :8000");
    return Ok(());
  };

  log::info!("Starting packaged backend sidecar at {:?}", path);
  let child = Command::new(&path)
    .env("AVC_HOST", "127.0.0.1")
    .env("AVC_PORT", "8000")
    .stdout(Stdio::null())
    .stderr(Stdio::null())
    .spawn()
    .map_err(|err| format!("Failed to spawn backend: {err}"))?;

  *state.0.lock().map_err(|e| e.to_string())? = Some(child);

  for _ in 0..40 {
    if backend_healthy() {
      log::info!("Backend health check passed");
      return Ok(());
    }
    thread::sleep(Duration::from_millis(250));
  }
  Err("Backend failed to become healthy on 127.0.0.1:8000".into())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  tauri::Builder::default()
    .manage(BackendState(Mutex::new(None)))
    .setup(|app| {
      if cfg!(debug_assertions) {
        app.handle().plugin(
          tauri_plugin_log::Builder::default()
            .level(log::LevelFilter::Info)
            .build(),
        )?;
      }
      let state = app.state::<BackendState>();
      if let Err(err) = spawn_sidecar_backend(&*state) {
        log::warn!("Sidecar startup skipped/failed: {err}");
      }
      Ok(())
    })
    .on_window_event(|window, event| {
      if let tauri::WindowEvent::Destroyed = event {
        if let Some(state) = window.try_state::<BackendState>() {
          if let Ok(mut guard) = state.0.lock() {
            if let Some(mut child) = guard.take() {
              let _ = child.kill();
            }
          }
        }
      }
    })
    .run(tauri::generate_context!())
    .expect("error while building tauri application");
}
