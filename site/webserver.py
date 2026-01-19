import os
import asyncio
from quart import Quart, render_template, request, jsonify, redirect, url_for, send_file
from quart_discord import DiscordOAuth2Session, Unauthorized

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'code')
STATIC_DIR = os.path.join(BASE_DIR, 'code', 'assets')

app = Quart(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
app.secret_key = os.urandom(24)

# --- CONFIG ---
app.config["DISCORD_CLIENT_ID"] = 1462416328815022203
app.config["DISCORD_CLIENT_SECRET"] = "2UBXhr4rxDAJ6XokPwFz2HgzhNfxxZLW"
app.config["DISCORD_REDIRECT_URI"] = "https://dbot-site.bh-games.com:9055/callback"

discord = DiscordOAuth2Session(app)


async def is_admin(guild_id, user_id):
    guild = app.bot.get_guild(int(guild_id))
    if not guild: return False
    member = guild.get_member(int(user_id))
    return member.guild_permissions.administrator if member else False


@app.route("/")
async def index():
    return await render_template("index.html", authorized=await discord.authorized)


# --- RAW FILES (MD) ---
@app.route("/privacy-policy.md")
async def privacy():
    return await send_file(os.path.join(TEMPLATE_DIR, 'privacy-policy.md'), mimetype='text/plain')


@app.route("/terms-of-use.md")
async def terms():
    return await send_file(os.path.join(TEMPLATE_DIR, 'terms-of-use.md'), mimetype='text/plain')


# --- AUTH ---
@app.route("/login")
async def login():
    return await discord.create_session(scope=["identify", "guilds"])


@app.route("/callback")
async def callback():
    try:
        await discord.callback()
    except:
        return redirect(url_for("login"))
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
async def dashboard():
    if not await discord.authorized: return redirect(url_for("login"))
    try:
        user = await discord.fetch_user()
        guilds = await discord.fetch_guilds()
        admin_guilds = [g for g in guilds if g.permissions.administrator]
        bot_guilds = [g.id for g in app.bot.guilds]

        return await render_template("index.html",
                                     authorized=True, in_dashboard=True,
                                     user=user, guilds=admin_guilds, bot_guilds=bot_guilds)
    except:
        return redirect(url_for("login"))


# --- MEGA API ---
@app.route("/api/get_all_data/<int:guild_id>")
async def get_all_data(guild_id):
    if not await discord.authorized: return jsonify({"err": "Auth"}), 401
    user = await discord.fetch_user()
    if not await is_admin(guild_id, user.id): return jsonify({"err": "Perms"}), 403

    db = app.bot.db
    data = {
        "anti_invite": await db.fetchrow("SELECT * FROM anti_invite_settings WHERE guild_id=%s", (guild_id,)) or {},
        "anti_tl": await db.fetchrow("SELECT * FROM antitlauncher_settings WHERE guild_id=%s", (guild_id,)) or {},
        "server": await db.fetchrow("SELECT * FROM server_settings WHERE guild_id=%s", (guild_id,)) or {},
        # Для ігор та економіки беремо тільки загальні дані або топ
        "counting": await db.fetchrow("SELECT current_count, last_user_id FROM server_settings WHERE guild_id=%s",
                                      (guild_id,)) or {"current_count": 0}
    }
    return jsonify(data)


@app.route("/api/update", methods=["POST"])
async def update_data():
    if not await discord.authorized: return jsonify({"err": 1}), 401
    req = await request.json
    gid, table, field, val = int(req['guild_id']), req['table'], req['field'], req['value']

    user = await discord.fetch_user()
    if not await is_admin(gid, user.id): return jsonify({"err": 3}), 403

    # Спеціальна обробка для таблиці users (Економіка)
    if table == "users":
        target_user = req.get('target_user_id')
        await app.bot.db.execute(
            f"INSERT INTO users (guild_id, user_id, {field}) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE {field}=%s",
            (gid, target_user, val, val)
        )
    else:
        await app.bot.db.execute(
            f"INSERT INTO {table} (guild_id, {field}) VALUES (%s, %s) ON DUPLICATE KEY UPDATE {field}=%s",
            (gid, val, val)
        )
    return jsonify({"status": "ok"})


async def run_site(bot):
    app.bot = bot
    await app.run_task(host="0.0.0.0", port=9055)