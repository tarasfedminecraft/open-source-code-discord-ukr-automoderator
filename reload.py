import discord
from discord.ext import commands
from discord import app_commands
import os
import sys
import traceback
import time


class Reloader(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- Допоміжна функція для автозаповнення ---
    async def module_autocomplete(self, interaction: discord.Interaction, current: str) -> list[
        app_commands.Choice[str]]:
        modules = ["ALL"]  # Опція для оновлення всього
        # Скануємо папку на .py файли
        for filename in os.listdir('./'):
            if filename.endswith('.py') and filename != 'main.py':
                modules.append(filename[:-3])

        # Фільтруємо те, що вводить користувач
        return [
            app_commands.Choice(name=m, value=m)
            for m in modules if current.lower() in m.lower()
        ][:25]  # Discord дозволяє максимум 25 підказок

    @app_commands.command(name="reload", description="Керування модулями бота")
    @app_commands.describe(
        module="Оберіть модуль зі списку або ALL для всіх",
        sync="Синхронізувати Slash-команди (True/False)"
    )
    @app_commands.autocomplete(module=module_autocomplete)
    @app_commands.checks.has_permissions(administrator=True)
    async def system_reload(self, interaction: discord.Interaction, module: str = "ALL", sync: bool = False):
        await interaction.response.defer(ephemeral=True)
        start_time = time.perf_counter()

        embed = discord.Embed(title="⚙️ Система оновлення", color=discord.Color.blue())

        success_log = []
        error_log = []

        # Визначаємо список модулів для оновлення
        target_modules = []
        if module == "ALL":
            # Якщо вибрано ALL - беремо всі файли
            for filename in os.listdir('./'):
                if filename.endswith('.py') and filename != 'main.py':
                    target_modules.append(filename[:-3])
        else:
            # Якщо вибрано конкретний модуль
            target_modules.append(module)

        # Процес оновлення
        for cog_name in target_modules:
            try:
                # Спробуємо перезавантажити
                await self.bot.reload_extension(cog_name)
                success_log.append(f"🔄 **{cog_name}**")
            except commands.ExtensionNotLoaded:
                # Якщо ще не завантажено - завантажуємо
                try:
                    await self.bot.load_extension(cog_name)
                    success_log.append(f"📥 **{cog_name}** (New)")
                except Exception as e:
                    error_log.append(f"❌ **{cog_name}**: `{e}`")
            except commands.ExtensionFailed as e:
                # Помилка в самому коді (SyntaxError тощо)
                error_log.append(f"🔥 **{cog_name}**: `{e.original}`")
                print(f"CRITICAL ERROR in {cog_name}:", file=sys.stderr)
                traceback.print_exc()
            except Exception as e:
                error_log.append(f"❌ **{cog_name}**: `{e}`")

        # Синхронізація (Tree Sync)
        tree_msg = "⏩ Пропущено"
        if sync:
            try:
                synced = await self.bot.tree.sync()
                tree_msg = f"⚡ Сінхронізовано {len(synced)} команд"
            except Exception as e:
                tree_msg = f"⚠️ Помилка: {e}"
                error_log.append(f"Tree: {e}")

        # Підрахунок часу
        elapsed = round((time.perf_counter() - start_time) * 1000, 2)
        embed.set_footer(text=f"⏱️ Час виконання: {elapsed}ms | Адмін: {interaction.user.name}")

        # Формування полів Embed (з захистом від переповнення)
        if success_log:
            succ_text = "\n".join(success_log)
            if len(succ_text) > 1000: succ_text = succ_text[:1000] + "\n... і ще"
            embed.add_field(name=f"✅ Успішно ({len(success_log)})", value=succ_text, inline=False)

        if error_log:
            err_text = "\n".join(error_log)
            if len(err_text) > 1000: err_text = err_text[:1000] + "\n... див. консоль"
            embed.color = discord.Color.red()
            embed.add_field(name=f"🚫 Помилки ({len(error_log)})", value=err_text, inline=False)
        else:
            embed.color = discord.Color.green()

        embed.add_field(name="Синхронізація", value=tree_msg, inline=False)

        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Reloader(bot))