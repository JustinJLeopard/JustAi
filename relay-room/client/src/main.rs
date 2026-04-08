mod commands;
mod db;

use anyhow::Result;
use clap::{Args, Parser, Subcommand};
use db::RelayDb;

#[derive(Parser, Debug)]
#[command(name = "relay", about = "CLI for the Relay Room local agent board")]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand, Debug)]
enum Command {
    Register(RegisterArgs),
    Agents(AgentsArgs),
    Heartbeat(AgentArgs),
    AgentStatus(AgentStatusArgs),
    Status,
    Board(BoardArgs),
    Tasks(TasksArgs),
    Show(ShowArgs),
    Inbox(InboxArgs),
    Post(PostArgs),
    Retry(RetryArgs),
    Requeue(RequeueArgs),
    Claim(TaskActorArgs),
    Start(TaskActorArgs),
    Done(DoneArgs),
    Fail(FailArgs),
    Msg(MessageArgs),
    Watch(WatchArgs),
    Archive(ArchiveArgs),
    SessionEnd(SessionEndArgs),
    /// Print the dispatch log for a task
    TaskLog(TaskLogArgs),
}

#[derive(Args, Debug)]
struct BoardArgs {
    /// Show all tasks including done, failed, and archived
    #[arg(long)]
    all: bool,
    /// Output board state as JSON
    #[arg(long)]
    json: bool,
}

#[derive(Args, Debug)]
struct RegisterArgs {
    agent: String,
    #[arg(long = "handler-type", default_value = "discord-bot")]
    handler_type: String,
    #[arg(long = "caps", default_value = "")]
    caps: String,
}

#[derive(Args, Debug)]
struct AgentsArgs {
    #[arg(long)]
    json: bool,
    /// Output format: table (default) or json
    #[arg(long, value_parser = ["table", "json"])]
    format: Option<String>,
}

#[derive(Args, Debug)]
struct AgentArgs {
    agent: String,
}

#[derive(Args, Debug)]
struct AgentStatusArgs {
    agent: String,
    #[arg(long)]
    status: String,
    #[arg(long = "task", default_value_t = 0)]
    current_task: u64,
}

#[derive(Args, Debug)]
struct TasksArgs {
    #[arg(long = "from")]
    from_agent: Option<String>,
    #[arg(long = "to")]
    to_agent: Option<String>,
    #[arg(long)]
    status: Option<String>,
}

#[derive(Args, Debug)]
struct InboxArgs {
    agent: String,
}

#[derive(Args, Debug)]
struct ShowArgs {
    id: u64,
    #[arg(long)]
    json: bool,
}

#[derive(Args, Debug)]
struct PostArgs {
    #[arg(long)]
    from: String,
    #[arg(long)]
    to: String,
    #[arg(long)]
    title: String,
    #[arg(long, default_value = "")]
    payload: String,
    #[arg(long, default_value_t = 5)]
    priority: u8,
    #[arg(long = "type", value_name = "task|update|question")]
    task_type: Option<String>,
    #[arg(long, default_value = "session-local")]
    session: String,
    #[arg(long)]
    json: bool,
}

#[derive(Args, Debug)]
struct RetryArgs {
    id: u64,
    #[arg(long)]
    json: bool,
}

#[derive(Args, Debug)]
struct RequeueArgs {
    id: u64,
    #[arg(long = "as")]
    agent: String,
    #[arg(long)]
    error: String,
}

#[derive(Args, Debug)]
struct TaskActorArgs {
    id: u64,
    #[arg(long = "as")]
    agent: String,
}

#[derive(Args, Debug)]
struct DoneArgs {
    id: u64,
    #[arg(long = "as")]
    agent: String,
    #[arg(long)]
    result: String,
}

#[derive(Args, Debug)]
struct FailArgs {
    id: u64,
    #[arg(long = "as")]
    agent: String,
    #[arg(long)]
    error: String,
}

#[derive(Args, Debug)]
struct MessageArgs {
    #[arg(long)]
    from: String,
    #[arg(long)]
    to: String,
    #[arg(long)]
    content: String,
    #[arg(long, default_value_t = 0)]
    task_ref: u64,
}

#[derive(Args, Debug)]
struct WatchArgs {
    #[arg(long = "agent")]
    to_agent: Option<String>,
    #[arg(long, default_value_t = 3)]
    every: u64,
}

#[derive(Args, Debug)]
struct ArchiveArgs {
    /// Task ID to archive (omit to archive done/failed tasks older than 24h)
    id: Option<u64>,
    /// Archive all done/failed tasks regardless of age
    #[arg(long)]
    all: bool,
    /// Preview which tasks would be archived without actually archiving
    #[arg(long)]
    dry_run: bool,
    /// List all archived tasks
    #[arg(long, conflicts_with_all = ["id", "all", "dry_run", "count"])]
    list: bool,
    /// Show count of archived tasks
    #[arg(long, conflicts_with_all = ["id", "all", "dry_run", "list"])]
    count: bool,
    #[arg(long)]
    json: bool,
}


#[derive(Args, Debug)]
struct SessionEndArgs {
    /// Optional human-written session summary
    #[arg(long, short)]
    summary: Option<String>,
    /// Filter tasks to this agent
    #[arg(long = "as")]
    agent: Option<String>,
    /// Number of recent tasks to include
    #[arg(long, default_value_t = 50)]
    last: u32,
    /// Current blockers
    #[arg(long, short, default_value = "none")]
    blockers: String,
    /// Output JSON only (no persistence)
    #[arg(long)]
    json: bool,
}

#[derive(Args, Debug)]
struct TaskLogArgs {
    /// Task ID to show logs for
    id: u64,
    /// Path to the dispatch log file
    #[arg(long, default_value = "/tmp/relay_dispatch.log")]
    dispatch_log: String,
    /// Path to per-task log file (default: /tmp/relay_dispatch_task_<id>.log)
    #[arg(long)]
    task_log: Option<String>,
    /// Output structured JSON
    #[arg(long)]
    json: bool,
}
fn main() -> Result<()> {
    let cli = Cli::parse();
    let db = RelayDb::from_env();

    match cli.command {
        Command::Register(args) => {
            commands::register(&db, &args.agent, &args.handler_type, &args.caps)
        }
        Command::Agents(args) => {
            let json_output = args.json || args.format.as_deref() == Some("json");
            commands::agents(&db, json_output)
        }
        Command::Heartbeat(args) => commands::heartbeat(&db, &args.agent),
        Command::AgentStatus(args) => {
            commands::agent_status(&db, &args.agent, &args.status, args.current_task)
        }
        Command::Status => commands::status(&db),
        Command::Board(args) => commands::board(&db, args.all, args.json),
        Command::Tasks(args) => commands::tasks(
            &db,
            args.from_agent.as_deref(),
            args.to_agent.as_deref(),
            args.status.as_deref(),
        ),
        Command::Show(args) => commands::show(&db, args.id, args.json),
        Command::Inbox(args) => commands::inbox(&db, &args.agent),
        Command::Post(args) => commands::post(
            &db,
            &args.from,
            &args.to,
            &args.title,
            &args.payload,
            args.priority,
            args.task_type.as_deref(),
            &args.session,
            args.json,
        ),
        Command::Retry(args) => commands::retry(&db, args.id, args.json),
        Command::Requeue(args) => commands::requeue(&db, args.id, &args.agent, &args.error),
        Command::Claim(args) => commands::claim(&db, args.id, &args.agent),
        Command::Start(args) => commands::start(&db, args.id, &args.agent),
        Command::Done(args) => commands::done(&db, args.id, &args.agent, &args.result),
        Command::Fail(args) => commands::fail(&db, args.id, &args.agent, &args.error),
        Command::Msg(args) => {
            commands::msg(&db, &args.from, &args.to, &args.content, args.task_ref)
        }
        Command::Archive(args) => {
            if args.list {
                commands::archive_list(&db, args.json)
            } else if args.count {
                commands::archive_count(&db, args.json)
            } else {
                commands::archive(&db, args.id, args.all, args.dry_run, args.json)
            }
        }
        Command::SessionEnd(args) => commands::session_end(
            args.summary.as_deref(),
            args.agent.as_deref(),
            args.last,
            &args.blockers,
            args.json,
        ),
        Command::Watch(args) => commands::watch(&db, args.to_agent.as_deref(), args.every),
        Command::TaskLog(args) => commands::task_log(
            &db,
            args.id,
            &args.dispatch_log,
            args.task_log.as_deref(),
            args.json,
        ),
    }
}
