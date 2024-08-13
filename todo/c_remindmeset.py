"""Commands for [p]remindmeset."""
from redbot.core import checks, commands

from .pcx_lib import SettingDisplay, checkmark


class RemindMeSetCommands():
    """Commands for [p]remindmeset."""

    @commands.group()
    @checks.admin_or_permissions(manage_guild=True)
    async def todoset(self, ctx: commands.Context) -> None:
        """Manage Todo settings."""

    @todoset.command()
    async def settings(self, ctx: commands.Context) -> None:
        """Display current settings."""
        server_section = SettingDisplay("Server Settings")
        if ctx.guild:
            server_section.add("Me too", "Enabled" if await self.config.guild(ctx.guild).me_too() else "Disabled")

        if await ctx.bot.is_owner(ctx.author):
            global_section = SettingDisplay("Global Settings")
            global_section.add("Maximum todo items per user", await self.config.max_user_reminders())
            stats_section = SettingDisplay("Stats")
            stats_section.add("Total todo items ever", await self.config.total())
            await ctx.send(server_section.display(global_section, stats_section))
        else:
            await ctx.send(str(server_section))

    @todoset.command()
    @commands.guild_only()
    async def metoo(self, ctx: commands.Context) -> None:
        """Toggle the bot asking if others want to add an item to their todo lists.

        If the bot doesn't have the Add Reactions permission in the channel, it won't ask regardless.
        """
        me_too = not await self.config.guild(ctx.guild).me_too()
        await self.config.guild(ctx.guild).me_too.set(me_too)
        await ctx.send(checkmark(f"I will {'now' if me_too else 'no longer'} ask if others want to add an item to their todo lists."))

    @todoset.command(name="max")
    @checks.is_owner()
    async def set_max(self, ctx: commands.Context, maximum: int) -> None:
        """Global: Set the maximum number of reminders a user can create at one time."""
        await self.config.max_user_reminders.set(maximum)
        await ctx.send(checkmark(f"Maximum reminders per user is now set to {await self.config.max_user_reminders()}"))