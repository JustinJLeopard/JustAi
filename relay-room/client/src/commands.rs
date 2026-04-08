use crate::db::RelayDb;
use anyhow::{Context, Result};
use serde_json::{Map, Value, json};
use std::thread;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use uuid::Uuid;

pub fn register(db: &RelayDb, agent: &str, handler_type: &str, caps: &str) -> Result<()> {
    println!(
        "{}",
        db.call("register_agent", [agent, handler_type, caps])?
    );
    Ok(())
}

pub fn agents(db: &RelayDb, json_output: bool) -> Result<()> {
    let output = db.sql(
        "select name, handler_type, status, current_task_id, capabilities, last_heartbeat, last_seen from agents"
    )?;
    if json_output {
        println!("{}", render_agents_json(&output)?);
    } else {
        println!("{output}");
    }
    Ok(())
}

pub fn heartbeat(db: &RelayDb, agent: &str) -> Result<()> {
    println!("{}", db.call("heartbeat", [agent])?);
    Ok(())
}

pub fn agent_status(db: &RelayDb, agent: &str, status: &str, current_task: u64) -> Result<()> {
    println!(
        "{}",
        db.call(
            "set_agent_status",
            [
                agent.to_string(),
                status.to_string(),
                current_task.to_string()
            ],
        )?
    );
    Ok(())
}

pub fn status(db: &RelayDb) -> Result<()> {
    println!("Database: {}", db.database);
    println!("Server:   {}", db.server);
    println!("\nAgents");
    println!("{}", db.sql("select * from agents")?);
    Ok(())
}

pub fn board(db: &RelayDb, all: bool, json_output: bool) -> Result<()> {
    if json_output {
        println!("{}", render_board_json(db, all)?);
        return Ok(());
    }
    println!("Agents");
    println!("{}", db.sql("select * from agents")?);
    println!("\nActive Tasks");
    let active_tasks_output = db.sql("select * from tasks where status != 'done' and status != 'failed' and status != 'archived'")?;
    println!("{}", active_tasks_output);
    let active_count = count_data_rows(&active_tasks_output);
    if all {
        println!("\nDone/Failed Tasks");
        let done_failed_output = db.sql("select * from tasks where status = 'done' or status = 'failed'")?;
        println!("{}", done_failed_output);
        let done_failed_count = count_data_rows(&done_failed_output);
        println!("--- Total done/failed tasks: {} ---", done_failed_count);
        println!("\nArchived Tasks");
        let archived_output = db.sql("select * from archived_tasks")?;
        println!("{}", archived_output);
        let archived_count = count_data_rows(&archived_output);
        println!("--- Total archived tasks: {} ---", archived_count);
    }
    println!("\nRecent Events");
    println!("{}", render_recent_events_table(&db.sql("select * from events")?, 20)?);
    println!("\n--- Total active tasks: {} ---", active_count);
    Ok(())
}

pub fn tasks(
    db: &RelayDb,
    from: Option<&str>,
    to: Option<&str>,
    status: Option<&str>,
) -> Result<()> {
    println!("{}", db.sql(&build_tasks_query(from, to, status))?);
    Ok(())
}

pub fn show(db: &RelayDb, id: u64, json_output: bool) -> Result<()> {
    let output = db.sql(&build_show_query(id))?;
    if json_output {
        println!("{}", render_show_json(&output)?);
    } else {
        println!("{output}");
    }
    Ok(())
}

pub fn inbox(db: &RelayDb, agent: &str) -> Result<()> {
    let query = format!(
        "select * from messages where to_agent = '{}'",
        escape_sql(agent)
    );
    println!("{}", db.sql(&query)?);
    Ok(())
}

fn validate_post_args(title: &str, payload: &str) -> Result<()> {
    if title.trim().is_empty() {
        anyhow::bail!("--title cannot be empty. Provide a short summary of the task, e.g. --title \"review PR #42\"");
    }
    if payload.trim().is_empty() {
        anyhow::bail!("--payload cannot be empty. Provide the task details, e.g. --payload \"Please review the changes in PR #42\"");
    }
    Ok(())
}

fn validate_requeue_args(status: &str, claimed_by: &str, agent: &str, id: u64) -> Result<()> {
    if status != "in_progress" {
        anyhow::bail!(
            "task {id} must be in_progress before it can be requeued (status: {status})"
        );
    }
    if claimed_by != agent {
        anyhow::bail!("task {id} is owned by {claimed_by}, not {agent}");
    }
    Ok(())
}

pub fn post(
    db: &RelayDb,
    from: &str,
    to: &str,
    title: &str,
    payload: &str,
    priority: u8,
    task_type: Option<&str>,
    session: &str,
    json_output: bool,
) -> Result<()> {
    validate_post_args(title, payload)?;
    let task_uuid = Uuid::new_v4().to_string();
    let session_ref = build_session_ref(task_type, session)?;
    let reducer_output = db.call(
        "post_task",
        [
            from.to_string(),
            to.to_string(),
            title.to_string(),
            payload.to_string(),
            priority.to_string(),
            session_ref.clone(),
            task_uuid.clone(),
            "1".to_string(),
            "null".to_string(),
        ],
    )?;

    if json_output {
        let lookup = db.sql(&build_task_uuid_query(&task_uuid))?;
        println!("{}", render_post_json(&task_uuid, &lookup)?);
    } else {
        println!("{reducer_output}");
        println!("posted task_uuid={task_uuid}");
    }
    Ok(())
}

pub fn retry(db: &RelayDb, id: u64, json_output: bool) -> Result<()> {
    let output = db.sql(&build_show_query(id))?;
    let task = parse_pipe_table(&output)
        .into_iter()
        .next()
        .context("task not found")?;

    let status = task
        .get("status")
        .and_then(|value| value.as_str())
        .unwrap_or("");
    if status != "failed" && status != "done" {
        anyhow::bail!("task {id} must be done or failed before it can be retried (status: {status})");
    }

    let from = task
        .get("from_agent")
        .and_then(|value| value.as_str())
        .unwrap_or("");
    let to = task
        .get("to_agent")
        .and_then(|value| value.as_str())
        .unwrap_or("manuslocal");
    let title = task
        .get("title")
        .and_then(|value| value.as_str())
        .unwrap_or("");
    let payload = task
        .get("payload")
        .and_then(|value| value.as_str())
        .unwrap_or("");
    let priority = task
        .get("priority")
        .and_then(|value| value.as_u64())
        .unwrap_or(5);
    let session_ref = task
        .get("session_ref")
        .and_then(|value| value.as_str())
        .unwrap_or("session-local");
    let attempt_number = task
        .get("attempt_number")
        .and_then(|value| value.as_u64())
        .unwrap_or(1)
        .saturating_add(1);
    let root_parent = task
        .get("parent_task_id")
        .and_then(|value| value.as_u64())
        .filter(|value| *value != 0)
        .unwrap_or(id);

    let task_uuid = Uuid::new_v4().to_string();
    let reducer_output = db.call(
        "post_task",
        [
            from.to_string(),
            to.to_string(),
            title.to_string(),
            payload.to_string(),
            priority.to_string(),
            session_ref.to_string(),
            task_uuid.clone(),
            attempt_number.to_string(),
            format!("{{\"some\":{root_parent}}}"),
        ],
    )?;

    if json_output {
        let lookup = db.sql(&build_task_uuid_query(&task_uuid))?;
        println!("{}", render_post_json(&task_uuid, &lookup)?);
    } else {
        println!("{reducer_output}");
        println!(
            "retried task {id} → new task_uuid={task_uuid} (attempt {attempt_number}, root {root_parent})"
        );
    }
    Ok(())
}

pub fn requeue(db: &RelayDb, id: u64, agent: &str, error: &str) -> Result<()> {
    let output = db.sql(&build_show_query(id))?;
    let task = parse_pipe_table(&output)
        .into_iter()
        .next()
        .context("task not found")?;
    let status = task
        .get("status")
        .and_then(|value| value.as_str())
        .unwrap_or("");
    let claimed_by = task
        .get("claimed_by")
        .and_then(|value| value.as_str())
        .unwrap_or("");
    validate_requeue_args(status, claimed_by, agent, id)?;
    println!(
        "{}",
        db.call(
            "requeue_task",
            [id.to_string(), agent.to_string(), error.to_string()],
        )?
    );
    Ok(())
}

pub fn claim(db: &RelayDb, id: u64, agent: &str) -> Result<()> {
    println!(
        "{}",
        db.call("claim_task", [id.to_string(), agent.to_string()])?
    );
    Ok(())
}

pub fn start(db: &RelayDb, id: u64, agent: &str) -> Result<()> {
    println!(
        "{}",
        db.call("start_task", [id.to_string(), agent.to_string()])?
    );
    Ok(())
}

pub fn done(db: &RelayDb, id: u64, agent: &str, result: &str) -> Result<()> {
    println!(
        "{}",
        db.call(
            "complete_task",
            [id.to_string(), agent.to_string(), result.to_string()],
        )?
    );
    Ok(())
}

pub fn fail(db: &RelayDb, id: u64, agent: &str, error: &str) -> Result<()> {
    println!(
        "{}",
        db.call(
            "fail_task",
            [id.to_string(), agent.to_string(), error.to_string()],
        )?
    );
    Ok(())
}

pub fn msg(db: &RelayDb, from: &str, to: &str, content: &str, task_ref: u64) -> Result<()> {
    println!(
        "{}",
        db.call(
            "send_message",
            [
                from.to_string(),
                to.to_string(),
                content.to_string(),
                task_ref.to_string(),
            ],
        )?
    );
    Ok(())
}

fn now_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64
}

pub fn archive_list(db: &RelayDb, json_output: bool) -> Result<()> {
    let query = "select * from archived_tasks";
    let output = db.sql(query)?;
    if json_output {
        let rows = parse_pipe_table(&output);
        println!("{}", serde_json::json!(rows));
    } else {
        if output.trim().is_empty() {
            println!("no archived tasks");
        } else {
            println!("{output}");
        }
    }
    Ok(())
}

pub fn archive_count(db: &RelayDb, json_output: bool) -> Result<()> {
    let query = "select * from archived_tasks";
    let output = db.sql(query)?;
    let count = parse_pipe_table(&output).len() as u64;
    if json_output {
        println!("{}", serde_json::json!({"count": count}));
    } else {
        println!("{count} archived task(s)");
    }
    Ok(())
}

pub fn archive(db: &RelayDb, id: Option<u64>, all: bool, dry_run: bool, json_output: bool) -> Result<()> {
    if let Some(task_id) = id {
        // Archive a single task by ID
        if dry_run {
            if json_output {
                println!("{}", serde_json::json!({"dry_run": true, "would_archive": [task_id]}));
            } else {
                println!("[dry-run] would archive task {task_id}");
            }
        } else {
            let output = db.call("archive_task", [task_id.to_string()])?;
            if json_output {
                println!("{}", serde_json::json!({"archived": [task_id]}));
            } else {
                println!("{output}");
                println!("archived task {task_id}");
            }
        }
    } else {
        // Archive done/failed tasks; by default only those older than 24 hours
        let query = if all {
            "select id, status, updated_at from tasks where status = 'done' or status = 'failed'".to_string()
        } else {
            let cutoff_ms = now_ms().saturating_sub(24 * 60 * 60 * 1000);
            format!(
                "select id, status, updated_at from tasks where (status = 'done' or status = 'failed') and updated_at < {cutoff_ms}"
            )
        };
        let rows_output = db.sql(&query)?;
        let rows = parse_pipe_table(&rows_output);
        if rows.is_empty() {
            if json_output {
                let key = if dry_run { "would_archive" } else { "archived" };
                println!("{}", serde_json::json!({key: [], "dry_run": dry_run}));
            } else {
                let qualifier = if all { "" } else { " older than 24 hours" };
                println!("no done/failed tasks{qualifier} to archive");
            }
            return Ok(());
        }
        if dry_run {
            let candidate_ids: Vec<u64> = rows
                .iter()
                .filter_map(|row| row.get("id").and_then(|v| v.as_u64()))
                .collect();
            if json_output {
                println!("{}", serde_json::json!({"dry_run": true, "would_archive": candidate_ids}));
            } else {
                for id_val in &candidate_ids {
                    println!("[dry-run] would archive task {id_val}");
                }
                println!("[dry-run] {} task(s) would be archived", candidate_ids.len());
            }
        } else {
            let mut archived_ids = Vec::new();
            for row in &rows {
                if let Some(id_val) = row.get("id").and_then(|v| v.as_u64()) {
                    match db.call("archive_task", [id_val.to_string()]) {
                        Ok(output) => {
                            if !json_output {
                                println!("{output}");
                            }
                            archived_ids.push(id_val);
                        }
                        Err(e) => {
                            if !json_output {
                                eprintln!("warning: failed to archive task {id_val}: {e}");
                            }
                        }
                    }
                }
            }
            if json_output {
                println!("{}", serde_json::json!({"archived": archived_ids}));
            } else {
                println!("archived {} task(s)", archived_ids.len());
            }
        }
    }
    Ok(())
}

pub fn watch(db: &RelayDb, to: Option<&str>, every_seconds: u64) -> Result<()> {
    loop {
        print!("\x1B[2J\x1B[H");
        if let Some(agent) = to {
            println!("Tasks for {agent}\n");
            tasks(db, None, Some(agent), None)?;
            println!("\nInbox for {agent}\n");
            inbox(db, agent)?;
        } else {
            board(db, false, false)?;
        }
        thread::sleep(Duration::from_secs(every_seconds));
    }
}


/// Count data rows in a pipe-delimited table output (skips header and separator lines).
fn count_data_rows(output: &str) -> usize {
    output
        .lines()
        .filter(|line| {
            let trimmed = line.trim();
            !trimmed.is_empty()
                && !trimmed.chars().all(|c| c == '-' || c == '+' || c == ' ')
                && trimmed.contains('|')
        })
        .count()
        .saturating_sub(1) // subtract the header row
}

fn escape_sql(value: &str) -> String {
    value.replace('\'', "''")
}

fn build_tasks_query(from: Option<&str>, to: Option<&str>, status: Option<&str>) -> String {
    let mut query = "select * from tasks".to_string();
    let mut clauses = Vec::new();
    if let Some(from_agent) = from {
        clauses.push(format!("from_agent = '{}'", escape_sql(from_agent)));
    }
    if let Some(to_agent) = to {
        clauses.push(format!("to_agent = '{}'", escape_sql(to_agent)));
    }
    if let Some(task_status) = status {
        clauses.push(format!("status = '{}'", escape_sql(task_status)));
    }
    if !clauses.is_empty() {
        query.push_str(" where ");
        query.push_str(&clauses.join(" and "));
    }
    query
}

fn build_show_query(id: u64) -> String {
    format!("select * from tasks where id = {id}")
}

fn build_task_uuid_query(task_uuid: &str) -> String {
    format!(
        "select * from tasks where task_uuid = '{}'",
        escape_sql(task_uuid)
    )
}

fn build_session_ref(task_type: Option<&str>, session: &str) -> Result<String> {
    if let Some(kind) = task_type {
        let normalized = kind.trim().to_lowercase();
        match normalized.as_str() {
            "task" | "update" | "question" => {
                if session.contains(':') {
                    anyhow::bail!("--session should be an untyped suffix when --type is used");
                }
                Ok(format!("{}:{}", normalized, session.trim()))
            }
            _ => anyhow::bail!(
                "invalid --type '{}'; expected task, update, or question",
                kind
            ),
        }
    } else {
        Ok(session.to_string())
    }
}

fn parse_pipe_table(output: &str) -> Vec<Map<String, Value>> {
    let mut headers: Option<Vec<String>> = None;
    let mut rows = Vec::new();

    for raw_line in output.lines() {
        let line = raw_line.trim_end();
        if line.is_empty() || line.starts_with("WARNING:") {
            continue;
        }
        if !line.contains('|') {
            continue;
        }
        let stripped = line.replace('-', "").replace('+', "").trim().to_string();
        if stripped.is_empty() {
            continue;
        }

        let cells = line.split('|').map(normalize_cell).collect::<Vec<_>>();

        if headers.is_none() {
            headers = Some(cells);
            continue;
        }

        let mut row = Map::new();
        let known_headers = headers.as_ref().unwrap();
        for (header, value) in known_headers.iter().zip(cells.iter()) {
            row.insert(header.clone(), json_value_for_field(header, value));
        }
        rows.push(row);
    }

    rows
}

fn normalize_cell(value: &str) -> String {
    value.trim().trim_matches('"').to_string()
}

fn json_value_for_field(field: &str, value: &str) -> Value {
    match field {
        "id" | "priority" | "task_ref" | "created_at" | "updated_at" | "claimed_at"
        | "completed_at" | "current_task_id" | "last_heartbeat" | "last_seen" | "timestamp"
        | "count" | "original_task_id" | "archived_at" | "attempt_number" | "retry_count" | "parent_task_id" => {
            if field == "parent_task_id" {
                match parse_optional_u64(value) {
                    Some(parsed) => Value::from(parsed),
                    None => Value::Null,
                }
            } else {
                value
                    .parse::<u64>()
                    .map(Value::from)
                    .unwrap_or_else(|_| json!(value))
            }
        }
        "read" => value
            .parse::<bool>()
            .map(Value::from)
            .unwrap_or_else(|_| json!(value)),
        _ => json!(value),
    }
}

fn parse_optional_u64(value: &str) -> Option<u64> {
    let cleaned = value.trim();
    if cleaned.is_empty() || cleaned.eq_ignore_ascii_case("null") {
        return None;
    }
    if let Ok(parsed) = cleaned.parse::<u64>() {
        return Some(parsed);
    }
    let normalized = cleaned
        .trim_matches(|ch| matches!(ch, '(' | ')' | '{' | '}' | '[' | ']'))
        .trim();
    if let Some(rest) = normalized.strip_prefix("some =") {
        return rest.trim().parse::<u64>().ok();
    }
    if let Some(rest) = normalized.strip_prefix("some=") {
        return rest.trim().parse::<u64>().ok();
    }
    if let Some(rest) = normalized.strip_prefix("some:") {
        return rest.trim().parse::<u64>().ok();
    }
    None
}

fn render_board_json(db: &RelayDb, all: bool) -> Result<String> {
    let agents_output = db.sql("select name, handler_type, status, current_task_id, capabilities, last_heartbeat, last_seen from agents")?;
    let agents = parse_pipe_table(&agents_output);

    let active_output = db.sql("select * from tasks where status != 'done' and status != 'failed' and status != 'archived'")?;
    let active_tasks = parse_pipe_table(&active_output);

    let events_output = db.sql("select * from events")?;
    let mut recent_events = parse_pipe_table(&events_output);
    recent_events.sort_by_key(|row| {
        row.get("id")
            .and_then(|v| v.as_u64())
            .unwrap_or(0)
    });
    recent_events.reverse();
    recent_events.truncate(20);

    let active_count = active_tasks.len();

    // Always query done/failed and archived counts for the summary
    let done_failed_output = db.sql("select * from tasks where status = 'done' or status = 'failed'")?;
    let done_failed = parse_pipe_table(&done_failed_output);
    let done_failed_count = done_failed.len();

    let archived_output = db.sql("select * from archived_tasks")?;
    let archived = parse_pipe_table(&archived_output);
    let archived_count = archived.len();

    let mut board = json!({
        "agents": agents.into_iter().map(Value::Object).collect::<Vec<_>>(),
        "active_tasks": active_tasks.into_iter().map(Value::Object).collect::<Vec<_>>(),
        "recent_events": recent_events.into_iter().map(Value::Object).collect::<Vec<_>>(),
        "summary": {
            "active": active_count,
            "done_failed": done_failed_count,
            "archived": archived_count,
        },
    });

    if all {
        let map = board.as_object_mut().unwrap();
        map.insert("done_failed_tasks".to_string(), Value::Array(done_failed.into_iter().map(Value::Object).collect()));
        map.insert("archived_tasks".to_string(), Value::Array(archived.into_iter().map(Value::Object).collect()));
    }

    serde_json::to_string_pretty(&board).context("failed to serialize board JSON")
}

fn render_agents_json(output: &str) -> Result<String> {
    let rows = parse_pipe_table(output);
    let arr: Vec<Value> = rows.into_iter().map(Value::Object).collect();
    Ok(Value::Array(arr).to_string())
}

/// Sanitize a detail string for display: replace newlines/tabs with spaces,
/// collapse repeated whitespace, and truncate to `max_len` chars (appending "..."
/// when truncated).
fn sanitize_detail(s: &str, max_len: usize) -> String {
    let cleaned: String = s
        .chars()
        .map(|c| if c == '\n' || c == '\t' || c == '\r' { ' ' } else { c })
        .collect();
    let collapsed: String = cleaned
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ");
    if collapsed.len() > max_len {
        format!("{}...", &collapsed[..max_len])
    } else {
        collapsed
    }
}

fn render_recent_events_table(output: &str, limit: usize) -> Result<String> {
    let mut rows = parse_pipe_table(output);
    rows.sort_by_key(|row| {
        row.get("id")
            .and_then(|value| value.as_u64())
            .unwrap_or(0)
    });
    rows.reverse();
    rows.truncate(limit);

    // Sanitize the detail column for readability
    for row in rows.iter_mut() {
        if let Some(val) = row.get("detail").cloned() {
            let text = match &val {
                Value::String(s) => s.clone(),
                other => other.to_string(),
            };
            row.insert("detail".to_string(), Value::String(sanitize_detail(&text, 140)));
        }
    }

    render_pipe_table(
        &[
            "id",
            "event_type",
            "agent",
            "task_ref",
            "detail",
            "timestamp",
        ],
        &rows,
    )
}

fn render_pipe_table(headers: &[&str], rows: &[Map<String, Value>]) -> Result<String> {
    let header_strings = headers.iter().map(|header| header.to_string()).collect::<Vec<_>>();
    let mut widths = header_strings.iter().map(|header| header.len()).collect::<Vec<_>>();
    let mut rendered_rows = Vec::with_capacity(rows.len());

    for row in rows {
        let rendered = headers
            .iter()
            .enumerate()
            .map(|(index, header)| {
                let cell = render_value(row.get(*header).unwrap_or(&Value::Null));
                widths[index] = widths[index].max(cell.len());
                cell
            })
            .collect::<Vec<_>>();
        rendered_rows.push(rendered);
    }

    let header_line = join_pipe_row(&header_strings, &widths);
    let separator_line = widths
        .iter()
        .map(|width| "-".repeat(*width))
        .collect::<Vec<_>>()
        .join("-+-");

    let row_lines = rendered_rows
        .iter()
        .map(|row| join_pipe_row(row, &widths))
        .collect::<Vec<_>>();

    let mut lines = vec![header_line, separator_line];
    lines.extend(row_lines);
    Ok(lines.join("\n"))
}

fn join_pipe_row(cells: &[String], widths: &[usize]) -> String {
    cells.iter()
        .zip(widths.iter())
        .map(|(cell, width)| format!("{cell:<width$}", width = width))
        .collect::<Vec<_>>()
        .join(" | ")
}

fn render_value(value: &Value) -> String {
    match value {
        Value::Null => String::new(),
        Value::String(text) => format!("{text:?}"),
        Value::Number(number) => number.to_string(),
        Value::Bool(boolean) => boolean.to_string(),
        other => other.to_string(),
    }
}

fn render_show_json(output: &str) -> Result<String> {
    let rows = parse_pipe_table(output);
    let task = rows
        .into_iter()
        .next()
        .ok_or_else(|| anyhow::anyhow!("no task row found"))?;
    Ok(Value::Object(task).to_string())
}

fn render_post_json(task_uuid: &str, lookup_output: &str) -> Result<String> {
    let rows = parse_pipe_table(lookup_output);
    let task = rows
        .into_iter()
        .next()
        .ok_or_else(|| anyhow::anyhow!("could not resolve posted task by task_uuid"))?;
    let id = task
        .get("id")
        .cloned()
        .ok_or_else(|| anyhow::anyhow!("resolved task is missing id"))?;
    Ok(json!({ "task_uuid": task_uuid, "id": id }).to_string())
}

#[cfg(test)]
mod tests {
    use super::{
        build_session_ref, build_show_query, build_task_uuid_query, build_tasks_query, escape_sql,
        parse_pipe_table, render_agents_json, render_post_json, render_recent_events_table,
        render_show_json, sanitize_detail,
        validate_post_args, parse_optional_u64, json_value_for_field,
    };
    use serde_json::Value;

    #[test]
    fn escape_sql_escapes_single_quotes() {
        assert_eq!(escape_sql("o'reilly"), "o''reilly");
    }

    #[test]
    fn escape_sql_keeps_safe_text_unchanged() {
        assert_eq!(escape_sql("localmanus"), "localmanus");
    }

    #[test]
    fn build_tasks_query_includes_from_filter() {
        assert_eq!(
            build_tasks_query(Some("cowork-claude"), None, None),
            "select * from tasks where from_agent = 'cowork-claude'"
        );
    }

    #[test]
    fn build_tasks_query_combines_all_filters() {
        assert_eq!(
            build_tasks_query(Some("codex"), Some("cowork-claude"), Some("pending")),
            "select * from tasks where from_agent = 'codex' and to_agent = 'cowork-claude' and status = 'pending'"
        );
    }

    #[test]
    fn build_tasks_query_without_filters_selects_all() {
        assert_eq!(build_tasks_query(None, None, None), "select * from tasks");
    }

    #[test]
    fn build_session_ref_prefixes_type() {
        assert_eq!(
            build_session_ref(Some("update"), "sprint3").unwrap(),
            "update:sprint3"
        );
    }

    #[test]
    fn build_session_ref_leaves_legacy_session_when_type_absent() {
        assert_eq!(
            build_session_ref(None, "session-local").unwrap(),
            "session-local"
        );
    }

    #[test]
    fn build_session_ref_rejects_invalid_type() {
        assert!(build_session_ref(Some("note"), "sprint3").is_err());
    }

    #[test]
    fn build_session_ref_rejects_prefixed_session_when_type_is_used() {
        assert!(build_session_ref(Some("task"), "update:sprint3").is_err());
    }

    #[test]
    fn build_show_query_targets_single_task() {
        assert_eq!(build_show_query(7), "select * from tasks where id = 7");
    }

    #[test]
    fn build_task_uuid_query_escapes_value() {
        assert_eq!(
            build_task_uuid_query("abc"),
            "select * from tasks where task_uuid = 'abc'"
        );
    }

    #[test]
    fn parse_pipe_table_parses_numeric_and_string_fields() {
        let output = r#"id | task_uuid | status | priority
----+-----------+--------+---------
 7  | "uuid-7"  | "done" | 5
"#;
        let rows = parse_pipe_table(output);
        assert_eq!(rows.len(), 1);
        assert_eq!(rows[0]["id"], 7);
        assert_eq!(rows[0]["task_uuid"], "uuid-7");
        assert_eq!(rows[0]["status"], "done");
        assert_eq!(rows[0]["priority"], 5);
    }

    #[test]
    fn parse_pipe_table_parses_archive_specific_numeric_fields() {
        let output = r#"count | original_task_id | archived_at | retry_count
------+------------------+-------------+------------
 1    | 7                | 1234567890  | 2
"#;
        let rows = parse_pipe_table(output);
        assert_eq!(rows.len(), 1);
        assert_eq!(rows[0]["count"], 1);
        assert_eq!(rows[0]["original_task_id"], 7);
        assert_eq!(rows[0]["archived_at"], 1234567890u64);
        assert_eq!(rows[0]["retry_count"], 2);
    }

    #[test]
    fn render_show_json_returns_single_task_object() {
        let output = r#"id | task_uuid | status | priority | retry_count
----+-----------+--------+----------+------------
 7  | "uuid-7"  | "done" | 5        | 1
"#;
        let parsed: Value = serde_json::from_str(&render_show_json(output).unwrap()).unwrap();
        assert_eq!(parsed["id"], 7);
        assert_eq!(parsed["task_uuid"], "uuid-7");
        assert_eq!(parsed["status"], "done");
        assert_eq!(parsed["priority"], 5);
        assert_eq!(parsed["retry_count"], 1);
    }

    #[test]
    fn render_post_json_returns_id_and_task_uuid() {
        let output = r#"id | task_uuid | status | priority
----+-----------+--------+---------
 7  | "uuid-7"  | "pending" | 5
"#;
        let parsed: Value =
            serde_json::from_str(&render_post_json("uuid-7", output).unwrap()).unwrap();
        assert_eq!(parsed["task_uuid"], "uuid-7");
        assert_eq!(parsed["id"], 7);
    }

    #[test]
    fn render_agents_json_returns_array_of_agents() {
        let output = r#"name | handler_type | status | current_task_id | capabilities | last_heartbeat | last_seen
------+--------------+--------+-----------------+--------------+----------------+----------
 "codex" | "discord-bot" | "idle" | 0 | "code" | 1234567890 | 1234567890
 "claude" | "discord-bot" | "busy" | 3 | "reason" | 1234567891 | 1234567891
"#;
        let parsed: Value = serde_json::from_str(&render_agents_json(output).unwrap()).unwrap();
        assert!(parsed.is_array());
        let arr = parsed.as_array().unwrap();
        assert_eq!(arr.len(), 2);
        assert_eq!(arr[0]["name"], "codex");
        assert_eq!(arr[0]["status"], "idle");
        assert_eq!(arr[0]["current_task_id"], 0);
        assert_eq!(arr[1]["name"], "claude");
        assert_eq!(arr[1]["current_task_id"], 3);
    }

    #[test]
    fn validate_post_args_rejects_empty_title() {
        let err = validate_post_args("", "some payload").unwrap_err();
        assert!(err.to_string().contains("--title cannot be empty"));
    }

    #[test]
    fn validate_post_args_rejects_whitespace_only_title() {
        let err = validate_post_args("   ", "some payload").unwrap_err();
        assert!(err.to_string().contains("--title cannot be empty"));
    }

    #[test]
    fn validate_post_args_rejects_empty_payload() {
        let err = validate_post_args("some title", "").unwrap_err();
        assert!(err.to_string().contains("--payload cannot be empty"));
    }

    #[test]
    fn validate_post_args_rejects_whitespace_only_payload() {
        let err = validate_post_args("some title", "  	  ").unwrap_err();
        assert!(err.to_string().contains("--payload cannot be empty"));
    }

    #[test]
    fn validate_post_args_accepts_valid_inputs() {
        assert!(validate_post_args("review PR", "Please review").is_ok());
    }

    #[test]
    fn sanitize_detail_cleans_and_truncates() {
        // Newlines and tabs replaced with spaces, whitespace collapsed
        assert_eq!(sanitize_detail("hello\nworld\tfoo", 140), "hello world foo");

        // Repeated whitespace collapsed
        assert_eq!(sanitize_detail("a   b    c", 140), "a b c");

        // Mixed newlines, tabs, and repeated spaces
        assert_eq!(sanitize_detail("line1\n\n  line2\t\tline3", 140), "line1 line2 line3");

        // Truncation at 20 chars
        let long = "a]".repeat(100);
        let result = sanitize_detail(&long, 20);
        assert_eq!(result.len(), 23); // 20 + "..."
        assert!(result.ends_with("..."));

        // Short string unchanged
        assert_eq!(sanitize_detail("short", 140), "short");

        // Empty string
        assert_eq!(sanitize_detail("", 140), "");

        // Exactly at limit — no truncation
        let exact = "x".repeat(140);
        assert_eq!(sanitize_detail(&exact, 140), exact);
    }

    #[test]
    fn render_recent_events_sanitizes_detail_column() {
        let detail_with_whitespace = "hello   world";
        let output = format!(
            "id | event_type | agent | task_ref | detail | timestamp\n\
             ----+------------+-------+----------+--------+-----------\n\
              1  | \"test\"     | \"a\"   | 0        | \"{}\" | 100\n",
            detail_with_whitespace
        );
        let rendered = render_recent_events_table(&output, 10).unwrap();
        // The detail column should have collapsed whitespace
        assert!(rendered.contains("\"hello world\""));
        assert!(!rendered.contains("\"hello   world\""));
    }

    // ── Option encoding tests ──────────────────────────────────────────

    #[test]
    fn parse_optional_u64_returns_none_for_null() {
        assert_eq!(parse_optional_u64("null"), None);
        assert_eq!(parse_optional_u64("NULL"), None);
        assert_eq!(parse_optional_u64("  null  "), None);
    }

    #[test]
    fn parse_optional_u64_returns_none_for_empty() {
        assert_eq!(parse_optional_u64(""), None);
        assert_eq!(parse_optional_u64("   "), None);
    }

    #[test]
    fn parse_optional_u64_parses_plain_number() {
        assert_eq!(parse_optional_u64("42"), Some(42));
        assert_eq!(parse_optional_u64(" 7 "), Some(7));
        assert_eq!(parse_optional_u64("0"), Some(0));
    }

    #[test]
    fn parse_optional_u64_parses_some_equals_format() {
        assert_eq!(parse_optional_u64("{some = 99}"), Some(99));
        assert_eq!(parse_optional_u64("(some = 1)"), Some(1));
        assert_eq!(parse_optional_u64("[some = 123]"), Some(123));
    }

    #[test]
    fn parse_optional_u64_parses_some_equals_no_space() {
        assert_eq!(parse_optional_u64("{some=42}"), Some(42));
        assert_eq!(parse_optional_u64("(some=7)"), Some(7));
    }

    #[test]
    fn parse_optional_u64_parses_some_colon_format() {
        assert_eq!(parse_optional_u64("{some:10}"), Some(10));
        assert_eq!(parse_optional_u64("(some: 5)"), Some(5));
    }

    #[test]
    fn parse_optional_u64_returns_none_for_invalid_input() {
        assert_eq!(parse_optional_u64("abc"), None);
        assert_eq!(parse_optional_u64("{some = abc}"), None);
        assert_eq!(parse_optional_u64("{none}"), None);
    }

    #[test]
    fn json_value_for_parent_task_id_encodes_none_as_null() {
        let val = json_value_for_field("parent_task_id", "null");
        assert!(val.is_null(), "expected null, got {:?}", val);
    }

    #[test]
    fn json_value_for_parent_task_id_encodes_some_as_number() {
        let val = json_value_for_field("parent_task_id", "42");
        assert_eq!(val, 42);
    }

    #[test]
    fn json_value_for_parent_task_id_encodes_some_braced() {
        let val = json_value_for_field("parent_task_id", "{some = 7}");
        assert_eq!(val, 7);
    }

    #[test]
    fn option_none_encoding_matches_reducer_format() {
        // The post command sends "null" for Option::None — verify roundtrip
        let encoded = "null".to_string();
        assert_eq!(parse_optional_u64(&encoded), None);
        let json_val = json_value_for_field("parent_task_id", &encoded);
        assert!(json_val.is_null());
    }

    #[test]
    fn option_some_encoding_matches_reducer_format() {
        // The retry command encodes Option::Some(id) as {"some":id}
        let root_parent: u64 = 42;
        let encoded = format!("{{\"some\":{root_parent}}}");
        assert_eq!(encoded, "{\"some\":42}");
        // Verify the parse side can read the some= variant from SpacetimeDB output
        let spacetime_output = format!("{{some = {root_parent}}}");
        assert_eq!(parse_optional_u64(&spacetime_output), Some(42));
    }

    #[test]
    fn parse_pipe_table_handles_parent_task_id_null() {
        let output = "id | parent_task_id | status\n\
                       ----+---------------+--------\n\
                        1  | null          | \"done\"\n";
        let rows = parse_pipe_table(output);
        assert_eq!(rows.len(), 1);
        assert!(rows[0]["parent_task_id"].is_null());
    }

    #[test]
    fn parse_pipe_table_handles_parent_task_id_some() {
        let output = "id | parent_task_id | status\n\
                       ----+---------------+--------\n\
                        1  | 42            | \"done\"\n";
        let rows = parse_pipe_table(output);
        assert_eq!(rows.len(), 1);
        assert_eq!(rows[0]["parent_task_id"], 42);
    }

    #[test]
    fn parse_pipe_table_handles_parent_task_id_some_braced() {
        let output = "id | parent_task_id | status\n\
                       ----+---------------+--------\n\
                        1  | {some = 7}    | \"done\"\n";
        let rows = parse_pipe_table(output);
        assert_eq!(rows.len(), 1);
        assert_eq!(rows[0]["parent_task_id"], 7);
    }

    #[test]
    fn relay_show_json_preserves_retry_count_on_task_row() {
        // Simulate a task row with retry_count = 3, as returned by `relay show <id> --json`.
        let output = r#"id | task_uuid | status | priority | retry_count | from_agent | to_agent
----+-----------+--------+----------+-------------+------------+---------
 42 | "abc-def" | "in_progress" | 2  | 3           | "alice"    | "bob"
"#;
        let json_str = render_show_json(output).expect("render_show_json should succeed");
        let parsed: Value = serde_json::from_str(&json_str).expect("output must be valid JSON");

        // The key assertion: retry_count must survive the JSON round-trip as a number.
        assert_eq!(
            parsed.get("retry_count").expect("retry_count key must exist"),
            &Value::from(3),
            "retry_count should be preserved as the integer 3"
        );
        // Sanity-check neighbouring fields.
        assert_eq!(parsed["id"], 42);
        assert_eq!(parsed["status"], "in_progress");
    }

    #[test]
    fn retry_probe_intentional_failure() {
        // Verify that retry_count is parsed as a JSON number and survives
        // the render_show_json round-trip correctly.
        let output = r#"id | task_uuid | status | priority | retry_count | from_agent | to_agent
----+-----------+--------+----------+-------------+------------+---------
 99 | "uuid-99" | "failed" | 3      | 5           | "alice"    | "bob"
"#;
        let rows = parse_pipe_table(output);
        assert_eq!(rows.len(), 1);
        assert_eq!(
            rows[0].get("retry_count").expect("retry_count must exist"),
            &serde_json::json!(5),
            "retry_count should be parsed as numeric 5"
        );

        // Also verify it round-trips through render_show_json
        let json_str = render_show_json(output).expect("render_show_json should succeed");
        let parsed: Value = serde_json::from_str(&json_str).unwrap();
        assert_eq!(
            parsed.get("retry_count").expect("retry_count key in JSON output"),
            &serde_json::json!(5),
            "retry_count must be preserved as integer 5 in JSON output"
        );
    }
}

pub fn session_end(
    summary: Option<&str>,
    agent: Option<&str>,
    last: u32,
    blockers: &str,
    json_output: bool,
) -> Result<()> {
    // Resolve path to session_capture.py relative to the relay binary or cwd
    let script = find_session_capture_script();

    let mut cmd = std::process::Command::new("python3");
    cmd.arg(&script);

    if let Some(s) = summary {
        cmd.arg("--summary").arg(s);
    }
    if let Some(a) = agent {
        cmd.arg("--agent").arg(a);
    }
    cmd.arg("--last").arg(last.to_string());
    cmd.arg("--blockers").arg(blockers);
    if json_output {
        cmd.arg("--json");
    }

    let status = cmd
        .stdin(std::process::Stdio::inherit())
        .stdout(std::process::Stdio::inherit())
        .stderr(std::process::Stdio::inherit())
        .status()?;

    if !status.success() {
        anyhow::bail!("session_capture.py exited with {}", status);
    }
    Ok(())
}

fn find_session_capture_script() -> std::path::PathBuf {
    // Try a few conventional locations
    let candidates = [
        // Relative to current working dir
        std::path::PathBuf::from("scripts/session_capture.py"),
        // Relative to the relay-room project root via env
        std::env::var("RELAY_ROOM_ROOT")
            .map(|r| std::path::PathBuf::from(r).join("scripts/session_capture.py"))
            .unwrap_or_default(),
        // Walk up from cwd looking for scripts/session_capture.py
        find_in_ancestors("scripts/session_capture.py").unwrap_or_default(),
    ];

    for c in &candidates {
        if c.is_file() {
            return c.clone();
        }
    }

    // Last resort — assume it's on PATH or in scripts/
    std::path::PathBuf::from("scripts/session_capture.py")
}

fn find_in_ancestors(relative: &str) -> Option<std::path::PathBuf> {
    let cwd = std::env::current_dir().ok()?;
    for dir in cwd.ancestors() {
        let candidate = dir.join(relative);
        if candidate.is_file() {
            return Some(candidate);
        }
    }
    None
}

#[cfg(test)]
mod option_encoding_tests {
    use super::{json_value_for_field, parse_optional_u64};
    use serde_json::Value;

    // ── parse_optional_u64 ──

    #[test]
    fn parse_optional_u64_returns_none_for_null() {
        assert_eq!(parse_optional_u64("null"), None);
        assert_eq!(parse_optional_u64("NULL"), None);
        assert_eq!(parse_optional_u64("Null"), None);
    }

    #[test]
    fn parse_optional_u64_returns_none_for_empty() {
        assert_eq!(parse_optional_u64(""), None);
        assert_eq!(parse_optional_u64("  "), None);
    }

    #[test]
    fn parse_optional_u64_parses_plain_number() {
        assert_eq!(parse_optional_u64("42"), Some(42));
        assert_eq!(parse_optional_u64("0"), Some(0));
        assert_eq!(parse_optional_u64(" 7 "), Some(7));
    }

    #[test]
    fn parse_optional_u64_handles_some_equals() {
        assert_eq!(parse_optional_u64("some = 99"), Some(99));
        assert_eq!(parse_optional_u64("some=99"), Some(99));
    }

    #[test]
    fn parse_optional_u64_handles_some_colon() {
        assert_eq!(parse_optional_u64("some: 5"), Some(5));
        assert_eq!(parse_optional_u64("some:5"), Some(5));
    }

    #[test]
    fn parse_optional_u64_strips_braces_and_brackets() {
        assert_eq!(parse_optional_u64("{some = 10}"), Some(10));
        assert_eq!(parse_optional_u64("[some = 10]"), Some(10));
        assert_eq!(parse_optional_u64("(some = 10)"), Some(10));
    }

    #[test]
    fn parse_optional_u64_returns_none_for_garbage() {
        assert_eq!(parse_optional_u64("abc"), None);
        assert_eq!(parse_optional_u64("some = xyz"), None);
    }

    // ── json_value_for_field (parent_task_id) ──

    #[test]
    fn json_value_for_parent_task_id_null() {
        assert_eq!(json_value_for_field("parent_task_id", "null"), Value::Null);
        assert_eq!(json_value_for_field("parent_task_id", ""), Value::Null);
    }

    #[test]
    fn json_value_for_parent_task_id_some() {
        assert_eq!(json_value_for_field("parent_task_id", "42"), Value::from(42u64));
        assert_eq!(json_value_for_field("parent_task_id", "some = 7"), Value::from(7u64));
    }

    #[test]
    fn json_value_for_regular_numeric_field() {
        // Non-option numeric fields should parse normally
        assert_eq!(json_value_for_field("id", "10"), Value::from(10u64));
        assert_eq!(json_value_for_field("priority", "5"), Value::from(5u64));
    }

    // ── Encoding format used in post / retry ──

    #[test]
    fn post_encodes_none_as_null_string() {
        // post() passes "null" for parent_task_id (no parent)
        let encoded = "null".to_string();
        assert_eq!(encoded, "null");
    }

    #[test]
    fn retry_encodes_some_as_json_object() {
        // retry() passes {"some":N} for parent_task_id
        let root_parent: u64 = 42;
        let encoded = format!("{{\"some\":{root_parent}}}");
        assert_eq!(encoded, r#"{"some":42}"#);
    }

    // ── parse_pipe_table round-trip with parent_task_id ──

    #[test]
    fn pipe_table_parent_task_id_null_roundtrip() {
        use super::parse_pipe_table;
        let output = "id | parent_task_id | status\n\
                       ----+---------------+--------\n\
                        1  | null          | \"done\"\n";
        let rows = parse_pipe_table(output);
        assert_eq!(rows.len(), 1);
        assert_eq!(rows[0]["parent_task_id"], Value::Null);
    }

    #[test]
    fn pipe_table_parent_task_id_some_roundtrip() {
        use super::parse_pipe_table;
        let output = "id | parent_task_id | status\n\
                       ----+---------------+--------\n\
                        2  | 7             | \"done\"\n";
        let rows = parse_pipe_table(output);
        assert_eq!(rows.len(), 1);
        assert_eq!(rows[0]["parent_task_id"], Value::from(7u64));
    }

    #[test]
    fn pipe_table_parent_task_id_some_equals_form() {
        use super::parse_pipe_table;
        let output = "id | parent_task_id | status\n\
                       ----+---------------+--------\n\
                        3  | some = 42     | \"pending\"\n";
        let rows = parse_pipe_table(output);
        assert_eq!(rows.len(), 1);
        assert_eq!(rows[0]["parent_task_id"], Value::from(42u64));
    }

    #[test]
    fn validate_requeue_args_accepts_owned_in_progress_task() {
        assert!(super::validate_requeue_args("in_progress", "manuslocal", "manuslocal", 4).is_ok());
    }

    #[test]
    fn validate_requeue_args_rejects_non_in_progress_task() {
        let err = super::validate_requeue_args("pending", "manuslocal", "manuslocal", 4)
            .unwrap_err()
            .to_string();
        assert!(err.contains("must be in_progress"));
    }

    #[test]
    fn validate_requeue_args_rejects_wrong_owner() {
        let err = super::validate_requeue_args("in_progress", "relay-dispatch", "manuslocal", 4)
            .unwrap_err()
            .to_string();
        assert!(err.contains("owned by relay-dispatch"));
    }
}

pub fn task_log(db: &RelayDb, id: u64, dispatch_log: &str, task_log_path: Option<&str>, json: bool) -> Result<()> {
    use std::fs;
    use std::io::{BufRead, BufReader};
    use std::path::Path;

    let id_str = id.to_string();
    let mut found_lines = Vec::new();

    // 1. Try the dispatch log: grep for lines mentioning the task ID
    let dispatch_path = Path::new(dispatch_log);
    if dispatch_path.is_file() {
        if let Ok(file) = fs::File::open(dispatch_path) {
            let reader = BufReader::new(file);
            for line in reader.lines() {
                if let Ok(line) = line {
                    // Match lines containing "task <id>" pattern
                    if line.contains(&format!("task {id_str}"))
                        || line.contains(&format!("task_id={id_str}"))
                        || line.contains(&format!("task={id_str}"))
                    {
                        found_lines.push(line);
                    }
                }
            }
        }
    }

    // 2. Fall back (or supplement) with per-task log file
    let default_task_log = format!("/tmp/relay_dispatch_task_{}.log", id);
    let task_file = task_log_path.unwrap_or(&default_task_log);
    let task_path = Path::new(task_file);

    let fallback_contents = if task_path.is_file() {
        fs::read_to_string(task_path)
            .with_context(|| format!("failed to read task log: {}", task_file))?
    } else {
        String::new()
    };
    let fallback_lines: Vec<&str> = if fallback_contents.trim().is_empty() {
        Vec::new()
    } else {
        fallback_contents.lines().collect()
    };

    if json {
        let show_output = db.sql(&build_show_query(id))?;
        let retry_count = parse_pipe_table(&show_output)
            .into_iter()
            .next()
            .and_then(|row| row.get("retry_count").and_then(|value| value.as_u64()))
            .unwrap_or(0);
        // Build structured JSON output
        let dispatch_matches: Vec<serde_json::Value> = found_lines
            .iter()
            .map(|l| serde_json::Value::String(l.clone()))
            .collect();
        let fallback_log_lines: Vec<serde_json::Value> = fallback_lines
            .iter()
            .map(|l| serde_json::Value::String(l.to_string()))
            .collect();

        let mut obj = serde_json::Map::new();
        obj.insert("task_id".to_string(), serde_json::json!(id));
        obj.insert("retry_count".to_string(), serde_json::json!(retry_count));
        obj.insert("dispatch_match_count".to_string(), serde_json::json!(dispatch_matches.len()));
        obj.insert("dispatch_matches".to_string(), serde_json::Value::Array(dispatch_matches));

        // Fallback log metadata
        let mut fallback = serde_json::Map::new();
        fallback.insert("path".to_string(), serde_json::json!(task_file));
        fallback.insert("exists".to_string(), serde_json::json!(task_path.is_file()));
        fallback.insert("line_count".to_string(), serde_json::json!(fallback_log_lines.len()));
        if task_path.is_file() {
            if let Ok(meta) = fs::metadata(task_path) {
                fallback.insert("size_bytes".to_string(), serde_json::json!(meta.len()));
            }
        }
        fallback.insert("lines".to_string(), serde_json::Value::Array(fallback_log_lines));
        obj.insert("fallback_log".to_string(), serde_json::Value::Object(fallback));

        println!("{}", serde_json::to_string_pretty(&serde_json::Value::Object(obj))?);
        return Ok(());
    }

    // Human-readable output (unchanged behaviour)
    let show_output = db.sql(&build_show_query(id))?;
    let retry_count = parse_pipe_table(&show_output)
        .into_iter()
        .next()
        .and_then(|row| row.get("retry_count").and_then(|value| value.as_u64()))
        .unwrap_or(0);
    println!("retry_count: {}", retry_count);
    if !found_lines.is_empty() || !fallback_lines.is_empty() {
        println!();
    }
    if !found_lines.is_empty() {
        println!("=== Dispatch log entries for task {} ===", id);
        for line in &found_lines {
            println!("{}", line);
        }
    }

    if !fallback_lines.is_empty() {
        if !found_lines.is_empty() {
            println!();
        }
        println!("=== Per-task log: {} ===", task_file);
        print!("{}", fallback_contents);
        if !fallback_contents.ends_with('\n') {
            println!();
        }
    } else if found_lines.is_empty() {
        println!("No log entries found for task {}", id);
        println!(
            "  dispatch log: {} ({})",
            dispatch_log,
            if dispatch_path.is_file() {
                "exists, no matching entries"
            } else {
                "not found"
            }
        );
        println!(
            "  task log:     {} (not found)",
            task_file
        );
    }

    Ok(())
}
