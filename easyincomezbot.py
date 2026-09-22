#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mini App Launcher / Welcome Bot (FINAL)
/start → welcome text + Open App + Channel/Support/Group/Reviews
Admin can set AND delete every field.
Main Admin: 8289191009
"""

import logging
import os
import sqlite3
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    WebAppInfo,
    MenuButtonWebApp,
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
from telegram.error import BadRequest, TelegramError

BOT_TOKEN = "8818824501:AAHRg07xfYBpjm32kJMpObt9icp5S0dknoM"
MAIN_ADMIN_ID = 8289191009
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "miniapp_launcher.db")

SET_VALUE, ADD_ADMIN_ID, REMOVE_ADMIN_ID, TRANSFER_ID = range(4)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


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
        "bot_title": "EasyIncomeXBot",
        "welcome_text": (
            "🎁 <b>Welcome!</b>\n\n"
            "✨ যা যা করতে পারবেন:\n"
            "• 📺 Ads দেখুন এবং পয়েন্ট অর্জন করুন\n"
            "• ✅ Task সম্পূর্ণ করে Reward নিন\n"
            "• 👥 বন্ধুদের Invite করে অতিরিক্ত Reward\n"
            "• 💳 নির্দিষ্ট ব্যালেন্স হলে Withdrawal Request\n\n"
            "👇 শুরু করতে নিচের বাটনে ক্লিক করুন।"
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


def ensure_user(uid: int, username=None, full_name=None, referrer_id=None):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id=?", (uid,))
    if not cur.fetchone():
        if referrer_id and int(referrer_id) == int(uid):
            referrer_id = None
        cur.execute(
            "INSERT INTO users (user_id, username, full_name, referrer_id, joined_at) VALUES (?,?,?,?,?)",
            (uid, username, full_name, referrer_id, datetime.now().isoformat()),
        )
        conn.commit()
    else:
        cur.execute(
            "UPDATE users SET username=?, full_name=? WHERE user_id=?",
            (username, full_name, uid),
        )
        conn.commit()
    conn.close()


def looks_like_url(u: str) -> bool:
    u = (u or "").strip()
    if not (u.startswith("https://") or u.startswith("http://")):
        return False
    host = u.split("://", 1)[-1].split("/")[0].split("?")[0].lower()
    if not host or "." not in host:
        return False
    return True


def admin_kb():
    return ReplyKeyboardMarkup(
        [
            ["📝 Welcome Text", "🖼 Banner Text"],
            ["🚀 WebApp URL", "🔘 WebApp Button Name"],
            ["📢 Channel Link", "💬 Support Link"],
            ["👥 Group Link", "⭐ Reviews Link"],
            ["🏷 Labels", "🗑 Clear All Links"],
            ["👁 Preview Start", "📊 Stats"],
            ["➕ Add Admin", "🗑 Remove Admin"],
            ["👑 Ownership Transfer", "🏠 Close Admin"],
        ],
        resize_keyboard=True,
    )


def _url_or_cb(label: str, url: str, cb: str) -> InlineKeyboardButton:
    label = (label or "•")[:64]
    url = (url or "").strip()
    if looks_like_url(url):
        return InlineKeyboardButton(label, url=url)
    return InlineKeyboardButton(label, callback_data=cb)


def build_keyboard(mode: str = "auto") -> InlineKeyboardMarkup:
    webapp = (get_setting("webapp_url") or "").strip()
    btn_name = (get_setting("webapp_button") or "🚀 Open App")[:64]
    rows = []

    if mode == "safe" or not looks_like_url(webapp):
        rows.append([InlineKeyboardButton(btn_name, callback_data="noop")])
    elif mode == "url_only":
        rows.append([InlineKeyboardButton(btn_name, url=webapp)])
    else:
        if webapp.startswith("https://"):
            rows.append(
                [InlineKeyboardButton(btn_name, web_app=WebAppInfo(url=webapp))]
            )
        else:
            rows.append([InlineKeyboardButton(btn_name, url=webapp)])

    ch = get_setting("channel_url") or ""
    su = get_setting("support_url") or ""
    gr = get_setting("group_url") or ""
    rv = get_setting("reviews_url") or ""
    rows.append(
        [
            _url_or_cb(get_setting("channel_label") or "📢 Channel", ch, "link_missing_ch"),
            _url_or_cb(get_setting("support_label") or "💬 Support", su, "link_missing_su"),
        ]
    )
    rows.append(
        [
            _url_or_cb(get_setting("group_label") or "👥 Group", gr, "link_missing_gr"),
            _url_or_cb(get_setting("reviews_label") or "⭐ Reviews", rv, "link_missing_rv"),
        ]
    )
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
        parts.append("🎁 <b>Welcome!</b>\n\nনিচের বাটন ব্যবহার করুন।")
    return "\n\n".join(parts)


def strip_html(text: str) -> str:
    for a, b in (
        ("<b>", ""), ("</b>", ""), ("<i>", ""), ("</i>", ""),
        ("<u>", ""), ("</u>", ""), ("<code>", ""), ("</code>", ""),
        ("<pre>", ""), ("</pre>", ""),
    ):
        text = text.replace(a, b)
    return text


async def send_start_message(message, context: ContextTypes.DEFAULT_TYPE):
    text = start_message_text()
    last_err = None
    for mode in ("auto", "url_only", "safe"):
        kb = build_keyboard(mode)
        try:
            await message.reply_text(
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=kb,
                disable_web_page_preview=True,
            )
            return mode
        except (BadRequest, TelegramError) as e:
            last_err = e
            logger.warning("start HTML mode=%s: %s", mode, e)
        try:
            await message.reply_text(
                strip_html(text),
                reply_markup=kb,
                disable_web_page_preview=True,
            )
            return mode
        except (BadRequest, TelegramError) as e:
            last_err = e
            logger.warning("start plain mode=%s: %s", mode, e)

    await message.reply_text(
        strip_html(text)
        + "\n\n⚠️ বাটন পাঠানো যায়নি। /admin → 🗑 Clear All Links চাপুন, পরে WebApp আবার সেট করুন।\n"
        f"(err: {last_err})"
    )
    return None


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
    try:
        ensure_user(
            uid,
            update.effective_user.username,
            update.effective_user.full_name,
            ref,
        )
    except Exception as e:
        logger.exception("ensure_user: %s", e)

    mode = await send_start_message(update.message, context)
    logger.info("start mode=%s uid=%s", mode, uid)

    if is_admin(uid):
        try:
            await update.message.reply_text("🔧 Admin: /admin", reply_markup=admin_kb())
        except Exception:
            pass


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ শুধু Admin।")
        return
    wa = get_setting("webapp_url") or "(খালি)"
    await update.message.reply_text(
        "🔧 <b>Admin Panel</b>\n\n"
        "সেট করতে বাটন চাপুন।\n"
        "ডিলিট করতে সেট করার সময় শুধু <code>-</code> পাঠান।\n"
        "সব লিংক মুছতে: <b>🗑 Clear All Links</b>\n\n"
        f"WebApp এখন:\n<code>{wa}</code>\n\n"
        "সঠিক উদাহরণ:\n"
        "<code>https://easyincomezbot-user.edgeone.dev/</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_kb(),
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("/start — মেইন\n/admin — অ্যাডমিন")


async def noop_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer(
        "WebApp URL নেই অথবা BotFather-এ domain সেট নেই।",
        show_alert=True,
    )


async def link_missing_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer(
        "লিংক সেট নেই — Admin থেকে দিন।",
        show_alert=True,
    )


FIELD_MAP = {
    "📝 Welcome Text": ("welcome_text", "Welcome টেক্সট পাঠান।\nডিলিট: -\n/cancel"),
    "🖼 Banner Text": ("banner_text", "Banner টেক্সট।\nডিলিট: -\n/cancel"),
    "🚀 WebApp URL": (
        "webapp_url",
        "Mini App URL:\nhttps://easyincomezbot-user.edgeone.dev/\nডিলিট: -\n/cancel",
    ),
    "🔘 WebApp Button Name": ("webapp_button", "বাটনের নাম।\nডিলিট/ডিফল্ট: -\n/cancel"),
    "📢 Channel Link": ("channel_url", "https://t.me/...\nডিলিট: -\n/cancel"),
    "💬 Support Link": ("support_url", "Support লিংক\nডিলিট: -\n/cancel"),
    "👥 Group Link": ("group_url", "Group লিংক\nডিলিট: -\n/cancel"),
    "⭐ Reviews Link": ("reviews_url", "Reviews লিংক\nডিলিট: -\n/cancel"),
}


async def admin_field_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    text = update.message.text
    if text not in FIELD_MAP:
        return ConversationHandler.END
    key, prompt = FIELD_MAP[text]
    context.user_data["set_key"] = key
    cur = get_setting(key) or "(খালি)"
    await update.message.reply_text(
        f"বর্তমান:\n<code>{cur[:800]}</code>\n\n{prompt}",
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
        if key == "webapp_button":
            val = "🚀 Open App"

    if key == "webapp_url" and val:
        if not val.startswith("https://") or not looks_like_url(val):
            await update.message.reply_text(
                "⚠️ সঠিক URL দিন।\n"
                "✅ https://easyincomezbot-user.edgeone.dev/\n"
                "ডিলিট: -"
            )
            return SET_VALUE

    set_setting(key, val)
    context.user_data.pop("set_key", None)
    if not val or (key == "webapp_button" and update.message.text.strip() == "-"):
        msg = f"🗑 <b>{key}</b> মুছে/ডিফল্ট।"
    else:
        msg = f"✅ <b>{key}</b> সেভ।"
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=admin_kb())

    if key in ("webapp_url", "webapp_button"):
        try:
            u = get_setting("webapp_url")
            if u.startswith("https://") and looks_like_url(u):
                await context.bot.set_chat_menu_button(
                    menu_button=MenuButtonWebApp(
                        text=(get_setting("webapp_button") or "Open")[:20],
                        web_app=WebAppInfo(url=u),
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
        "৪টি লেবেল | দিয়ে:\n"
        "<code>📢 Channel|💬 Support|👥 Group|⭐ Reviews</code>\n"
        "ডিলিট: -",
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardRemove(),
    )
    return SET_VALUE


async def admin_set_value_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = context.user_data.get("set_key")
    if key == "labels_pack":
        raw = (update.message.text or "").strip()
        if raw == "-":
            set_setting("channel_label", "📢 Channel")
            set_setting("support_label", "💬 Support")
            set_setting("group_label", "👥 Group")
            set_setting("reviews_label", "⭐ Reviews")
        else:
            parts = [p.strip() for p in raw.split("|")]
            while len(parts) < 4:
                parts.append("")
            set_setting("channel_label", parts[0] or "📢 Channel")
            set_setting("support_label", parts[1] or "💬 Support")
            set_setting("group_label", parts[2] or "👥 Group")
            set_setting("reviews_label", parts[3] or "⭐ Reviews")
        context.user_data.pop("set_key", None)
        await update.message.reply_text("✅ Labels OK", reply_markup=admin_kb())
        return ConversationHandler.END
    return await admin_set_value(update, context)


async def clear_all_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    for k in ("webapp_url", "channel_url", "support_url", "group_url", "reviews_url", "banner_text"):
        set_setting(k, "")
    await update.message.reply_text(
        "🗑 WebApp + সব লিংক + Banner মুছে গেছে।",
        reply_markup=admin_kb(),
    )


async def preview_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await send_start_message(update.message, context)


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
        f"WebApp: <code>{(get_setting('webapp_url') or '-')[:80]}</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_kb(),
    )


async def add_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_main(update.effective_user.id):
        await update.message.reply_text("শুধু Main Owner।")
        return ConversationHandler.END
    await update.message.reply_text("নতুন Admin User ID:", reply_markup=ReplyKeyboardRemove())
    return ADD_ADMIN_ID


async def add_admin_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_main(update.effective_user.id):
        return ConversationHandler.END
    try:
        nid = int(update.message.text.strip())
    except Exception:
        await update.message.reply_text("সঠিক ID দিন।")
        return ADD_ADMIN_ID
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO admins (user_id, role, added_at) VALUES (?,?,?)",
        (nid, "admin", datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ Admin: {nid}", reply_markup=admin_kb())
    try:
        await context.bot.send_message(nid, "🔧 আপনি Admin। /admin")
    except Exception:
        pass
    return ConversationHandler.END


async def remove_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_main(update.effective_user.id):
        await update.message.reply_text("শুধু Main Owner।")
        return ConversationHandler.END
    await update.message.reply_text("রিমুভ Admin ID:", reply_markup=ReplyKeyboardRemove())
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
        await update.message.reply_text("Main Owner রিমুভ নয়।", reply_markup=admin_kb())
        return ConversationHandler.END
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM admins WHERE user_id=?", (nid,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"🗑 Removed: {nid}", reply_markup=admin_kb())
    return ConversationHandler.END


async def transfer_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_main(update.effective_user.id):
        await update.message.reply_text("শুধু Main Owner।")
        return ConversationHandler.END
    await update.message.reply_text("নতুন Owner ID:", reply_markup=ReplyKeyboardRemove())
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
        await update.message.reply_text("নিজেকে নয়।", reply_markup=admin_kb())
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
    await update.message.reply_text(f"👑 Owner → {nid}", reply_markup=admin_kb())
    try:
        await context.bot.send_message(nid, "👑 আপনি Main Owner। /admin")
    except Exception:
        pass
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    kb = admin_kb() if is_admin(update.effective_user.id) else ReplyKeyboardRemove()
    await update.message.reply_text("বাতিল।", reply_markup=kb)
    return ConversationHandler.END


async def close_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Admin বন্ধ। /start", reply_markup=ReplyKeyboardRemove())


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    text = (update.message.text or "").strip()
    if text == "👁 Preview Start":
        await preview_start(update, context)
    elif text == "📊 Stats":
        await stats_cmd(update, context)
    elif text == "🏠 Close Admin":
        await close_admin(update, context)
    elif text == "🗑 Clear All Links":
        await clear_all_links(update, context)


def main():
    if not BOT_TOKEN or "YOUR_BOT" in BOT_TOKEN:
        print("ERROR: BOT_TOKEN")
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
            MessageHandler(filters.Regex(r"^🏷 Labels"), labels_start),
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
        states={ADD_ADMIN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin_receive)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    rm_adm = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^🗑 Remove Admin$"), remove_admin_start)],
        states={REMOVE_ADMIN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_admin_receive)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    tr_adm = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^👑 Ownership Transfer$"), transfer_start)],
        states={TRANSFER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, transfer_receive)]},
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

    print("Bot running... Admin:", MAIN_ADMIN_ID)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
