use std::path::{Path, PathBuf};
use std::process::{Child, Command};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::{Manager, RunEvent};

/// Child processes (MCP server + studio sidecar) owned by the desktop shell.
struct Sidecars(Mutex<Vec<Child>>);

/// The splash window declared in `tauri.conf.json`, up at launch and closed on
/// the handover to `main`.
const SPLASH_WINDOW: &str = "splashscreen";

/// The shortest time the splash stays up, measured from launch rather than from
/// the moment the frontend happens to report in. A branded frame that a fast boot
/// blinks past is worse than no splash at all.
const SPLASH_MIN_VISIBLE: Duration = Duration::from_millis(900);

/// Below this, the boot was so fast the splash barely painted: holding it for the
/// minimum would be pure added delay, so the handover happens at once.
const SPLASH_SKIP_BELOW: Duration = Duration::from_millis(250);

/// The longest the splash may hold the app back. A frontend that never reports —
/// a bundle that failed to load, a crashed renderer — still gets a window.
const SPLASH_MAX_WAIT: Duration = Duration::from_secs(8);

/// The opt-out. Set `AGENTIC_ODI_SPLASH=off` (or `0`) to launch straight into
/// `main`, with no splash window at all.
const SPLASH_ENV: &str = "AGENTIC_ODI_SPLASH";

/// Whether the splash is wanted. Anything but an explicit "off"/"0" keeps it on,
/// so a typo cannot silently disable the branding.
fn splash_enabled() -> bool {
    match std::env::var(SPLASH_ENV) {
        Ok(value) => {
            let value = value.trim().to_ascii_lowercase();
            !matches!(value.as_str(), "off" | "0" | "false")
        }
        Err(_) => true,
    }
}

/// The splash's clock and its one-shot handover latch.
struct Splash {
    shown: Instant,
    revealed: AtomicBool,
}

/// Reveal `main` and retire the splash. Idempotent: the frontend's report, the
/// minimum-display timer, and the watchdog all race here, and only the first
/// one moves the windows.
fn reveal(app: &tauri::AppHandle) {
    let splash = app.state::<Splash>();
    if splash.revealed.swap(true, Ordering::SeqCst) {
        return;
    }
    if let Some(main) = app.get_webview_window("main") {
        let _ = main.show();
        let _ = main.set_focus();
    }
    if let Some(window) = app.get_webview_window(SPLASH_WINDOW) {
        let _ = window.close();
    }
}

/// The frontend reports that it has committed and finished first-boot work.
///
/// The wait is a background thread so the command returns at once and a slow
/// handover can never block a turn. The frontend also times out its own call, so
/// neither side can hang the launch on the other.
#[tauri::command]
fn set_complete(app: tauri::AppHandle, splash: tauri::State<'_, Splash>) {
    let elapsed = splash.shown.elapsed();
    // A boot under the skip threshold means the splash barely painted; waiting
    // out the minimum would only slow a fast machine down.
    let remaining = if elapsed < SPLASH_SKIP_BELOW {
        Duration::ZERO
    } else {
        SPLASH_MIN_VISIBLE.saturating_sub(elapsed)
    };
    std::thread::spawn(move || {
        if !remaining.is_zero() {
            std::thread::sleep(remaining);
        }
        reveal(&app);
    });
}

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
        if dir.join("apps/mcp-server").is_dir() && dir.join("apps/studio-api").is_dir() {
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
        // The updater installs the new bundle; this plugin performs the
        // in-place relaunch that makes the staged update take effect.
        .plugin(tauri_plugin_process::init())
        .manage(Sidecars(Mutex::new(Vec::new())))
        .manage(Splash {
            shown: Instant::now(),
            revealed: AtomicBool::new(false),
        })
        .invoke_handler(tauri::generate_handler![set_complete])
        .setup(|app| {
            if splash_enabled() {
                // The watchdog. If the frontend never reports — a bundle that
                // failed to load, a renderer that crashed — the app still gets a
                // window instead of a splash that never leaves.
                let handle = app.handle().clone();
                std::thread::spawn(move || {
                    std::thread::sleep(SPLASH_MAX_WAIT);
                    reveal(&handle);
                });
            } else {
                // Opt-out: retire the splash and show `main` at once, with no
                // branded frame at all.
                if let Some(window) = app.get_webview_window(SPLASH_WINDOW) {
                    let _ = window.close();
                }
                if let Some(main) = app.get_webview_window("main") {
                    let _ = main.show();
                }
            }

            match find_repo_root() {
                Some(cwd) => {
                    let state = app.state::<Sidecars>();
                    let mut children = state.0.lock().expect("sidecar mutex poisoned");
                    if let Some(child) = spawn_module(&cwd, "agentic_odi_mcp_server") {
                        children.push(child);
                    }
                    if let Some(child) = spawn_module(&cwd, "agentic_odi_studio_api.main") {
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
