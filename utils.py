import discord
from discord.ext import commands
from discord import app_commands
import datetime

class Utils(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot_logs = []

    def add_log(self, msg: str):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.bot_logs.append(f"[{timestamp}] {msg}")
        if len(self.bot_logs) > 200:
            del self.bot_logs[:-200]

    @app_commands.command(name="info", description="Загальна інформація")
    async def cmd_info(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"🤖 **D Bot** працює!\nПінг: {round(self.bot.latency * 1000)}ms")

    @app_commands.command(name="debug", description="Останні логи")
    async def cmd_debug(self, interaction: discord.Interaction):
        # Ця команда покаже логи, якщо ми будемо писати їх в self.bot_logs через цей клас.
        # Для простоти поки що просто повертає статус.
        logs = "\n".join(self.bot_logs[-10:]) or "Логи порожні"
        await interaction.response.send_message(f"```\n{logs}\n```", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Utils(bot))