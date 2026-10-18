use std::path::{Path, PathBuf};
use std::process::{Child, Command};
use std::sync::Mutex;

use tauri::{Manager, RunEvent};

/// Child processes (MCP server + studio sidecar) owned by the desktop shell.
struct Sidecars(Mutex<Vec<Child>>);

/// Locate the repository root so the sidecar modules can be launched with the
/// project's `uv` environment. Prefers an explicit override, then walks up from
/// the current working directory looking for the two server packages.
fn find_repo_root() -> Option<PathBuf> {
    if let Ok(root) = std::env::var("AGENTIC_ODI_REPO_ROOT") {
        let path = PathBuf::from(root);
        if path.is_dir() {
            return Some(path);
        }
    }

    let mut dir = std::env::current_dir().ok()?;
    loop {
        if dir.join("mcp_server").is_dir() && dir.join("local_server").is_dir() {
            return Some(dir);
        }
        if !dir.pop() {
            return None;
        }
    }
}

/// Spawn `uv run python -m <module>` from the given working directory.
fn spawn_module(cwd: &Path, module: &str) -> Option<Child> {
    match Command::new("uv")
        .arg("run")
        .arg("python")
        .arg("-m")
        .arg(module)
        .current_dir(cwd)
        .spawn()
    {
        Ok(child) => Some(child),
        Err(err) => {
            eprintln!("failed to spawn `{module}`: {err}");
            None
        }
    }
}

fn shutdown(children: &mut Vec<Child>) {
    for child in children.iter_mut() {
        let _ = child.kill();
        let _ = child.wait();
    }
    children.clear();
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(Sidecars(Mutex::new(Vec::new())))
        .setup(|app| {
            match find_repo_root() {
                Some(cwd) => {
                    let state = app.state::<Sidecars>();
                    let mut children = state.0.lock().expect("sidecar mutex poisoned");
                    if let Some(child) = spawn_module(&cwd, "mcp_server") {
                        children.push(child);
                    }
                    if let Some(child) = spawn_module(&cwd, "local_server.main") {
                        children.push(child);
                    }
                }
                None => {
                    eprintln!("could not locate repository root; Python sidecar was not started");
                }
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if let RunEvent::Exit = event {
                let state = app_handle.state::<Sidecars>();
                let mut children = match state.0.lock() {
                    Ok(guard) => guard,
                    Err(_) => return,
                };
                shutdown(&mut children);
            }
        });
}
