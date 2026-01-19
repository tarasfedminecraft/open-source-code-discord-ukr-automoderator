import discord
from discord.ext import commands
import os
import datetime
from dotenv import load_dotenv
from database import setup_db

# 👇 ІМПОРТУЄМО ФУНКЦІЮ ЗАПУСКУ САЙТУ
# Переконайся, що папка називається 'site', а файл 'webserver.py'
try:
    from site.webserver import run_site
except ImportError:
    print("⚠️ Увага: Не вдалося імпортувати модуль сайту. Перевірте папку 'site'.")
    # Заглушка, щоб бот не впав, якщо сайту немає
    async def run_site(bot): pass

# Завантажуємо токен з .env
load_dotenv()
TOKEN = os.getenv('TOKEN')

class MyBot(commands.Bot):
    def __init__(self):
        # Вмикаємо всі потрібні інтенти
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.presences = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )
        self.db = None

    async def setup_hook(self):
        # 1. Спершу запускаємо базу даних
        await setup_db(self)

        # 2. ЗАПУСКАЄМО САЙТ 🌐
        # Ми передаємо 'self' (самого бота) у функцію сайту,
        # щоб сайт мав доступ до бази даних та серверів.
        print("🌐 Ініціалізація веб-дашборду...")
        self.loop.create_task(run_site(self))

        print("--- Завантаження модулів ---")
        # Список файлів, які НЕ є модулями (Cogs)
        system_files = ['main.py', 'database.py']

        # Скануємо папку на наявність когів
        for filename in os.listdir('./'):
            # Завантажуємо лише .py файли, яких немає в списку system_files
            if filename.endswith('.py') and filename not in system_files:
                extension_name = filename[:-3]
                try:
                    await self.load_extension(extension_name)
                    print(f"✅ Модуль завантажено: {extension_name}")
                except Exception as e:
                    print(f"❌ Помилка в модулі {extension_name}: {e}")

        print("--- Синхронізація команд ---")
        await self.tree.sync()
        print("✅ Команди синхронізовано!")

    async def on_ready(self):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Бот {self.user} готовий до роботи!")
        # Встановлюємо статус
        await self.change_presence(
            activity=discord.Game(name="Під захистом D Bot 🛡️")
        )

# Запуск
if __name__ == "__main__":
    if TOKEN:
        bot = MyBot()
        bot.run(TOKEN)
    else:
        print("🔴 Критична помилка: Токен не знайдено в .env файлі!")