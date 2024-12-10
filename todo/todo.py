"""RemindMe cog for Red-DiscordBot ported and enhanced by PhasecoreX."""
import asyncio
import discord
import logging
from typing import Any

from abc import ABC
from redbot.core import Config, commands

from .c_reminder import ReminderCommands
from .c_remindmeset import RemindMeSetCommands

log = logging.getLogger("red.pcxcogs.todo")


class CompositeMetaClass(type(commands.Cog), type(ABC)):
    """This allows the metaclass used for proper type detection to coexist with discord.py's metaclass."""


class Todo(
    ReminderCommands,
    RemindMeSetCommands,
    commands.Cog,
    metaclass=CompositeMetaClass,
):
    """Never forget anything anymore."""

    __author__ = "PhasecoreX"
    __version__ = "3.1.0b" # based off of remindme commit 1ccda7129b708516b71b0819d29155415d788104

    default_global_settings = {
        "schema_version": 0,
        "total": 0,
        "max_user_reminders": 20,
    }
    default_guild_settings = {
        "me_too": False,
    }
    default_reminder_settings = {
        "text": "",  # str
        "jump_link": None,  # str
    }
    SEND_DELAY_SECONDS = 30

    def __init__(self, bot):
        """Set up the cog."""
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1224364860, force_registration=True)
        self.config.register_global(**self.default_global_settings)
        self.config.register_guild(**self.default_guild_settings)
        # user id -> user reminder id
        self.config.init_custom("REMINDER", 3)
        self.config.register_custom("REMINDER", **self.default_reminder_settings)
        self.me_too_reminders = {}
        self.clicked_me_too_reminder = {}
        self.reminder_emoji = "\N{Spiral Note Pad}"

    #
    # Red methods
    #

    def format_help_for_context(self, ctx: commands.Context) -> str:
        """Show version in help."""
        pre_processed = super().format_help_for_context(ctx)
        return f"{pre_processed}\n\nCog Version: {self.__version__}"

    async def red_delete_data_for_user(self, *, requester, user_id: int):  # pylint: disable=unused-argument
        await self.config.custom("REMINDER", str(user_id)).clear()

    #
    # Initialization methods
    #
       
    async def initialize(self) -> None:
        """Perform setup actions before loading cog."""
        await self._migrate_config()
        
    async def _migrate_config(self) -> None:
        """Perform some configuration migrations."""
        if not await self.config.schema_version():
            await self.config.schema_version.set(3)

    #
    # Listener methods
    #

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.raw_models.RawReactionActionEvent) -> None:
        """Watches for bell reactions on reminder messages."""
        if str(payload.emoji) != self.reminder_emoji:
            return
        if not payload.guild_id or await self.bot.cog_disabled_in_guild_raw(self.qualified_name, payload.guild_id):
            return
        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return
        if not await self.config.guild(guild).me_too():
            return
        member = guild.get_member(payload.user_id)
        if not member:
            return
        if member.bot:
            return

        try:
            reminder = self.me_too_reminders[payload.message_id]
            clicked_set = self.clicked_me_too_reminder[payload.message_id]
            if member.id in clicked_set:
                return  # User clicked the bell again, not going to add a duplicate reminder
            clicked_set.add(member.id)
            if await self.insert_reminder(member.id, reminder):
                message = "hey! just letting you know i've added that to your todo list."
                await member.send(message)
            else:
                await self.send_too_many_message(member)
        except KeyError:
            return

    #
    # Public methods
    #

    async def insert_reminder(self, user_id: int, todo_list: str, reminder: dict):
        """Insert a new reminder into the config.

        Will handle generating a user_reminder_id and reminder limits.
        Returns True for success, False for user having too many reminders.
        """
        # Check that the user has room for another reminder
        maximum = await self.config.max_user_reminders()
        users_partial_reminders = await self.config.custom("REMINDER", str(user_id), str(todo_list)).all()  # Does NOT return default values
        if len(users_partial_reminders) > maximum - 1:
            return False

        # Get next user_reminder_id
        next_reminder_id = 1
        while str(next_reminder_id) in users_partial_reminders:  # Keys are strings
            next_reminder_id += 1

        # Save new reminder
        await self.config.custom("REMINDER", str(user_id), str(todo_list), str(next_reminder_id)).set(reminder)

    async def send_too_many_message(self, ctx: commands.Context, maximum: int = -1):
        """Send a message to the user telling them they have too many reminders."""
        if maximum < 0:
            maximum = await self.config.max_user_reminders()
        plural = "todo item" if maximum == 1 else "todo items"
        message = (f"you have too many todo items! i can only keep track of {maximum} {plural} for you at a time.")
        await ctx.reply(message)