import discord
from discord.ext import commands
from discord import app_commands
import re


class AntiInvite(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Регулярний вираз для пошуку інвайтів
        self.invite_regex = re.compile(
            r"(?:https?://)?(?:www\.)?(?:discord\.(?:gg|io|me|li)|discordapp\.com/invite|discord\.com/invite)/[a-zA-Z0-9]+",
            re.IGNORECASE
        )

    async def get_config(self, guild_id: int):
        """Отримує налаштування сервера з MariaDB"""
        data = await self.bot.db.fetchrow("SELECT * FROM anti_invite_settings WHERE guild_id = %s", (guild_id,))
        if not data:
            return {"enabled": False, "log_channel_id": None}
        return data

    @app_commands.command(name="lk_setup", description="Налаштувати Anti-Invite")
    @app_commands.checks.has_permissions(administrator=True)
    async def lk_setup(self, interaction: discord.Interaction):
        await self.send_setup_view(interaction)

    async def send_setup_view(self, interaction: discord.Interaction):
        config = await self.get_config(interaction.guild_id)

        embed = discord.Embed(
            title="🛡️ Керування фільтром посилань",
            description=(
                "Видаляє запрошення на інші сервери.\n\n"
                f"**Статус:** {'✅ Увімкнено' if config['enabled'] else '❌ Вимкнено'}\n"
                f"**Канал логів:** <#{config['log_channel_id']}>" if config[
                    'log_channel_id'] else "**Канал логів:** Не встановлено"
            ),
            color=discord.Color.gold()
        )

        view = discord.ui.View()

        btn_toggle = discord.ui.Button(
            label="Вимкнути захист" if config['enabled'] else "Увімкнути захист",
            style=discord.ButtonStyle.danger if config['enabled'] else discord.ButtonStyle.success
        )

        btn_set_log = discord.ui.Button(label="Встановити цей канал для логів", style=discord.ButtonStyle.secondary)

        # Колбек для вмикання/вимикання
        async def toggle_callback(inter: discord.Interaction):
            new_status = not config['enabled']
            await self.bot.db.execute(
                "INSERT INTO anti_invite_settings (guild_id, enabled) VALUES (%s, %s) ON DUPLICATE KEY UPDATE enabled = %s",
                (inter.guild_id, new_status, new_status)
            )
            await self.send_setup_view(interaction)
            await inter.response.defer()

        # Колбек для встановлення каналу логів
        async def set_log_callback(inter: discord.Interaction):
            await self.bot.db.execute(
                "INSERT INTO anti_invite_settings (guild_id, log_channel_id) VALUES (%s, %s) ON DUPLICATE KEY UPDATE log_channel_id = %s",
                (inter.guild_id, inter.channel.id, inter.channel.id)
            )
            await inter.response.send_message(f"✅ Канал логів встановлено.", ephemeral=True)
            await self.send_setup_view(interaction)

        btn_toggle.callback = toggle_callback
        btn_set_log.callback = set_log_callback
        view.add_item(btn_toggle)
        view.add_item(btn_set_log)

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ігноруємо ботів та особисті повідомлення
        if message.author.bot or not message.guild: return

        # Отримуємо конфіг сервера
        config = await self.get_config(message.guild.id)

        # Перевіряємо, чи увімкнено захист та чи є у автора права модератора
        if not config["enabled"]: return
        if message.author.guild_permissions.manage_messages: return

        if self.invite_regex.search(message.content):
            try:
                await message.delete()
                await message.channel.send(f"⚠️ {message.author.mention}, посилання заборонені!", delete_after=5)

                if config["log_channel_id"]:
                    log_chan = self.bot.get_channel(config["log_channel_id"])
                    if log_chan:
                        embed = discord.Embed(title="🚫 Інвайт видалено", color=discord.Color.orange())
                        embed.add_field(name="Автор", value=f"{message.author} ({message.author.id})")
                        embed.add_field(name="Канал", value=message.channel.mention)
                        embed.add_field(name="Текст", value=message.content[:1024])  # Захист від задовгих повідомлень
                        await log_chan.send(embed=embed)
            except:
                pass


async def setup(bot):
    await bot.add_cog(AntiInvite(bot))