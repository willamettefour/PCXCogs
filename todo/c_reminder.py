"""Commands for the average user."""
import asyncio
import discord
import re

from redbot.core import commands
from redbot.core.utils.chat_formatting import error
from redbot.core.utils.predicates import MessagePredicate

from .pcx_lib import delete, embed_splitter

class ReminderCommands():
    """Commands for the average user."""

    @commands.group()
    async def todo(self, ctx: commands.Context):
        """Manage your todo list."""

    @todo.command()
    async def lists(self, ctx):
        """Shows your todo lists."""
        author = ctx.author
        todo_list = await self.config.custom("REMINDER", str(author.id)).all()
        lists = list(todo_list.keys())
        tdlists = ""
        for tdlist in lists:
            tdlists += f"• {tdlist}\n" 
        embed = discord.Embed(title=f"{author.display_name}'s Todo Lists", description=tdlists, color=await ctx.embed_color())
        if author.avatar is None:
            url = author.default_avatar
        else:
            url = str(author.avatar.replace(size=2048, static_format="webp")) 
            if author.avatar.is_animated() is False:
                url += "&quality=lossless"
        embed.set_thumbnail(url=url)
        await ctx.send(embed=embed)

    @todo.command()
    async def list(self, ctx, todo_list: str = "", sort: str = None):
        """Shows your todo list."""
        # Grab users reminders, format them so we can see the user_reminder_id
        author = ctx.author
        user_reminders = []
        if todo_list == "":
            todo_list = "main"
            if sort is None:
                sort = "id"
        else:
            if todo_list and sort is None:
                if todo_list in ["id", "added"]:
                    if not await self.config.custom("REMINDER", str(author.id), str(todo_list)).all():
                        todo_list = "main"
                        sort = "id"
                else:
                    sort = "id"
        user_reminders_dict = await self.config.custom("REMINDER", str(author.id), str(todo_list)).all()
        for user_reminder_id, reminder in user_reminders_dict.items():
            reminder.update({"user_reminder_id": int(user_reminder_id)})
            user_reminders.append(reminder)

        # Check if they actually have any reminders
        if not user_reminders:
            await ctx.reply("You haven't added anything to that todo list!", mention_author=False)
            return
            
        # Sort the reminders
        if sort == "added":
            pass
        elif sort == "id":
            user_reminders.sort(key=lambda reminder_info: reminder_info["user_reminder_id"])
        else:
            await ctx.send("that is not a valid sorting option. choose from `id` (default) or `added`.")
            return

        # Make a pretty embed listing the reminders
        embed = discord.Embed(title=f"{author.display_name}'s Todo List ({todo_list})", color=await ctx.embed_color())
        if author.avatar is None:
            url = author.default_avatar
        else:
            url = str(author.avatar.replace(size=2048, static_format="webp")) 
            if author.avatar.is_animated() is False:
                url += "&quality=lossless"
        embed.set_thumbnail(url=url)
        for reminder in user_reminders:  # TODO make this look nicer.
            reminder_title = (f"ID# {reminder['user_reminder_id']}")
            reminder_text = reminder["text"]
            if reminder["jump_link"]:
                reminder_text += f"\n([original message]({reminder['jump_link']}))"
            reminder_text = reminder_text
            embed.add_field(name=reminder_title, value=reminder_text, inline=False)
        try:
            await embed_splitter(ctx, embed)
        except discord.Forbidden:
            await ctx.reply("I can't DM you...", mention_author=False)

    @todo.command(aliases=["add"])
    async def create(self, ctx, *, todo_list, note: str = ""):
        """Create a todo item."""
        match = re.search(r'"(.*?)"', todo_list)
        if match:
            td_list = match.group(1)
            note = todo_list.replace(f'"{td_list}"', '')
            if note.startswith(" "):
                note = note[1:]
            if td_list == "":
                td_list = "main"
            todo_list = td_list
        else:
            note = todo_list
            todo_list = "main"
        await self._create_reminder(ctx, todo_list, note)
        total = await self.config.total()
        await self.config.total.set(total + 1)

    @todo.command()
    async def edit(self, ctx, todo_list: str = "", reminder_id: str = None, *, text: str = ""):
        """Modify the text of an existing todo item."""
        if text == "":
            if todo_list == "":
                reminder_id = ""
            else:
                text = reminder_id
                reminder_id = todo_list
                todo_list = "main"
        config_reminder = await self._get_reminder_config_group(ctx, str(todo_list), ctx.author.id, reminder_id)
        if not config_reminder:
            return

        text = text.strip()
        if len(text) > 800:
            await ctx.reply("your todo text is too long.", mention_author=False)
            return

        await config_reminder.text.set(text)
        await ctx.send(f"todo item with ID# **{reminder_id}** has been edited successfully.")

    @todo.command(aliases=["delete", "del"])
    async def remove(self, ctx, todo_list: str = "", index: str = None):
        """Delete a todo item.

        <index> can either be:
        - a todo item's ID
        - `last` to delete the most recently added todo item
        - `all` to clear your todo list
        """
        if todo_list == "" and index:
            todo_list = "main"
        if index is None and todo_list != "":
            index = todo_list
            todo_list = "main"
        await self._delete_reminder(ctx, todo_list, index)

    async def _create_reminder(self, ctx, todo_list: str, note: str):
        """Logic to create a reminder."""
        # Check that user is allowed to make a new reminder
        author = ctx.message.author
        maximum = await self.config.max_user_reminders()
        users_reminders = await self.config.custom("REMINDER", str(author.id), str(todo_list)).all()  # Does NOT return default values
        if len(users_reminders) > maximum - 1:
            await self.send_too_many_message(ctx, maximum)
            return
            
        if note == "":
            await ctx.send("No text was given!")
            return 

        # Create basic reminder
        new_reminder = {
            "text": note,
            "jump_link": ctx.message.jump_url,
        }

        # Save reminder for user
        await self.insert_reminder(author.id, todo_list, new_reminder)

        # Let user know we successfully saved their reminder
        await ctx.reply("Successfully added to your todo list.", mention_author=False)

        # Send me too message if enabled
        if (
            ctx.guild
            and await self.config.guild(ctx.guild).me_too()
            and ctx.channel.permissions_for(ctx.me).add_reactions
        ):
            query: discord.Message = await ctx.send(
                f"If anyone else would like to add this to their todo lists, "
                "click the notepad!"
            )
            self.me_too_reminders[query.id] = new_reminder
            self.clicked_me_too_reminder[query.id] = set([author.id])
            await query.add_reaction(self.reminder_emoji)
            await asyncio.sleep(30)
            await delete(query)
            del self.me_too_reminders[query.id]
            del self.clicked_me_too_reminder[query.id]

    async def _delete_reminder(self, ctx, todo_list: str, index: str):
        """Logic to delete reminders."""
        if not index:
            return
        author = ctx.author
        if index == "all":
            all_users_reminders = self.config.custom("REMINDER", str(author.id), str(todo_list))
            full_list = await self.config.custom("REMINDER", str(author.id)).all()
            lists = list(full_list.keys())
            if todo_list not in full_list:
                await ctx.reply("that todo list doesn't exist! remember that names are case-sensitive!")
                return

            # Ask if the user really wants to do this
            pred = MessagePredicate.yes_or_no(ctx)
            await ctx.reply("are you **sure** you want to delete this todo list? (yes/no)")
            try:
                await ctx.bot.wait_for("message", check=pred, timeout=30)
            except asyncio.TimeoutError:
                pass
            if pred.result:
                pass
            else:
                await ctx.reply("i have left that todo list alone.")
                return
            await all_users_reminders.clear()
            await ctx.reply(f"todo list `{todo_list}` has been deleted")
            return

        if index == "last":
            all_users_reminders_dict = await self.config.custom("REMINDER", str(author.id), str(todo_list)).all()
            if not all_users_reminders_dict:
                await ctx.reply("you don't have anything in that todo list!", mention_author=False)
                return

            reminder_id_to_delete = int(list(all_users_reminders_dict)[-1])
            await self.config.custom("REMINDER", str(author.id), str(todo_list), str(reminder_id_to_delete)).clear()
            await ctx.reply(f"your most recently created todo item (ID# **{reminder_id_to_delete}**) in `{todo_list}` has been removed.", mention_author=False)
            return

        try:
            int_index = int(index)
        except ValueError:
            await ctx.send_help()
            return

        config_reminder = await self._get_reminder_config_group(ctx, todo_list, author.id, int_index)
        if not config_reminder:
            return
        await config_reminder.clear()
        await ctx.reply(f"todo item with ID# **{int_index}** has been removed.", mention_author=False)

    async def _get_reminder_config_group(self, ctx, todo_list: str, user_id: int, user_reminder_id: int):
        config_reminder = self.config.custom("REMINDER", str(user_id), str(todo_list), str(user_reminder_id))
        if not await config_reminder.text():
            await ctx.reply(f"todo item with ID# **{user_reminder_id}** does not exist! check your todo list and verify you typed the correct ID #.", mention_author=False)
            return None
        return config_reminder