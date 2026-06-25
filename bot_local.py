import os
import sqlite3
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7664139802"))
SITE_LINK = os.environ.get("SITE_LINK", "https://apex-trading-eta.vercel.app/")
CHANNEL_LINK = os.environ.get("CHANNEL_LINK", "https://t.me/princexiq")
DB_PATH = "users.db"

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")
    def log_message(self, *args):
        pass

def run_web():
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            source TEXT,
            experience TEXT,
            broker TEXT,
            clicked INTEGER DEFAULT 0,
            joined_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_user(user_id, username, source):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, source) VALUES (?, ?, ?)", (user_id, username, source))
    conn.commit()
    conn.close()

def set_experience(user_id, experience):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET experience=? WHERE user_id=?", (experience, user_id))
    conn.commit()
    conn.close()

def set_broker(user_id, broker):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET broker=? WHERE user_id=?", (broker, user_id))
    conn.commit()
    conn.close()

def mark_clicked(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET clicked=1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE clicked=1")
    clicked = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE experience='new'")
    new_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE experience='experienced'")
    exp_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE broker='olymptrade'")
    olymp_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE broker='pocketoption'")
    pocket_count = c.fetchone()[0]
    conn.close()
    return total, clicked, new_count, exp_count, olymp_count, pocket_count

def get_all_user_ids():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    ids = [row[0] for row in c.fetchall()]
    conn.close()
    return ids

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    source = args[0] if args else "direct"
    save_user(user.id, user.username or "", source)
    keyboard = [[InlineKeyboardButton("🆕 New to trading", callback_data="exp_new"), InlineKeyboardButton("📈 Experienced", callback_data="exp_experienced")]]
    await update.message.reply_text(f"Welcome to Princex IQ, {user.first_name}! 🎯\n\nQuick question before we get you started:\nAre you new to forex trading or already trading?", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_experience(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if query.data == "exp_new":
        set_experience(user_id, "new")
        text = "No worries — everyone starts somewhere! 🚀\n\nWe'll guide you step by step with free signals, tips, and a simple platform to begin trading safely."
    else:
        set_experience(user_id, "experienced")
        text = "Perfect — let's get you set up fast. 📊\n\nGet live signals, advanced analysis, and direct access to our trading platform."
    await query.edit_message_text(text)
    keyboard = [[InlineKeyboardButton("Olymptrade", callback_data="broker_olymptrade"), InlineKeyboardButton("Pocket Option", callback_data="broker_pocketoption")]]
    await query.message.reply_text("One more thing — which broker are you currently using (or planning to use)?", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_broker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if query.data == "broker_pocketoption":
        set_broker(user_id, "pocketoption")
        text = "Good to know. ⚠️ Pocket Option payouts shift constantly.\n\nOlymptrade keeps payout percentages stable. Most of our top traders have switched over. 📈"
    else:
        set_broker(user_id, "olymptrade")
        text = "Great choice! ✅ Olymptrade keeps payout percentages consistent, which means our signals are far more reliable for you."
    await query.edit_message_text(text)
    keyboard = [[InlineKeyboardButton("🌐 Visit Site & Register", url=SITE_LINK)]]
    await query.message.reply_text("Tap below to register on our platform:", reply_markup=InlineKeyboardMarkup(keyboard))
    mark_clicked(user_id)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    total, clicked, new_count, exp_count, olymp_count, pocket_count = get_stats()
    await update.message.reply_text(f"📊 Bot Stats\n\nTotal users: {total}\nReached site link: {clicked}\nNew traders: {new_count}\nExperienced traders: {exp_count}\nOlymptrade users: {olymp_count}\nPocket Option users: {pocket_count}")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Usage: /broadcast your message here")
        return
    message = " ".join(context.args)
    ids = get_all_user_ids()
    sent = 0
    for uid in ids:
        try:
            await context.bot.send_message(chat_id=uid, text=message)
            sent += 1
        except Exception as e:
            log.warning(f"Failed to send to {uid}: {e}")
    await update.message.reply_text(f"Broadcast sent to {sent}/{len(ids)} users.")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Commands:\n/start - begin\nChannel: {CHANNEL_LINK}\nSite: {SITE_LINK}")

def main():
    init_db()
    threading.Thread(target=run_web, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(handle_experience, pattern="^exp_"))
    app.add_handler(CallbackQueryHandler(handle_broker, pattern="^broker_"))
    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
