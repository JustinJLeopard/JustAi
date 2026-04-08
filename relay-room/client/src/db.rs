use anyhow::{Context, Result, bail};
use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::{Command, Output, Stdio};

#[derive(Clone, Debug)]
pub struct RelayDb {
    pub database: String,
    pub server: String,
    pub anonymous: bool,
    pub spacetime_bin: String,
}

impl RelayDb {
    pub fn from_env() -> Self {
        Self {
            database: env::var("RELAY_DB_NAME").unwrap_or_else(|_| {
                resolve_database_target().unwrap_or_else(|| "relay-room-dev".to_string())
            }),
            server: env::var("RELAY_SERVER").unwrap_or_else(|_| "local-server".to_string()),
            anonymous: env::var("RELAY_ANONYMOUS")
                .map(|value| value != "0" && value.to_lowercase() != "false")
                .unwrap_or(true),
            spacetime_bin: env::var("RELAY_SPACETIME_BIN")
                .unwrap_or_else(|_| "spacetime".to_string()),
        }
    }

    pub fn call<I, S>(&self, reducer: &str, args: I) -> Result<String>
    where
        I: IntoIterator<Item = S>,
        S: Into<String>,
    {
        let mut cmd = self.base_command("call");
        cmd.arg(&self.database).arg(reducer);
        for arg in args {
            cmd.arg(arg.into());
        }
        self.run(cmd)
    }

    pub fn sql(&self, query: &str) -> Result<String> {
        let mut cmd = self.base_command("sql");
        cmd.arg(&self.database).arg(query);
        self.run(cmd)
    }

    fn base_command(&self, subcommand: &str) -> Command {
        let mut cmd = Command::new(&self.spacetime_bin);
        cmd.arg(subcommand);
        if self.anonymous {
            cmd.arg("--anonymous");
        }
        cmd.arg("--server").arg(&self.server).arg("-y");
        cmd.stdout(Stdio::piped()).stderr(Stdio::piped());
        cmd
    }

    fn run(&self, mut cmd: Command) -> Result<String> {
        let rendered = render_command(&cmd);
        let output = cmd
            .output()
            .with_context(|| format!("failed to run `{rendered}`"))?;
        parse_output(output, &rendered)
    }
}

fn resolve_database_target() -> Option<String> {
    let cwd = env::current_dir().ok()?;
    find_target_file(&cwd).and_then(read_target_file)
}

fn find_target_file(start: &Path) -> Option<PathBuf> {
    for dir in start.ancestors() {
        let candidate = dir.join(".relay-db-target");
        if candidate.is_file() {
            return Some(candidate);
        }
    }
    None
}

fn read_target_file(path: PathBuf) -> Option<String> {
    let raw = fs::read_to_string(path).ok()?;
    let target = raw.trim().to_string();
    if target.is_empty() {
        None
    } else {
        Some(target)
    }
}

fn parse_output(output: Output, rendered: &str) -> Result<String> {
    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();

    if !output.status.success() {
        if stderr.is_empty() {
            bail!("`{rendered}` failed with exit status {}", output.status);
        }
        bail!("`{rendered}` failed:\n{stderr}");
    }

    if stderr.is_empty() {
        Ok(stdout)
    } else if stdout.is_empty() {
        Ok(stderr)
    } else {
        Ok(format!("{stdout}\n{stderr}"))
    }
}

fn render_command(cmd: &Command) -> String {
    let program = cmd.get_program().to_string_lossy();
    let args = cmd
        .get_args()
        .map(|arg| shell_escape(&arg.to_string_lossy()))
        .collect::<Vec<_>>()
        .join(" ");
    format!("{program} {args}")
}

fn shell_escape(value: &str) -> String {
    if value
        .chars()
        .all(|ch| ch.is_ascii_alphanumeric() || matches!(ch, '-' | '_' | '.' | '/' | ':'))
    {
        value.to_string()
    } else {
        format!("{value:?}")
    }
}

#[cfg(test)]
mod tests {
    use super::{
        RelayDb, find_target_file, parse_output, read_target_file, render_command, shell_escape,
    };
    use std::process::{Command, Output};
    use tempfile::tempdir;

    #[test]
    fn from_env_uses_defaults() {
        let db = RelayDb::from_env();
        assert_eq!(db.server, "local-server");
        assert!(db.anonymous);
        assert_eq!(db.spacetime_bin, "spacetime");
    }

    #[test]
    fn find_target_file_walks_up_directory_tree() {
        let dir = tempdir().unwrap();
        let nested = dir.path().join("a").join("b");
        std::fs::create_dir_all(&nested).unwrap();
        let target = dir.path().join(".relay-db-target");
        std::fs::write(&target, "relay-target\n").unwrap();

        assert_eq!(find_target_file(&nested).unwrap(), target);
        assert_eq!(read_target_file(target).unwrap(), "relay-target");
    }

    #[test]
    fn shell_escape_leaves_safe_values_untouched() {
        assert_eq!(shell_escape("relay-room-dev"), "relay-room-dev");
        assert_eq!(shell_escape("local-server"), "local-server");
    }

    #[test]
    fn shell_escape_quotes_values_with_spaces() {
        assert_eq!(
            shell_escape("select * from tasks"),
            "\"select * from tasks\""
        );
    }

    #[test]
    fn render_command_includes_escaped_arguments() {
        let mut cmd = Command::new("relay");
        cmd.arg("tasks").arg("select * from tasks");
        assert_eq!(render_command(&cmd), "relay tasks \"select * from tasks\"");
    }

    #[test]
    fn parse_output_prefers_stdout_when_stderr_empty() {
        let output = Output {
            status: exit_status(0),
            stdout: b"ok\n".to_vec(),
            stderr: Vec::new(),
        };
        assert_eq!(parse_output(output, "relay status").unwrap(), "ok");
    }

    #[test]
    fn parse_output_combines_stdout_and_stderr_on_success() {
        let output = Output {
            status: exit_status(0),
            stdout: b"data\n".to_vec(),
            stderr: b"warning".to_vec(),
        };
        assert_eq!(
            parse_output(output, "relay status").unwrap(),
            "data\nwarning"
        );
    }

    #[test]
    fn parse_output_returns_error_with_stderr() {
        let output = Output {
            status: exit_status(1),
            stdout: Vec::new(),
            stderr: b"boom".to_vec(),
        };
        let err = parse_output(output, "relay status")
            .unwrap_err()
            .to_string();
        assert!(err.contains("relay status"));
        assert!(err.contains("boom"));
    }

    #[cfg(unix)]
    fn exit_status(code: i32) -> std::process::ExitStatus {
        use std::os::unix::process::ExitStatusExt;
        std::process::ExitStatus::from_raw(code << 8)
    }
}
