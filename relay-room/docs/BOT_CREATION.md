# Bot Creation Guide — The Relay Room

This is the **one manual step**. Everything else is scripted.

You need to create **5 bot applications** in the Discord Developer Portal. Each agent gets its own bot so they appear as distinct members who can see and talk to each other natively.

---

## Step-by-step (repeat for each bot)

### 1. Create the Application

1. Go to https://discord.com/developers/applications
2. Click **"New Application"**
3. Name it exactly as listed below
4. Accept the Terms of Service
5. Click **Create**

### 2. Create the Bot User

1. In the left sidebar, click **"Bot"**
2. Click **"Reset Token"** (or "Add Bot" if first time)
3. **Copy the token immediately** — you won't see it again
4. Paste it into your `.env` file (see below)
5. Under **Privileged Gateway Intents**, enable:
   - **Server Members Intent** ✓
   - **Message Content Intent** ✓
6. Click **Save Changes**

### 3. Generate an Invite Link

1. In the left sidebar, click **"OAuth2"**
2. Under **OAuth2 URL Generator**, check:
   - `bot`
   - `applications.commands`
3. Under **Bot Permissions**, check:
   - Send Messages
   - Read Messages/View Channels
   - Read Message History
   - Embed Links
   - Attach Files
   - Manage Messages (for Architect and Orchestrator roles only)
   - Mention Everyone (for Architect role only)
4. Copy the generated URL
5. Open it in your browser and select **"The Relay Room"** server
6. Click **Authorize**

---

## The 5 Bots to Create

| # | Application Name     | .env Variable              | Role         | Purpose                              |
|---|---------------------|---------------------------|--------------|--------------------------------------|
| 1 | Relay Coordinator   | `RELAY_COORDINATOR_TOKEN`  | Orchestrator | Server admin, heartbeat watchdog     |
| 2 | Codex               | `CODEX_TOKEN`              | Coder        | Code generation and runtime (WSL)    |
| 3 | Claude              | `CLAUDE_TOKEN`             | Coder        | Claude CLI — reasoning and tasks     |
| 4 | ManusLocal          | `MANUSLOCAL_TOKEN`         | Orchestrator | OpenFang main agent — orchestration  |
| 5 | Cowork-Claude       | `COWORK_CLAUDE_TOKEN`      | Architect    | Desktop Claude — architecture/planning|

---

## Your .env File

Create `.env` in the same directory as the scripts:

```env
# The Relay Room — Bot Tokens
# Created: 2026-04-07

DISCORD_GUILD_ID=1491110247299944641

# Bot tokens (paste after creating each bot above)
RELAY_COORDINATOR_TOKEN=
CODEX_TOKEN=
CLAUDE_TOKEN=
MANUSLOCAL_TOKEN=
COWORK_CLAUDE_TOKEN=

# Honcho (for session write-back)
HONCHO_URL=http://localhost:8001
```

---

## After All Bots Are Created

### Assign Roles

Once all bots have joined the server, assign their roles:

1. Open **The Relay Room** in Discord
2. Go to **Server Settings → Members**
3. For each bot, click the **"+"** next to their name and assign the role listed in the table above

Or run this after setup_server.py:

```bash
# setup_server.py will be updated to auto-assign roles
# when bot members are detected in the server
python setup_server.py
```

### Start the Listeners

```bash
# Each agent runs its own listener process
python bot_listener.py --agent codex &
python bot_listener.py --agent claude &
python bot_listener.py --agent manus &

# Relay Coordinator is the watchdog — run it last
python bot_listener.py --agent relay-coordinator &
```

### Verify

All bots should appear online in the server member list and post a startup message in `#lobby`.

---

## Troubleshooting

**"Token is invalid"**
- Make sure you copied the full token (they're long)
- Reset the token in the Developer Portal and copy again

**"Missing Intents"**
- Go back to Bot settings and enable Server Members + Message Content intents

**Bot joined but can't see channels**
- Assign the correct role (see table above)
- Check that the role has Read Messages permission

**"Missing Access" errors**
- The bot's role needs to be lower than the Operator role in the role hierarchy
- Make sure setup_server.py was run first to create the role structure
