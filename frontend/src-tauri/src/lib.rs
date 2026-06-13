// Augur 桌面外壳：启动时 spawn 打包进 app 的 PyInstaller 独立后端（onedir），
// 注入数据目录，退出时 kill。后端不在 → 弹原生错误对话框而非白屏。
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;

use tauri::{Manager, RunEvent};

/// 持有打包后端子进程句柄，供 app 退出时 kill。
struct BackendProcess(Mutex<Option<Child>>);

/// 定位后端二进制：打包态在 app 的 Resources/augur-backend/augur-backend（onedir，
/// 二进制与 _internal/ 同级随 bundle 一起进 Resources）；开发态回退仓库内 PyInstaller 产物。
fn backend_binary(app: &tauri::App) -> Option<std::path::PathBuf> {
    if let Ok(res) = app.path().resource_dir() {
        let p = res.join("augur-backend").join("augur-backend");
        if p.exists() {
            return Some(p);
        }
    }
    // tauri dev 下无 bundle，回退到仓库 backend/dist（需先 `pyinstaller augur.spec`）。
    let dev = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../backend/dist/augur-backend/augur-backend");
    dev.exists().then_some(dev)
}

/// spawn 打包后端：注入 AUGUR_DATA_DIR=~/Library/Application Support/Augur，
/// 后端 stdout/stderr 落 <data>/logs/backend.log（朋友机无终端，便于排查）。
fn spawn_backend(app: &tauri::App) -> Result<Child, String> {
    let bin = backend_binary(app)
        .ok_or_else(|| "找不到打包的 Augur 后端二进制（augur-backend）。".to_string())?;

    let data_dir = app
        .path()
        .data_dir()
        .map_err(|e| format!("无法解析应用数据目录：{e}"))?
        .join("Augur");
    std::fs::create_dir_all(&data_dir).ok();

    // 资源打包可能丢失可执行位 → 显式补上，否则 spawn 报 Permission denied。
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        if let Ok(meta) = std::fs::metadata(&bin) {
            let mut perm = meta.permissions();
            perm.set_mode(0o755);
            let _ = std::fs::set_permissions(&bin, perm);
        }
    }

    let mut cmd = Command::new(&bin);
    cmd.env("AUGUR_DATA_DIR", &data_dir);

    let log_dir = data_dir.join("logs");
    std::fs::create_dir_all(&log_dir).ok();
    if let Ok(out) = std::fs::File::create(log_dir.join("backend.log")) {
        if let Ok(err) = out.try_clone() {
            cmd.stdout(Stdio::from(out)).stderr(Stdio::from(err));
        }
    }

    cmd.spawn()
        .map_err(|e| format!("启动后端失败（{}）：{e}", bin.display()))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(BackendProcess(Mutex::new(None)))
        .setup(|app| {
            #[cfg(debug_assertions)]
            app.handle().plugin(
                tauri_plugin_log::Builder::default()
                    .level(log::LevelFilter::Info)
                    .build(),
            )?;

            match spawn_backend(app) {
                Ok(child) => {
                    app.state::<BackendProcess>().0.lock().unwrap().replace(child);
                }
                Err(e) => {
                    rfd::MessageDialog::new()
                        .set_level(rfd::MessageLevel::Error)
                        .set_title("Augur 启动失败")
                        .set_description(format!(
                            "{e}\n\n可查看日志：~/Library/Application Support/Augur/logs/backend.log"
                        ))
                        .show();
                    std::process::exit(1);
                }
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building Augur")
        .run(|app_handle, event| {
            // app 退出（关窗 / Cmd-Q）时 kill 后端，避免残留进程占端口。
            if let RunEvent::ExitRequested { .. } = event {
                if let Some(state) = app_handle.try_state::<BackendProcess>() {
                    if let Some(mut child) = state.0.lock().unwrap().take() {
                        let _ = child.kill();
                        let _ = child.wait();
                    }
                }
            }
        });
}
