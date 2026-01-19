import discord
from discord.ext import commands
from discord import app_commands
import re
import os
import random
import asyncio
from typing import List, Optional

# --- Константи ---
_ALLOWED_WORD_RE = re.compile(r"[А-Яа-яІіЇїЄєҐґ'ʼ’\-]+")
BAD_END_LETTERS = ('ь', 'й', 'и', 'і')


def normalize_word(word: str) -> str:
    if not word: return ""
    s = word.strip().lower()
    s = s.replace("ʼ", "'").replace("’", "'").replace("—", "-").replace("–", "-")
    m = _ALLOWED_WORD_RE.search(s)
    if not m: return ""
    return m.group(0).strip("-'")


async def safe_delete_message(msg):
    try:
        await msg.delete()
    except:
        pass


# --- Клас Games ---

class Games(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.valid_words = set()
        self.states = {}
        self.load_words()

    def load_words(self):
        self.valid_words = set()
        try:
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "slova.txt")
            if os.path.exists(path):
                with open(path, encoding="utf-8-sig") as f:
                    for raw in f:
                        w = normalize_word(raw)
                        if len(w) >= 1: self.valid_words.add(w)
                print(f"✅ Словник завантажено: {len(self.valid_words)} слів")
        except Exception as e:
            print(f"❌ Помилка словника: {e}")

    async def get_state(self, guild_id: int):
        if guild_id not in self.states:
            data = await self.bot.db.fetchrow("SELECT * FROM server_settings WHERE guild_id = %s", (guild_id,))
            if data:
                self.states[guild_id] = data
            else:
                self.states[guild_id] = {
                    "counting_channel": None,
                    "words_channel": None,
                    "current_count": 0,
                    "last_user_id": None
                }
        return self.states[guild_id]

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild: return

        state = await self.get_state(message.guild.id)

        # --- Логіка рахунку ---
        if state["counting_channel"] == message.channel.id:
            if not re.fullmatch(r"\d+", message.content.strip()): return
            num = int(message.content.strip())

            # 1. Перевірка на правильність числа
            if num != state["current_count"] + 1:
                await message.add_reaction("❌")
                await safe_delete_message(message)
                return

            # 2. Перевірка: чи не та сама людина пише підряд?
            if message.author.id == state.get("last_user_id"):
                await message.add_reaction("🚫")
                await safe_delete_message(message)
                return

            # Оновлюємо стан у локальній пам'яті
            state["current_count"] = num
            state["last_user_id"] = message.author.id

            # Оновлюємо загальний рахунок та останнього гравця в БАЗІ
            await self.bot.db.execute(
                "UPDATE server_settings SET current_count = %s, last_user_id = %s WHERE guild_id = %s",
                (num, message.author.id, message.guild.id)
            )

            # Нарахування особистих балів гравцю
            await self.bot.db.execute(
                "INSERT INTO counting_stats (guild_id, user_id, score) VALUES (%s, %s, 1) "
                "ON DUPLICATE KEY UPDATE score = score + 1",
                (message.guild.id, message.author.id)
            )
            await message.add_reaction("✅")

        # --- Логіка слів ---
        elif state["words_channel"] == message.channel.id:
            norm = normalize_word(message.content)
            if norm and norm in self.valid_words:
                await message.add_reaction("🟢")
            elif norm:
                await message.channel.send(f"Слова '{norm}' немає!", delete_after=3)
                await safe_delete_message(message)

    # --- Команди керування ---

    @app_commands.command(name="top_count", description="Топ гравців у рахувальник")
    async def top_count(self, interaction: discord.Interaction):
        results = await self.bot.db.fetchall(
            "SELECT user_id, score FROM counting_stats WHERE guild_id = %s ORDER BY score DESC LIMIT 10",
            (interaction.guild.id,)
        )

        if not results:
            return await interaction.response.send_message("Топ поки що порожній! Почніть рахувати.", ephemeral=True)

        embed = discord.Embed(title="🔢 Топ лічильників сервера", color=discord.Color.gold())

        description = ""
        for i, row in enumerate(results, 1):
            user = self.bot.get_user(row['user_id'])
            user_name = user.name if user else f"ID: {row['user_id']}"
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"**{i}.**"
            description += f"{medal} {user_name} — `{row['score']}` чисел\n"

        embed.description = description
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="reset_count", description="Повний скид рахунку (Тільки Адмін)")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset_count(self, interaction: discord.Interaction):
        # Очищуємо в базі (включаючи last_user_id)
        await self.bot.db.execute(
            "UPDATE server_settings SET current_count = 0, last_user_id = NULL WHERE guild_id = %s",
            (interaction.guild.id,)
        )
        await self.bot.db.execute("DELETE FROM counting_stats WHERE guild_id = %s", (interaction.guild.id,))

        # Очищуємо в пам'яті об'єкта
        if interaction.guild.id in self.states:
            self.states[interaction.guild.id]["current_count"] = 0
            self.states[interaction.guild.id]["last_user_id"] = None

        await interaction.response.send_message("🧹 **Рахунок, статистика та історія гравців обнулені!**")

    @app_commands.command(name="set_word", description="Встановити канал для гри у слова")
    @app_commands.checks.has_permissions(administrator=True)
    async def cmd_set_word(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self.bot.db.execute(
            "INSERT INTO server_settings (guild_id, words_channel) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE words_channel = %s",
            (interaction.guild.id, channel.id, channel.id)
        )
        if interaction.guild.id in self.states: del self.states[interaction.guild.id]
        await interaction.response.send_message(f"📝 Канал для слів встановлено: {channel.mention}")

    @app_commands.command(name="set_counting", description="Встановити канал для рахунку")
    @app_commands.checks.has_permissions(administrator=True)
    async def cmd_set_counting(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self.bot.db.execute(
            "INSERT INTO server_settings (guild_id, counting_channel, current_count, last_user_id) VALUES (%s, %s, 0, NULL) "
            "ON DUPLICATE KEY UPDATE counting_channel = %s, current_count = 0, last_user_id = NULL",
            (interaction.guild.id, channel.id, channel.id)
        )
        if interaction.guild.id in self.states: del self.states[interaction.guild.id]
        await interaction.response.send_message(f"🔢 Канал для рахунку встановлено: {channel.mention}")


async def setup(bot):
    await bot.add_cog(Games(bot))