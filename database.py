import aiomysql
import os
import logging
import asyncio

# Налаштування логування
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('database')


class Database:
    def __init__(self):
        self.pool = None

    async def connect(self):
        """Створює пул з'єднань з MariaDB з оптимальними налаштуваннями"""
        try:
            self.pool = await aiomysql.create_pool(
                host=os.getenv('DB_HOST'),
                port=int(os.getenv('DB_PORT', 3307)),  # Твій порт 3307
                user=os.getenv('DB_USER'),
                password=os.getenv('DB_PASS'),
                db=os.getenv('DB_NAME'),
                autocommit=True,  # Автоматичне збереження змін
                minsize=1,  # Мінімальна кількість активних з'єднань
                maxsize=10  # Максимальна кількість з'єднань
            )
            logger.info("✅ Підключення до MariaDB встановлено успішно!")
            await self._create_tables()
        except Exception as e:
            logger.error(f"❌ Помилка підключення до БД: {e}")

    async def _create_tables(self):
        """Створює всі необхідні таблиці автоматично при запуску"""
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                # 1. Таблиця налаштувань (Рахунок та Слова)
                # ДОДАНО колонку last_user_id
                await cur.execute("""
                                  CREATE TABLE IF NOT EXISTS server_settings
                                  (
                                      guild_id
                                      BIGINT
                                      PRIMARY
                                      KEY,
                                      counting_channel
                                      BIGINT
                                      DEFAULT
                                      NULL,
                                      words_channel
                                      BIGINT
                                      DEFAULT
                                      NULL,
                                      current_count
                                      INT
                                      DEFAULT
                                      0,
                                      last_user_id
                                      BIGINT
                                      DEFAULT
                                      NULL
                                  )
                                  """)

                # 2. Таблиця для ТОПІВ
                await cur.execute("""
                                  CREATE TABLE IF NOT EXISTS counting_stats
                                  (
                                      guild_id
                                      BIGINT,
                                      user_id
                                      BIGINT,
                                      score
                                      INT
                                      DEFAULT
                                      0,
                                      PRIMARY
                                      KEY
                                  (
                                      guild_id,
                                      user_id
                                  )
                                      )
                                  """)

                # 3. Таблиця для Anti-TLauncher
                await cur.execute("""
                                  CREATE TABLE IF NOT EXISTS antitlauncher_settings
                                  (
                                      guild_id
                                      BIGINT
                                      PRIMARY
                                      KEY,
                                      log_channel_id
                                      BIGINT
                                      DEFAULT
                                      NULL,
                                      warnings_to_ban
                                      INT
                                      DEFAULT
                                      3,
                                      forget_after_minutes
                                      INT
                                      DEFAULT
                                      30,
                                      enabled
                                      BOOLEAN
                                      DEFAULT
                                      FALSE
                                  )
                                  """)

                # 4. Таблиця для Anti-Invite
                await cur.execute("""
                                  CREATE TABLE IF NOT EXISTS anti_invite_settings
                                  (
                                      guild_id
                                      BIGINT
                                      PRIMARY
                                      KEY,
                                      enabled
                                      BOOLEAN
                                      DEFAULT
                                      FALSE,
                                      log_channel_id
                                      BIGINT
                                      DEFAULT
                                      NULL
                                  )
                                  """)

                # 5. Таблиця для Економіки
                await cur.execute("""
                                  CREATE TABLE IF NOT EXISTS users
                                  (
                                      user_id
                                      BIGINT
                                      PRIMARY
                                      KEY,
                                      balance
                                      INT
                                      DEFAULT
                                      0,
                                      last_daily
                                      DATETIME
                                      DEFAULT
                                      NULL
                                  )
                                  """)

                logger.info("✅ Усі таблиці бази даних перевірені/створені")

    # --- Універсальні методи для роботи з даними ---

    async def execute(self, query: str, params: tuple = None):
        """Використовується для INSERT, UPDATE, DELETE"""
        if not self.pool: return
        async with self.pool.acquire() as conn:
            async with conn.cursor() as cur:
                try:
                    await cur.execute(query, params)
                except Exception as e:
                    logger.error(f"⚠️ SQL Execute Error: {e}\nQuery: {query}")

    async def fetchrow(self, query: str, params: tuple = None):
        """Повертає один рядок у вигляді словника (Dict)"""
        if not self.pool: return None
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                try:
                    await cur.execute(query, params)
                    return await cur.fetchone()
                except Exception as e:
                    logger.error(f"⚠️ SQL Fetchrow Error: {e}")
                    return None

    async def fetchall(self, query: str, params: tuple = None):
        """Повертає список всіх рядків (для топів тощо)"""
        if not self.pool: return []
        async with self.pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                try:
                    await cur.execute(query, params)
                    return await cur.fetchall()
                except Exception as e:
                    logger.error(f"⚠️ SQL Fetchall Error: {e}")
                    return []


# Функція для ініціалізації при старті бота (викликається в main.py)
async def setup_db(bot):
    db = Database()
    await db.connect()
    bot.db = db