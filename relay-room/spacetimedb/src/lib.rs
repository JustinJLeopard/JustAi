use spacetimedb::{ReducerContext, Table, table};

#[table(accessor = tasks, public)]
pub struct Task {
    #[primary_key]
    #[auto_inc]
    pub id: u64,
    pub task_uuid: String,
    pub from_agent: String,
    pub to_agent: String,
    pub claimed_by: String,
    pub title: String,
    pub payload: String,
    pub status: String,
    pub priority: u8,
    pub session_ref: String,
    pub attempt_number: u32,
    pub retry_count: u32,
    pub parent_task_id: Option<u64>,
    pub created_at: u64,
    pub updated_at: u64,
    pub claimed_at: u64,
    pub completed_at: u64,
    pub result: String,
}

#[table(accessor = agents, public)]
pub struct Agent {
    #[primary_key]
    pub name: String,
    pub handler_type: String,
    pub status: String,
    pub current_task_id: u64,
    pub capabilities: String,
    pub last_heartbeat: u64,
    pub last_seen: u64,
}

#[table(accessor = messages, public)]
pub struct Message {
    #[primary_key]
    #[auto_inc]
    pub id: u64,
    pub from_agent: String,
    pub to_agent: String,
    pub content: String,
    pub task_ref: u64,
    pub timestamp: u64,
    pub read: bool,
}

#[table(accessor = events, public)]
pub struct Event {
    #[primary_key]
    #[auto_inc]
    pub id: u64,
    pub event_type: String,
    pub agent: String,
    pub task_ref: u64,
    pub detail: String,
    pub timestamp: u64,
}

fn now_ms(ctx: &ReducerContext) -> u64 {
    (ctx.timestamp.to_micros_since_unix_epoch() / 1000) as u64
}

fn log_event(ctx: &ReducerContext, event_type: &str, agent: &str, task_ref: u64, detail: &str) {
    ctx.db.events().insert(Event {
        id: 0,
        event_type: event_type.to_string(),
        agent: agent.to_string(),
        task_ref,
        detail: detail.to_string(),
        timestamp: now_ms(ctx),
    });
}

#[spacetimedb::reducer]
pub fn register_agent(
    ctx: &ReducerContext,
    name: String,
    handler_type: String,
    capabilities: String,
) {
    let ts = now_ms(ctx);
    if let Some(existing) = ctx.db.agents().name().find(&name) {
        ctx.db.agents().name().update(Agent {
            handler_type,
            capabilities,
            last_heartbeat: ts,
            last_seen: ts,
            ..existing
        });
    } else {
        ctx.db.agents().insert(Agent {
            name: name.clone(),
            handler_type,
            status: "online".to_string(),
            current_task_id: 0,
            capabilities,
            last_heartbeat: ts,
            last_seen: ts,
        });
        log_event(ctx, "agent_registered", &name, 0, "");
    }
}

#[spacetimedb::reducer]
pub fn heartbeat(ctx: &ReducerContext, agent: String) {
    let ts = now_ms(ctx);
    if let Some(a) = ctx.db.agents().name().find(&agent) {
        ctx.db.agents().name().update(Agent {
            last_heartbeat: ts,
            last_seen: ts,
            ..a
        });
    }
}

#[spacetimedb::reducer]
pub fn set_agent_status(ctx: &ReducerContext, agent: String, status: String, current_task: u64) {
    let ts = now_ms(ctx);
    if let Some(a) = ctx.db.agents().name().find(&agent) {
        ctx.db.agents().name().update(Agent {
            status: status.clone(),
            current_task_id: current_task,
            last_seen: ts,
            ..a
        });
        log_event(ctx, "agent_status_changed", &agent, current_task, &status);
    }
}

#[spacetimedb::reducer]
pub fn post_task(
    ctx: &ReducerContext,
    from_agent: String,
    to_agent: String,
    title: String,
    payload: String,
    priority: u8,
    session_ref: String,
    task_uuid: String,
    attempt_number: u32,
    parent_task_id: Option<u64>,
) {
    let ts = now_ms(ctx);
    let task = ctx.db.tasks().insert(Task {
        id: 0,
        task_uuid: task_uuid.clone(),
        from_agent: from_agent.clone(),
        to_agent,
        claimed_by: String::new(),
        title: title.clone(),
        payload,
        status: "pending".to_string(),
        priority,
        session_ref,
        attempt_number,
        retry_count: 0,
        parent_task_id,
        created_at: ts,
        updated_at: ts,
        claimed_at: 0,
        completed_at: 0,
        result: String::new(),
    });
    log_event(ctx, "task_created", &from_agent, task.id, &title);
}

#[spacetimedb::reducer]
pub fn claim_task(ctx: &ReducerContext, task_id: u64, agent: String) -> Result<(), String> {
    let ts = now_ms(ctx);
    let task = ctx
        .db
        .tasks()
        .id()
        .find(&task_id)
        .ok_or_else(|| format!("task {} not found", task_id))?;
    if task.status != "pending" {
        return Err(format!(
            "task {} is not pending (status: {})",
            task_id, task.status
        ));
    }
    ctx.db.tasks().id().update(Task {
        status: "claimed".to_string(),
        claimed_by: agent.clone(),
        claimed_at: ts,
        updated_at: ts,
        ..task
    });
    log_event(ctx, "task_claimed", &agent, task_id, "");
    Ok(())
}

#[spacetimedb::reducer]
pub fn start_task(ctx: &ReducerContext, task_id: u64, agent: String) -> Result<(), String> {
    let ts = now_ms(ctx);
    let task = ctx
        .db
        .tasks()
        .id()
        .find(&task_id)
        .ok_or_else(|| format!("task {} not found", task_id))?;
    if task.status != "claimed" {
        return Err(format!("task {} is not claimed", task_id));
    }
    if task.claimed_by != agent {
        return Err(format!(
            "task {} is claimed by {}, not {}",
            task_id, task.claimed_by, agent
        ));
    }
    ctx.db.tasks().id().update(Task {
        status: "in_progress".to_string(),
        updated_at: ts,
        ..task
    });
    log_event(ctx, "task_started", &agent, task_id, "");
    Ok(())
}

#[spacetimedb::reducer]
pub fn complete_task(
    ctx: &ReducerContext,
    task_id: u64,
    agent: String,
    result: String,
) -> Result<(), String> {
    let ts = now_ms(ctx);
    let task = ctx
        .db
        .tasks()
        .id()
        .find(&task_id)
        .ok_or_else(|| format!("task {} not found", task_id))?;
    if task.status != "in_progress" {
        return Err(format!("task {} is not in_progress", task_id));
    }
    if task.claimed_by != agent {
        return Err(format!("task {} is owned by {}", task_id, task.claimed_by));
    }
    ctx.db.tasks().id().update(Task {
        status: "done".to_string(),
        result: result.clone(),
        completed_at: ts,
        updated_at: ts,
        ..task
    });
    log_event(ctx, "task_done", &agent, task_id, &result);
    Ok(())
}

#[spacetimedb::reducer]
pub fn fail_task(
    ctx: &ReducerContext,
    task_id: u64,
    agent: String,
    error: String,
) -> Result<(), String> {
    let ts = now_ms(ctx);
    let task = ctx
        .db
        .tasks()
        .id()
        .find(&task_id)
        .ok_or_else(|| format!("task {} not found", task_id))?;
    if task.claimed_by != agent {
        return Err(format!("task {} is owned by {}", task_id, task.claimed_by));
    }
    ctx.db.tasks().id().update(Task {
        status: "failed".to_string(),
        result: error.clone(),
        completed_at: ts,
        updated_at: ts,
        ..task
    });
    log_event(ctx, "task_failed", &agent, task_id, &error);
    Ok(())
}

#[spacetimedb::reducer]
pub fn requeue_task(
    ctx: &ReducerContext,
    task_id: u64,
    agent: String,
    error: String,
) -> Result<(), String> {
    let ts = now_ms(ctx);
    let task = ctx
        .db
        .tasks()
        .id()
        .find(&task_id)
        .ok_or_else(|| format!("task {} not found", task_id))?;
    if task.status != "in_progress" {
        return Err(format!(
            "task {} is not in_progress (status: {})",
            task_id, task.status
        ));
    }
    if task.claimed_by != agent {
        return Err(format!("task {} is owned by {}", task_id, task.claimed_by));
    }
    let next_retry = task.retry_count.saturating_add(1);
    let next_attempt = task.attempt_number.saturating_add(1);
    ctx.db.tasks().id().update(Task {
        status: "pending".to_string(),
        claimed_by: String::new(),
        updated_at: ts,
        claimed_at: 0,
        completed_at: 0,
        result: error.clone(),
        attempt_number: next_attempt,
        retry_count: next_retry,
        ..task
    });
    log_event(
        ctx,
        "task_requeued",
        &agent,
        task_id,
        &format!("retry {}: {}", next_retry, error),
    );
    Ok(())
}

#[spacetimedb::reducer]
pub fn send_message(
    ctx: &ReducerContext,
    from_agent: String,
    to_agent: String,
    content: String,
    task_ref: u64,
) {
    let ts = now_ms(ctx);
    ctx.db.messages().insert(Message {
        id: 0,
        from_agent: from_agent.clone(),
        to_agent: to_agent.clone(),
        content: content.clone(),
        task_ref,
        timestamp: ts,
        read: false,
    });
    log_event(
        ctx,
        "message_sent",
        &from_agent,
        task_ref,
        &format!("to:{}", to_agent),
    );
}

#[spacetimedb::reducer]
pub fn mark_read(ctx: &ReducerContext, message_id: u64) -> Result<(), String> {
    let msg = ctx
        .db
        .messages()
        .id()
        .find(&message_id)
        .ok_or_else(|| format!("message {} not found", message_id))?;
    ctx.db.messages().id().update(Message { read: true, ..msg });
    Ok(())
}

#[table(accessor = archived_tasks, public)]
pub struct ArchivedTask {
    #[primary_key]
    #[auto_inc]
    pub id: u64,
    pub original_task_id: u64,
    pub task_uuid: String,
    pub from_agent: String,
    pub to_agent: String,
    pub claimed_by: String,
    pub title: String,
    pub payload: String,
    pub status: String,
    pub priority: u8,
    pub session_ref: String,
    pub attempt_number: u32,
    pub retry_count: u32,
    pub parent_task_id: Option<u64>,
    pub created_at: u64,
    pub updated_at: u64,
    pub claimed_at: u64,
    pub completed_at: u64,
    pub result: String,
    pub archived_at: u64,
}

#[spacetimedb::reducer]
pub fn archive_task(ctx: &ReducerContext, task_id: u64) -> Result<(), String> {
    let ts = now_ms(ctx);
    let task = ctx
        .db
        .tasks()
        .id()
        .find(&task_id)
        .ok_or_else(|| format!("task {} not found", task_id))?;
    if task.status != "done" && task.status != "failed" {
        return Err(format!(
            "task {} has status '{}'; only done or failed tasks can be archived",
            task_id, task.status
        ));
    }
    ctx.db.archived_tasks().insert(ArchivedTask {
        id: 0,
        original_task_id: task.id,
        task_uuid: task.task_uuid.clone(),
        from_agent: task.from_agent.clone(),
        to_agent: task.to_agent.clone(),
        claimed_by: task.claimed_by.clone(),
        title: task.title.clone(),
        payload: task.payload.clone(),
        status: task.status.clone(),
        priority: task.priority,
        session_ref: task.session_ref.clone(),
        attempt_number: task.attempt_number,
        retry_count: task.retry_count,
        parent_task_id: task.parent_task_id,
        created_at: task.created_at,
        updated_at: task.updated_at,
        claimed_at: task.claimed_at,
        completed_at: task.completed_at,
        result: task.result.clone(),
        archived_at: ts,
    });
    ctx.db.tasks().id().delete(&task_id);
    log_event(ctx, "task_archived", &task.from_agent, task_id, &task.title);
    Ok(())
}
