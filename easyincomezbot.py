#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mini App Launcher / Welcome Bot
UI like: invite message + Open App (WebApp) + Channel / Support / Group / Reviews

Main Admin: 8289191009
- /start shows configurable welcome + inline buttons
- Admin can set: welcome text, Open App URL, Channel/Support/Group/Reviews links
- Add Admin / Remove Admin / Ownership Transfer
- Persistent reply menu for admin
"""

import logging
import os
import sqlite3
from datetime import datetime
from typing import Optional

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    WebAppInfo,
    MenuButtonWebApp,
    MenuButtonCommands,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

# ================== CONFIG ==================
BOT_TOKEN = "8818824501:AAHRg07xfYBpjm32kJMpObt9icp5S0dknoM"
MAIN_ADMIN_ID = 8289191009
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "miniapp_launcher.db")

(
    SET_VALUE,
    ADD_ADMIN_ID,
    REMOVE_ADMIN_ID,
    TRANSFER_ID,
) = range(4)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ================== DB ==================
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            role TEXT DEFAULT 'admin',
            added_at TEXT
        );
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            referrer_id INTEGER,
            joined_at TEXT
        );
        """
    )
    defaults = {
        "owner_id": str(MAIN_ADMIN_ID),
        "bot_title": "TONTraderAI",
        "welcome_text": (
            "🎁 <b>You're Invited!</b>\n\n"
            "Your friend invited you to join — the ultimate platform.\n\n"
            "✨ <b>Your Exclusive Welcome Perks:</b>\n"
            "• 🎁 Signup bonus ready to claim\n"
            "• ⚡ Automated features inside the App\n"
            "• 🤝 Referral program — invite friends\n\n"
            "👇 Tap <b>Open App</b> below to continue!"
        ),
        "webapp_url": "",
        "webapp_button": "🚀 Open App",
        "channel_url": "",
        "channel_label": "📢 Channel",
        "support_url": "",
        "support_label": "💬 Support",
        "group_url": "",
        "group_label": "👥 Group",
        "reviews_url": "",
        "reviews_label": "⭐ Reviews",
        "banner_text": "",
        "force_channel": "0",
        "menu_webapp": "1",
    }
    for k, v in defaults.items():
        cur.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v)
        )
    cur.execute(
        "INSERT OR IGNORE INTO admins (user_id, role, added_at) VALUES (?, 'main', ?)",
        (MAIN_ADMIN_ID, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_setting(key: str, default: str = "") -> str:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = cur.fetchone()
    conn.close()
    if row and row["value"] is not None:
        return row["value"]
    return default


def set_setting(key: str, value: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, value),
    )
    conn.commit()
    conn.close()


def owner_id() -> int:
    try:
        return int(get_setting("owner_id") or MAIN_ADMIN_ID)
    except Exception:
        return MAIN_ADMIN_ID


def is_main(uid: int) -> bool:
    return int(uid) == owner_id() or int(uid) == MAIN_ADMIN_ID


def is_admin(uid: int) -> bool:
    if is_main(uid):
        return True
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM admins WHERE user_id=?", (uid,))
    ok = cur.fetchone() is not None
    conn.close()
    return ok


def ensure_user(uid: int, username: str = None, full_name: str = None, referrer_id: int = None):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (uid,))
    if not cur.fetchone():
        if referrer_id and int(referrer_id) == int(uid):
            referrer_id = None
        cur.execute(
            """INSERT INTO users (user_id, username, full_name, referrer_id, joined_at)
               VALUES (?,?,?,?,?)""",
            (
                uid,
                username,
                full_name,
                referrer_id,
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
    else:
        cur.execute(
            "UPDATE users SET username=?, full_name=? WHERE user_id=?",
            (username, full_name, uid),
        )
        conn.commit()
    conn.close()


# ================== KEYBOARDS ==================
def admin_kb():
    return ReplyKeyboardMarkup(
        [
            ["📝 Welcome Text", "🖼 Banner Text"],
            ["🚀 WebApp URL", "🔘 WebApp Button Name"],
            ["📢 Channel Link", "💬 Support Link"],
            ["👥 Group Link", "⭐ Reviews Link"],
            ["🏷 Labels (Ch/Sup/Grp/Rev)", "👁 Preview Start"],
            ["➕ Add Admin", "🗑 Remove Admin"],
            ["👑 Ownership Transfer", "📊 Stats"],
            ["🏠 Close Admin"],
        ],
        resize_keyboard=True,
    )


def build_start_keyboard() -> InlineKeyboardMarkup:
    rows = []
    webapp = (get_setting("webapp_url") or "").strip()
    btn_name = get_setting("webapp_button") or "🚀 Open App"

    if webapp:
        if webapp.startswith("https://"):
            rows.append(
                [InlineKeyboardButton(btn_name, web_app=WebAppInfo(url=webapp))]
            )
        else:
            # http or t.me — use normal URL button
            rows.append([InlineKeyboardButton(btn_name, url=webapp)])
    else:
        rows.append(
            [InlineKeyboardButton(btn_name + " (not set)", callback_data="noop")]
        )

    ch = (get_setting("channel_url") or "").strip()
    su = (get_setting("support_url") or "").strip()
    gr = (get_setting("group_url") or "").strip()
    rv = (get_setting("reviews_url") or "").strip()

    ch_l = get_setting("channel_label") or "📢 Channel"
    su_l = get_setting("support_label") or "💬 Support"
    gr_l = get_setting("group_label") or "👥 Group"
    rv_l = get_setting("reviews_label") or "⭐ Reviews"

    row2 = []
    if ch:
        row2.append(InlineKeyboardButton(ch_l, url=ch))
    else:
        row2.append(InlineKeyboardButton(ch_l, callback_data="link_missing_ch"))
    if su:
        row2.append(InlineKeyboardButton(su_l, url=su))
    else:
        row2.append(InlineKeyboardButton(su_l, callback_data="link_missing_su"))
    rows.append(row2)

    row3 = []
    if gr:
        row3.append(InlineKeyboardButton(gr_l, url=gr))
    else:
        row3.append(InlineKeyboardButton(gr_l, callback_data="link_missing_gr"))
    if rv:
        row3.append(InlineKeyboardButton(rv_l, url=rv))
    else:
        row3.append(InlineKeyboardButton(rv_l, callback_data="link_missing_rv"))
    rows.append(row3)

    return InlineKeyboardMarkup(rows)


def start_message_text() -> str:
    banner = (get_setting("banner_text") or "").strip()
    welcome = (get_setting("welcome_text") or "").strip()
    parts = []
    if banner:
        parts.append(banner)
    if welcome:
        parts.append(welcome)
    if not parts:
        parts.append("Welcome! Configure text from Admin Panel.")
    return "\n\n".join(parts)


# ================== START ==================
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ref = None
    if context.args:
        arg = context.args[0]
        if arg.startswith("ref_"):
            try:
                ref = int(arg.replace("ref_", ""))
            except Exception:
                ref = None
        elif arg.isdigit():
            ref = int(arg)

    ensure_user(
        uid,
        update.effective_user.username,
        update.effective_user.full_name,
        ref,
    )

    text = start_message_text()
    kb = build_start_keyboard()
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
        disable_web_page_preview=True,
    )

    if is_admin(uid):
        await update.message.reply_text(
            "🔧 Admin: /admin দিয়ে প্যানেল খুলুন।",
            reply_markup=admin_kb(),
        )


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ শুধু Admin।")
        return
    await update.message.reply_text(
        "🔧 <b>Admin Panel</b>\n\n"
        "নিচের বাটন দিয়ে সব সেটআপ করুন।\n"
        "WebApp URL অবশ্যই <code>https://</code> দিয়ে শুরু করতে হবে।",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_kb(),
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ /start — মেইন মেনু\n"
        "/admin — অ্যাডমিন প্যানেল (শুধু admin)"
    )


# ================== CALLBACKS ==================
async def noop_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Admin এখনো WebApp URL সেট করেনি।", show_alert=True)


async def link_missing_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("লিংক সেট নেই — Admin Panel থেকে সেট করুন।", show_alert=True)


# ================== ADMIN SET FLOW ==================
FIELD_MAP = {
    "📝 Welcome Text": ("welcome_text", "নতুন Welcome টেক্সট পাঠান (HTML চলবে):\n/cancel বাতিল"),
    "🖼 Banner Text": ("banner_text", "Banner টেক্সট পাঠান (খালি রাখতে - লিখুন):\n/cancel"),
    "🚀 WebApp URL": ("webapp_url", "Mini App / WebApp URL পাঠান (https://...):\n/cancel"),
    "🔘 WebApp Button Name": ("webapp_button", "Open App বাটনের নাম পাঠান:\n/cancel"),
    "📢 Channel Link": ("channel_url", "Channel লিংক (https://t.me/...):\n/cancel"),
    "💬 Support Link": ("support_url", "Support লিংক (https://t.me/...):\n/cancel"),
    "👥 Group Link": ("group_url", "Group লিংক:\n/cancel"),
    "⭐ Reviews Link": ("reviews_url", "Reviews লিংক:\n/cancel"),
}


async def admin_field_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    text = update.message.text
    if text not in FIELD_MAP:
        return ConversationHandler.END
    key, prompt = FIELD_MAP[text]
    context.user_data["set_key"] = key
    cur = get_setting(key) or "(empty)"
    await update.message.reply_text(
        f"বর্তমান:\n<code>{cur[:500]}</code>\n\n{prompt}",
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardRemove(),
    )
    return SET_VALUE


async def admin_set_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    key = context.user_data.get("set_key")
    if not key:
        return ConversationHandler.END
    val = (update.message.text or "").strip()
    if val == "-":
        val = ""
    if key == "webapp_url" and val and not val.startswith("https://"):
        await update.message.reply_text(
            "⚠️ WebApp URL অবশ্যই https:// দিয়ে শুরু হতে হবে। আবার পাঠান বা /cancel"
        )
        return SET_VALUE
    set_setting(key, val)
    context.user_data.pop("set_key", None)
    await update.message.reply_text(
        f"✅ <b>{key}</b> সেভ হয়েছে।",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_kb(),
    )
    # try update menu button if webapp
    if key in ("webapp_url", "webapp_button") and get_setting("webapp_url").startswith("https://"):
        try:
            await context.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text=(get_setting("webapp_button") or "Open")[:20],
                    web_app=WebAppInfo(url=get_setting("webapp_url")),
                )
            )
        except Exception as e:
            logger.warning("menu button: %s", e)
    return ConversationHandler.END


async def labels_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    context.user_data["set_key"] = "labels_pack"
    await update.message.reply_text(
        "৪টি লেবেল এক লাইনে | দিয়ে পাঠান:\n"
        "<code>📢 Channel|💬 Support|👥 Group|⭐ Reviews</code>\n\n"
        f"বর্তমান:\n"
        f"{get_setting('channel_label')}|{get_setting('support_label')}|"
        f"{get_setting('group_label')}|{get_setting('reviews_label')}",
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardRemove(),
    )
    return SET_VALUE


async def admin_set_value_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = context.user_data.get("set_key")
    if key == "labels_pack":
        parts = [p.strip() for p in (update.message.text or "").split("|")]
        while len(parts) < 4:
            parts.append("")
        set_setting("channel_label", parts[0] or "📢 Channel")
        set_setting("support_label", parts[1] or "💬 Support")
        set_setting("group_label", parts[2] or "👥 Group")
        set_setting("reviews_label", parts[3] or "⭐ Reviews")
        context.user_data.pop("set_key", None)
        await update.message.reply_text("✅ Labels updated.", reply_markup=admin_kb())
        return ConversationHandler.END
    return await admin_set_value(update, context)


async def preview_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        start_message_text(),
        parse_mode=ParseMode.HTML,
        reply_markup=build_start_keyboard(),
        disable_web_page_preview=True,
    )


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM users")
    uc = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM admins")
    ac = cur.fetchone()["c"]
    conn.close()
    await update.message.reply_text(
        f"📊 Users: <b>{uc}</b>\nAdmins: <b>{ac}</b>\nOwner: <code>{owner_id()}</code>\n"
        f"WebApp: <code>{(get_setting('webapp_url') or '-')[:60]}</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_kb(),
    )


# ================== ADMIN MANAGE ==================
async def add_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_main(update.effective_user.id):
        await update.message.reply_text("শুধু Main Owner Add Admin করতে পারে।")
        return ConversationHandler.END
    await update.message.reply_text(
        "নতুন Admin এর Telegram User ID পাঠান:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ADD_ADMIN_ID


async def add_admin_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_main(update.effective_user.id):
        return ConversationHandler.END
    try:
        nid = int(update.message.text.strip())
    except Exception:
        await update.message.reply_text("সঠিক User ID দিন।")
        return ADD_ADMIN_ID
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO admins (user_id, role, added_at) VALUES (?,?,?)",
        (nid, "admin", datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ Admin added: {nid}", reply_markup=admin_kb())
    try:
        await context.bot.send_message(nid, "🔧 আপনাকে Admin বানানো হয়েছে। /admin")
    except Exception:
        pass
    return ConversationHandler.END


async def remove_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_main(update.effective_user.id):
        await update.message.reply_text("শুধু Main Owner Remove করতে পারে।")
        return ConversationHandler.END
    await update.message.reply_text(
        "রিমুভ করার Admin User ID:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return REMOVE_ADMIN_ID


async def remove_admin_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_main(update.effective_user.id):
        return ConversationHandler.END
    try:
        nid = int(update.message.text.strip())
    except Exception:
        await update.message.reply_text("সঠিক ID দিন।")
        return REMOVE_ADMIN_ID
    if nid == MAIN_ADMIN_ID or nid == owner_id():
        await update.message.reply_text("Main Owner রিমুভ করা যাবে না।", reply_markup=admin_kb())
        return ConversationHandler.END
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM admins WHERE user_id=? AND role!='main'", (nid,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"🗑 Removed: {nid}", reply_markup=admin_kb())
    return ConversationHandler.END


async def transfer_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_main(update.effective_user.id):
        await update.message.reply_text("শুধু Main Owner।")
        return ConversationHandler.END
    await update.message.reply_text(
        "নতুন Owner এর User ID পাঠান (এটি উল্টানো যাবে না সহজে):",
        reply_markup=ReplyKeyboardRemove(),
    )
    return TRANSFER_ID


async def transfer_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_main(update.effective_user.id):
        return ConversationHandler.END
    try:
        nid = int(update.message.text.strip())
    except Exception:
        await update.message.reply_text("সঠিক ID দিন।")
        return TRANSFER_ID
    if nid == update.effective_user.id:
        await update.message.reply_text("নিজেকে ট্রান্সফার নয়।", reply_markup=admin_kb())
        return ConversationHandler.END
    set_setting("owner_id", str(nid))
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO admins (user_id, role, added_at) VALUES (?,?,?)",
        (nid, "main", datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    await update.message.reply_text(
        f"👑 Ownership transferred to {nid}",
        reply_markup=admin_kb(),
    )
    try:
        await context.bot.send_message(nid, "👑 আপনি এখন Main Owner। /admin")
    except Exception:
        pass
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    kb = admin_kb() if is_admin(update.effective_user.id) else ReplyKeyboardRemove()
    await update.message.reply_text("বাতিল।", reply_markup=kb)
    return ConversationHandler.END


async def close_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Admin বন্ধ। /start চাপুন।",
        reply_markup=ReplyKeyboardRemove(),
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    uid = update.effective_user.id
    if not is_admin(uid):
        return
    if text == "👁 Preview Start":
        await preview_start(update, context)
    elif text == "📊 Stats":
        await stats_cmd(update, context)
    elif text == "🏠 Close Admin":
        await close_admin(update, context)
    elif text == "🏷 Labels (Ch/Sup/Grp/Rev)":
        return  # conversation entry
    # other fields handled by ConversationHandler entry points


def main():
    if not BOT_TOKEN or "YOUR_BOT" in BOT_TOKEN:
        print("ERROR: BOT_TOKEN সেট করুন")
        return
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    set_conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex(
                    r"^(📝 Welcome Text|🖼 Banner Text|🚀 WebApp URL|🔘 WebApp Button Name|"
                    r"📢 Channel Link|💬 Support Link|👥 Group Link|⭐ Reviews Link)$"
                ),
                admin_field_start,
            ),
            MessageHandler(
                filters.Regex(r"^🏷 Labels"),
                labels_start,
            ),
        ],
        states={
            SET_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_set_value_router)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    add_adm = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^➕ Add Admin$"), add_admin_start)],
        states={
            ADD_ADMIN_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin_receive)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    rm_adm = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r"^🗑 Remove Admin$"), remove_admin_start)
        ],
        states={
            REMOVE_ADMIN_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, remove_admin_receive)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    tr_adm = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r"^👑 Ownership Transfer$"), transfer_start)
        ],
        states={
            TRANSFER_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, transfer_receive)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CallbackQueryHandler(noop_cb, pattern=r"^noop$"))
    app.add_handler(CallbackQueryHandler(link_missing_cb, pattern=r"^link_missing_"))
    app.add_handler(set_conv)
    app.add_handler(add_adm)
    app.add_handler(rm_adm)
    app.add_handler(tr_adm)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Mini App Launcher Bot starting...")
    print("Bot running... Admin ID:", MAIN_ADMIN_ID)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
