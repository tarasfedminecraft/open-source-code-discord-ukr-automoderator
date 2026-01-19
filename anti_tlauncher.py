import discord
from discord.ext import commands
from discord import app_commands
import datetime


class ConfigModal(discord.ui.Modal):
    def __init__(self, title, config_key, parent_cog, interaction_origin):
        super().__init__(title=title)
        self.config_key = config_key
        self.parent_cog = parent_cog
        self.interaction_origin = interaction_origin
        self.input_field = discord.ui.TextInput(label="Значення", placeholder="Наприклад: 5", min_length=1,
                                                max_length=3)
        self.add_item(self.input_field)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = int(self.input_field.value)
            # Записуємо безпосередньо в базу даних через database.py
            await self.parent_cog.bot.db.execute(
                f"INSERT INTO antitlauncher_settings (guild_id, {self.config_key}) VALUES (%s, %s) "
                f"ON DUPLICATE KEY UPDATE {self.config_key} = %s",
                (interaction.guild_id, val, val)
            )
            await self.parent_cog.send_setup_view(self.interaction_origin)
            if not interaction.response.is_done():
                await interaction.response.defer()
        except Exception as e:
            await interaction.response.send_message(f"❌ Помилка: Введіть число!", ephemeral=True)


class AntiTLauncher(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.user_warnings = {}  # Варни юзерів залишаємо в RAM, бо вони тимчасові

    async def get_config(self, guild_id: int):
        """Отримує конфігурацію сервера з MariaDB"""
        data = await self.bot.db.fetchrow("SELECT * FROM antitlauncher_settings WHERE guild_id = %s", (guild_id,))
        if not data:
            # Дефолтні налаштування, якщо сервера немає в базі
            return {"log_channel_id": None, "warnings_to_ban": 3, "forget_after_minutes": 30, "enabled": False}
        return data

    @app_commands.command(name="at_setup", description="Налаштувати Anti-TLauncher")
    @app_commands.checks.has_permissions(administrator=True)
    async def at_setup(self, interaction: discord.Interaction):
        await self.send_setup_view(interaction)

    async def send_setup_view(self, interaction: discord.Interaction):
        config = await self.get_config(interaction.guild_id)

        embed = discord.Embed(
            title="⚙️ Панель Anti-TLauncher",
            description=(
                "Блокування користувачів з TLauncher.\n\n"
                f"**Логи в:** <#{config['log_channel_id']}>" if config['log_channel_id'] else "**Логи:** Не встановлено"
            ),
            color=discord.Color.blue()
        )
        embed.add_field(name="🔨 Ліміт варнів", value=f"{config['warnings_to_ban']}", inline=True)
        embed.add_field(name="🕒 Очищення", value=f"{config['forget_after_minutes']} хв", inline=True)
        embed.add_field(name="Статус", value="✅ ПРАЦЮЄ" if config["enabled"] else "❌ ВИМКНЕНО", inline=False)

        view = discord.ui.View()

        # Логіка кнопок
        btn_warns = discord.ui.Button(label="Ліміт варнів", style=discord.ButtonStyle.primary)
        btn_time = discord.ui.Button(label="Час (хв)", style=discord.ButtonStyle.primary)
        btn_toggle = discord.ui.Button(
            label="Зупинити захист" if config["enabled"] else "Запустити захист",
            style=discord.ButtonStyle.danger if config["enabled"] else discord.ButtonStyle.success
        )
        btn_log = discord.ui.Button(label="Встановити цей канал", style=discord.ButtonStyle.secondary)

        # Колбеки
        async def warns_callback(inter):
            await inter.response.send_modal(ConfigModal("Варни", "warnings_to_ban", self, interaction))

        async def time_callback(inter):
            await inter.response.send_modal(ConfigModal("Час", "forget_after_minutes", self, interaction))

        async def toggle_callback(inter):
            new_status = not config["enabled"]
            await self.bot.db.execute(
                "INSERT INTO antitlauncher_settings (guild_id, enabled) VALUES (%s, %s) ON DUPLICATE KEY UPDATE enabled = %s",
                (inter.guild_id, new_status, new_status)
            )
            await self.send_setup_view(interaction)
            await inter.response.defer()

        async def log_callback(inter):
            await self.bot.db.execute(
                "INSERT INTO antitlauncher_settings (guild_id, log_channel_id) VALUES (%s, %s) ON DUPLICATE KEY UPDATE log_channel_id = %s",
                (inter.guild_id, inter.channel.id, inter.channel.id)
            )
            await inter.response.send_message(f"✅ Канал логів встановлено.", ephemeral=True)
            await self.send_setup_view(interaction)

        btn_warns.callback = warns_callback
        btn_time.callback = time_callback
        btn_toggle.callback = toggle_callback
        btn_log.callback = log_callback

        for item in [btn_warns, btn_time, btn_toggle, btn_log]: view.add_item(item)

        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @commands.Cog.listener()
    async def on_presence_update(self, before, after):
        if not after.guild: return
        config = await self.get_config(after.guild.id)

        if not config["enabled"] or after.bot: return

        if any("TLauncher" in a.name for a in after.activities if hasattr(a, 'name') and a.name):
            await self.process_violation(after, config)
        else:
            await self.check_forgetting(after, config)

    async def process_violation(self, member, config):
        uid = member.id
        now = datetime.datetime.now()

        if uid in self.user_warnings:
            if (now - self.user_warnings[uid]["last_warned"]).total_seconds() < 300: return
        else:
            self.user_warnings[uid] = {"count": 0, "last_warned": now}

        self.user_warnings[uid]["count"] += 1
        self.user_warnings[uid]["last_warned"] = now

        log_chan = self.bot.get_channel(config["log_channel_id"])

        if self.user_warnings[uid]["count"] >= config["warnings_to_ban"]:
            try:
                await member.ban(reason="TLauncher")
                if log_chan: await log_chan.send(f"🔨 **БАН**: {member.mention} за використання TLauncher.")
                del self.user_warnings[uid]
            except:
                pass
        elif log_chan:
            emb = discord.Embed(title="⚠️ Виявлено TLauncher", color=discord.Color.red())
            emb.add_field(name="Юзер", value=member.mention)
            emb.add_field(name="Варни", value=f"{self.user_warnings[uid]['count']}/{config['warnings_to_ban']}")
            await log_chan.send(embed=emb)

    async def check_forgetting(self, member, config):
        uid = member.id
        if uid in self.user_warnings:
            diff = (datetime.datetime.now() - self.user_warnings[uid]["last_warned"]).total_seconds() / 60
            if diff >= config["forget_after_minutes"]:
                del self.user_warnings[uid]


async def setup(bot):
    await bot.add_cog(AntiTLauncher(bot))