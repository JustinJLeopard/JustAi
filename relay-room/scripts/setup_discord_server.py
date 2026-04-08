#!/usr/bin/env python3
"""
setup_server.py — The Relay Room Discord Server Configurator

Reads server_config.yaml and applies the full server structure to an existing
Discord server: roles, categories, channels, topics, and permissions.

Usage:
    1. Create your Discord server manually (or use an existing one).
    2. Create bot applications in the Developer Portal (see BOT_CREATION.md).
    3. Paste your bot token into .env as RELAY_COORDINATOR_TOKEN.
    4. Run:  python setup_server.py

Requirements:
    pip install discord.py pyyaml python-dotenv

The script is idempotent — running it again will skip roles/channels that
already exist and only create what's missing.
"""

import asyncio
import os
import sys
import yaml
import discord
from discord import PermissionOverwrite
from dotenv import load_dotenv
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
CONFIG_PATH = SCRIPT_DIR / "server_config.yaml"
ENV_PATH = SCRIPT_DIR / ".env"

# Permission name → discord.Permissions flag mapping
PERMISSION_MAP = {
    "administrator":        "administrator",
    "send_messages":        "send_messages",
    "read_messages":        "read_messages",
    "read_message_history": "read_message_history",
    "embed_links":          "embed_links",
    "attach_files":         "attach_files",
    "manage_messages":      "manage_messages",
    "mention_everyone":     "mention_everyone",
    "connect":              "connect",
    "speak":                "speak",
    "manage_channels":      "manage_channels",
    "manage_roles":         "manage_roles",
}


def load_config() -> dict:
    """Load and validate the server config YAML."""
    if not CONFIG_PATH.exists():
        print(f"✗ Config not found: {CONFIG_PATH}")
        sys.exit(1)
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)
    print(f"✓ Loaded config: {config['server']['name']}")
    return config


def build_permissions(perm_names: list[str]) -> discord.Permissions:
    """Convert a list of permission names to a discord.Permissions object."""
    perms = discord.Permissions.none()
    for name in perm_names:
        flag = PERMISSION_MAP.get(name)
        if flag:
            setattr(perms, flag, True)
        else:
            print(f"  ⚠ Unknown permission: {name}")
    return perms


class ServerSetup(discord.Client):
    """One-shot client that configures the server and disconnects."""

    def __init__(self, config: dict, guild_id: int):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        super().__init__(intents=intents)
        self.config = config
        self.guild_id = guild_id
        self.created_roles: dict[str, discord.Role] = {}

    async def on_ready(self):
        print(f"\n✓ Logged in as {self.user} (id: {self.user.id})")
        guild = self.get_guild(self.guild_id)
        if not guild:
            print(f"✗ Guild {self.guild_id} not found. Is the bot a member?")
            await self.close()
            return

        print(f"✓ Connected to guild: {guild.name}\n")

        try:
            await self.setup_roles(guild)
            await self.setup_categories_and_channels(guild)
            await self.set_server_description(guild)
            await self.print_summary(guild)
        except Exception as e:
            print(f"\n✗ Setup failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self.close()

    # ── Roles ────────────────────────────────────────────────────────────────

    async def setup_roles(self, guild: discord.Guild):
        print("═══ ROLES ═══")
        existing = {r.name: r for r in guild.roles}

        for role_def in self.config.get("roles", []):
            name = role_def["name"]
            if name in existing:
                role = existing[name]
                print(f"  ✓ Role exists: {name} (updating...)")
                await role.edit(
                    color=discord.Color(role_def.get("color", 0)),
                    permissions=build_permissions(role_def.get("permissions", [])),
                    hoist=role_def.get("hoist", False),
                    mentionable=role_def.get("mentionable", False),
                    reason="Relay Room setup — role update",
                )
            else:
                print(f"  + Creating role: {name}")
                role = await guild.create_role(
                    name=name,
                    color=discord.Color(role_def.get("color", 0)),
                    permissions=build_permissions(role_def.get("permissions", [])),
                    hoist=role_def.get("hoist", False),
                    mentionable=role_def.get("mentionable", False),
                    reason="Relay Room setup — role creation",
                )
            self.created_roles[name] = role

        # Reorder roles so higher-authority roles are higher in the list
        # (first in config = highest authority)
        positions = {}
        total = len(self.created_roles)
        base_position = 1  # 0 is @everyone
        for i, role_def in enumerate(reversed(self.config.get("roles", []))):
            name = role_def["name"]
            if name in self.created_roles:
                positions[self.created_roles[name]] = base_position + i

        if positions:
            try:
                await guild.edit_role_positions(positions=positions)
                print("  ✓ Role positions updated")
            except discord.HTTPException as e:
                print(f"  ⚠ Could not reorder roles: {e}")

        print()

    # ── Categories & Channels ────────────────────────────────────────────────

    async def setup_categories_and_channels(self, guild: discord.Guild):
        print("═══ CATEGORIES & CHANNELS ═══")
        existing_categories = {c.name: c for c in guild.categories}
        existing_channels = {ch.name: ch for ch in guild.channels
                            if not isinstance(ch, discord.CategoryChannel)}

        for cat_def in self.config.get("categories", []):
            cat_name = cat_def["name"]

            # Create or get category
            if cat_name in existing_categories:
                category = existing_categories[cat_name]
                print(f"  ✓ Category exists: {cat_name}")
            else:
                print(f"  + Creating category: {cat_name}")
                category = await guild.create_category(
                    name=cat_name,
                    reason="Relay Room setup",
                )

            # Create channels within category
            for ch_def in cat_def.get("channels", []):
                ch_name = ch_def["name"]
                ch_type = ch_def.get("type", "text")
                ch_topic = ch_def.get("topic", "")
                restricted_to = ch_def.get("restricted_to", [])

                # Build permission overwrites for restricted channels
                overwrites = {}
                if restricted_to:
                    # Deny @everyone read access
                    overwrites[guild.default_role] = PermissionOverwrite(
                        read_messages=False,
                        send_messages=False,
                    )
                    # Allow specified roles
                    for role_name in restricted_to:
                        role = self.created_roles.get(role_name)
                        if role:
                            overwrites[role] = PermissionOverwrite(
                                read_messages=True,
                                send_messages=True,
                                read_message_history=True,
                            )
                        else:
                            print(f"    ⚠ Restricted role not found: {role_name}")

                # Check if channel already exists in this category
                existing_in_cat = [
                    ch for ch in category.channels if ch.name == ch_name
                ]

                if existing_in_cat:
                    channel = existing_in_cat[0]
                    print(f"    ✓ Channel exists: #{ch_name}")
                    # Update topic if different
                    if hasattr(channel, 'topic') and channel.topic != ch_topic:
                        await channel.edit(topic=ch_topic)
                        print(f"      ↻ Updated topic")
                else:
                    if ch_type == "voice":
                        print(f"    + Creating voice channel: 🔊 {ch_name}")
                        await guild.create_voice_channel(
                            name=ch_name,
                            category=category,
                            overwrites=overwrites if overwrites else discord.utils.MISSING,
                            reason="Relay Room setup",
                        )
                    else:
                        print(f"    + Creating text channel: #{ch_name}")
                        await guild.create_text_channel(
                            name=ch_name,
                            category=category,
                            topic=ch_topic,
                            overwrites=overwrites if overwrites else discord.utils.MISSING,
                            reason="Relay Room setup",
                        )

        print()

    # ── Server Description ───────────────────────────────────────────────────

    async def set_server_description(self, guild: discord.Guild):
        desc = self.config.get("server", {}).get("description", "")
        if desc:
            try:
                await guild.edit(description=desc)
                print(f"✓ Server description set")
            except discord.HTTPException:
                print("⚠ Could not set description (may require Community features)")

    # ── Summary ──────────────────────────────────────────────────────────────

    async def print_summary(self, guild: discord.Guild):
        print("\n" + "═" * 60)
        print(f"  THE RELAY ROOM — SETUP COMPLETE")
        print("═" * 60)
        print(f"  Server:     {guild.name}")
        print(f"  Guild ID:   {guild.id}")
        print(f"  Roles:      {len(self.created_roles)}")
        cat_count = len([c for c in guild.categories])
        ch_count = len([c for c in guild.channels
                        if not isinstance(c, discord.CategoryChannel)])
        print(f"  Categories: {cat_count}")
        print(f"  Channels:   {ch_count}")
        print(f"  Members:    {guild.member_count}")
        print("═" * 60)
        print("\nNext steps:")
        print("  1. Create bot applications (see BOT_CREATION.md)")
        print("  2. Invite bots to the server with proper permissions")
        print("  3. Assign roles to each bot")
        print("  4. Run bot listeners:  python bot_listener.py --agent <name>")
        print()


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    load_dotenv(ENV_PATH)

    token = os.getenv("RELAY_COORDINATOR_TOKEN")
    guild_id_str = os.getenv("DISCORD_GUILD_ID", "1491110247299944641")

    if not token:
        print("✗ RELAY_COORDINATOR_TOKEN not set in .env")
        print("  Create a bot in the Discord Developer Portal,")
        print("  then add its token to .env:")
        print(f"    {ENV_PATH}")
        sys.exit(1)

    try:
        guild_id = int(guild_id_str)
    except ValueError:
        print(f"✗ Invalid DISCORD_GUILD_ID: {guild_id_str}")
        sys.exit(1)

    config = load_config()

    print(f"\nTarget guild: {guild_id}")
    print("Starting setup...\n")

    client = ServerSetup(config, guild_id)
    client.run(token, log_handler=None)


if __name__ == "__main__":
    main()
