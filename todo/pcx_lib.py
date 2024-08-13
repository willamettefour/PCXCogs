"""Shared code across multiple cogs."""
import discord

from reactionmenu import ViewMenu, ViewButton
from redbot.core import __version__ as redbot_version
from redbot.core import commands
from redbot.core.utils import common_filters
from redbot.core.utils.chat_formatting import box
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

headers = {"user-agent": "Red-DiscordBot/" + redbot_version}

def checkmark(text: str) -> str:
    """Get text prefixed with a checkmark emoji."""
    return f"\N{WHITE HEAVY CHECK MARK} {text}"

async def delete(message: discord.Message, *, delay: float | None = None) -> bool:
    """Attempt to delete a message.

    Returns True if successful, False otherwise.
    """
    try:
        await message.delete(delay=delay)
    except discord.NotFound:
        return True  # Already deleted
    except discord.HTTPException:
        return False
    return True

async def embed_splitter(ctx, embed: discord.Embed) -> list[discord.Embed]:
    """Take an embed and split it so that each embed has at most 20 fields and a length of 5900.

    Each field value will also be checked to have a length no greater than 1024.

    If supplied with a destination, will also send those embeds to the destination.
    """
    embed_dict = embed.to_dict()

    # Check and fix field value lengths
    modified = False
    if "fields" in embed_dict:
        for field in embed_dict["fields"]:
            if len(field["value"]) > 1024:
                field["value"] = field["value"][:1021] + "..."
                modified = True
    if modified:
        embed = discord.Embed.from_dict(embed_dict)

    # Short circuit
    if len(embed) < 5901 and ("fields" not in embed_dict or len(embed_dict["fields"]) < 21):
        return await ctx.send(embed=embed)

    # Nah we really doing this
    split_embeds: list[discord.Embed] = []
    fields = embed_dict["fields"] if "fields" in embed_dict else []
    embed_dict["fields"] = []

    for field in fields:
        embed_dict["fields"].append(field)
        current_embed = discord.Embed.from_dict(embed_dict)
        if len(current_embed) > 5900 or len(embed_dict["fields"]) > 20:
            embed_dict["fields"].pop()
            current_embed = discord.Embed.from_dict(embed_dict)
            split_embeds.append(current_embed.copy())
            embed_dict["fields"] = [field]

    current_embed = discord.Embed.from_dict(embed_dict)
    split_embeds.append(current_embed.copy())
    menu = ViewMenu(ctx, style='page $/&', menu_type=ViewMenu.TypeEmbed)
    if len(split_embeds) > 2:
        fpb = ViewButton(style=discord.ButtonStyle.primary, emoji='⏪', label='First', custom_id=ViewButton.ID_GO_TO_FIRST_PAGE)
        menu.add_button(fpb)
    back_button = ViewButton(style=discord.ButtonStyle.primary, emoji='◀️', label='Back', custom_id=ViewButton.ID_PREVIOUS_PAGE)
    menu.add_button(back_button)
    if len(split_embeds) > 2:
        gtpb = ViewButton(style=discord.ButtonStyle.primary, emoji='🔢', label='Menu' ,custom_id=ViewButton.ID_GO_TO_PAGE)
        menu.add_button(gtpb)
    next_button = ViewButton(style=discord.ButtonStyle.primary, emoji='▶️', label='Next', custom_id=ViewButton.ID_NEXT_PAGE)
    menu.add_button(next_button)
    if len(split_embeds) > 2:
        lpb = ViewButton(style=discord.ButtonStyle.primary, emoji='⏩', label='Last', custom_id=ViewButton.ID_GO_TO_LAST_PAGE)
        menu.add_button(lpb)
    for embed in split_embeds:
        menu.add_page(embed)
    await menu.start()

class SettingDisplay:
    """A formatted list of settings."""

    def __init__(self, header: Optional[str] = None) -> None:
        """Init."""
        self.header = header
        self._length = 0
        self._settings: list[tuple] = []

    def add(self, setting: str, value: Any) -> None:  # noqa: ANN401
        """Add a setting."""
        setting_colon = setting + ":"
        self._settings.append((setting_colon, value))
        self._length = max(len(setting_colon), self._length)

    def raw(self) -> str:
        """Generate the raw text of this SettingDisplay, to be monospace (ini) formatted later."""
        msg = ""
        if not self._settings:
            return msg
        if self.header:
            msg += f"--- {self.header} ---\n"
        for setting in self._settings:
            msg += f"{setting[0].ljust(self._length, ' ')} [{setting[1]}]\n"
        return msg.strip()

    def display(self, *additional) -> str:  # noqa: ANN002 (Self)
        """Generate a ready-to-send formatted box of settings.

        If additional SettingDisplays are provided, merges their output into one.
        """
        msg = self.raw()
        for section in additional:
            msg += "\n\n" + section.raw()
        return box(msg, lang="ini")

    def __str__(self) -> str:
        """Generate a ready-to-send formatted box of settings."""
        return self.display()

class Perms:
    """Helper class for dealing with a dictionary of discord.PermissionOverwrite."""

    def __init__(self, overwrites: dict[discord.Role | discord.Member | discord.Object, discord.PermissionOverwrite] | None = None) -> None:
        """Init."""
        self.__overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {}
        self.__original: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {}
        if overwrites:
            for key, value in overwrites.items():
                if isinstance(key, discord.Role | discord.Member):
                    pair = value.pair()
                    self.__overwrites[key] = discord.PermissionOverwrite().from_pair(
                        *pair
                    )
                    self.__original[key] = discord.PermissionOverwrite().from_pair(
                        *pair
                    )

    def overwrite(self, target: discord.Role | discord.Member | discord.Object, permission_overwrite: discord.PermissionOverwrite) -> None:
        """Set the permissions for a target."""
        if not permission_overwrite.is_empty() and isinstance(target, discord.Role | discord.Member):
            self.__overwrites[target] = discord.PermissionOverwrite().from_pair(
                *permission_overwrite.pair()
            )

    def update(self, target: Union[discord.Role, discord.Member], perm: Mapping[str, Optional[bool]]) -> None:
        """Update the permissions for a target."""
        if target not in self.__overwrites:
            self.__overwrites[target] = discord.PermissionOverwrite()
        self.__overwrites[target].update(**perm)
        if self.__overwrites[target].is_empty():
            del self.__overwrites[target]

    @property
    def modified(self) -> bool:
        """Check if current overwrites are different from when this object was first initialized."""
        return self.__overwrites != self.__original

    @property
    def overwrites(self) -> Optional[dict[Union[discord.Role, discord.Member], discord.PermissionOverwrite]]:
        """Get current overwrites."""
        return self.__overwrites