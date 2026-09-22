
import asyncio
import logging
import os
import sqlite3
from contextlib import closing
from html import escape
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    WebAppInfo,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder


# =========================================================
# EasyIncomezBot - Python + aiogram 3.x
# =========================================================
# 1) Install:
#       pip install -U aiogram
#
# 2) Put your BotFather token in BOT_TOKEN below, OR set:
#       BOT_TOKEN=your_token
#
# 3) Run:
#       python easyincomezbot.py
#
# Admin Telegram ID:
#       8289191009
# =========================================================

BOT_TOKEN = os.getenv("8818824501:AAGAHqX8in0PL4XAvfSkP12TEjvTLgIzi4E", "PASTE_YOUR_BOT_TOKEN_HERE")
ADMIN_ID = 8289191009
DB_FILE = "easyincomezbot.db"


DEFAULT_WELCOME = """🎉 Welcome to EasyIncomezBot! 💰

🚀 এখানে সহজ কিছু কাজ সম্পন্ন করে রিওয়ার্ড অর্জন করুন।

✨ যা যা করতে পারবেন:
📺 Ads দেখুন এবং পয়েন্ট অর্জন করুন
✅ বিভিন্ন Task সম্পূর্ণ করে Reward নিন
👥 বন্ধুদের Invite করে অতিরিক্ত Reward পান
💳 নির্দিষ্ট ব্যালেন্স হলে Withdrawal Request করুন

👇 শুরু করতে নিচের বাটনে ক্লিক করুন।

💙 EasyIncomezBot
⚡ Watch • Task • Earn"""

DEFAULTS = {
    "welcome_text": DEFAULT_WELCOME,
    "welcome_photo": "",
    "open_text": "🚀 Open App",
    "open_url": "",
    "channel_text": "📢 Channel",
    "channel_url": "",
    "support_text": "💬 Support",
    "support_url": "",
    "group_text": "👥 Group",
    "group_url": "",
    "reviews_text": "⭐ Reviews",
    "reviews_url": "",
}


# =========================================================
# DATABASE
# =========================================================

def db():
    return sqlite3.connect(DB_FILE)


def init_db():
    with closing(db()) as conn:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                balance REAL NOT NULL DEFAULT 0,
                referrals INTEGER NOT NULL DEFAULT 0
            )
        """)

        for key, value in DEFAULTS.items():
            cur.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)",
                (key, value),
            )

        conn.commit()


def get_setting(key: str) -> str:
    with closing(db()) as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?",
            (key,),
        ).fetchone()

    return row[0] if row else DEFAULTS.get(key, "")


def set_setting(key: str, value: str):
    with closing(db()) as conn:
        conn.execute(
            """
            INSERT INTO settings(key, value)
            VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            (key, value),
        )
        conn.commit()


def save_user(user):
    with closing(db()) as conn:
        conn.execute(
            """
            INSERT INTO users(user_id, username, first_name)
            VALUES(?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name
            """,
            (
                user.id,
                user.username or "",
                user.first_name or "",
            ),
        )
        conn.commit()


def get_user(user_id: int):
    with closing(db()) as conn:
        return conn.execute(
            """
            SELECT user_id, username, first_name, balance, referrals
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()


def set_balance(user_id: int, amount: float):
    with closing(db()) as conn:
        conn.execute(
            "UPDATE users SET balance = ? WHERE user_id = ?",
            (amount, user_id),
        )
        conn.commit()


def user_count() -> int:
    with closing(db()) as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM users"
        ).fetchone()[0]


def total_balance() -> float:
    with closing(db()) as conn:
        return conn.execute(
            "SELECT COALESCE(SUM(balance), 0) FROM users"
        ).fetchone()[0]


# =========================================================
# KEYBOARDS
# =========================================================

def admin_keyboard():
    b = InlineKeyboardBuilder()

    b.button(text="🚀 Open App", callback_data="edit:open")
    b.button(text="📢 Channel", callback_data="edit:channel")

    b.button(text="💬 Support", callback_data="edit:support")
    b.button(text="👥 Group", callback_data="edit:group")

    b.button(text="⭐ Reviews", callback_data="edit:reviews")
    b.button(text="📝 Welcome Text", callback_data="edit:welcome")

    b.button(text="🖼️ Welcome Photo", callback_data="edit:photo")
    b.button(text="🗑️ Remove Photo", callback_data="edit:remove_photo")

    b.button(text="👤 User Balance", callback_data="edit:balance")

    b.button(text="⚙️ Settings", callback_data="show:settings")
    b.button(text="👁️ Preview", callback_data="show:preview")

    b.adjust(2, 2, 2, 2, 1, 2)

    return b.as_markup()


def user_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🚀 Open App"),
                KeyboardButton(text="📢 Channel"),
            ],
            [
                KeyboardButton(text="💬 Support"),
                KeyboardButton(text="👥 Group"),
            ],
            [
                KeyboardButton(text="⭐ Reviews"),
                KeyboardButton(text="💰 My Balance"),
            ],
            [
                KeyboardButton(text="🔗 Referral"),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def admin_reply_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⚙️ Admin Panel")],
            [
                KeyboardButton(text="👤 User Balance"),
                KeyboardButton(text="📊 Statistics"),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def welcome_inline_keyboard():
    b = InlineKeyboardBuilder()

    open_url = get_setting("open_url")
    channel_url = get_setting("channel_url")
    support_url = get_setting("support_url")
    group_url = get_setting("group_url")
    reviews_url = get_setting("reviews_url")

    # Open App = Telegram Mini App Web App button.
    if open_url:
        b.button(
            text=get_setting("open_text") or "🚀 Open App",
            web_app=WebAppInfo(url=open_url),
        )

    row = []

    if channel_url:
        row.append(
            InlineKeyboardButton(
                text=get_setting("channel_text") or "📢 Channel",
                url=channel_url,
            )
        )

    if support_url:
        row.append(
            InlineKeyboardButton(
                text=get_setting("support_text") or "💬 Support",
                url=support_url,
            )
        )

    if row:
        b.row(*row)

    row = []

    if group_url:
        row.append(
            InlineKeyboardButton(
                text=get_setting("group_text") or "👥 Group",
                url=group_url,
            )
        )

    if reviews_url:
        row.append(
            InlineKeyboardButton(
                text=get_setting("reviews_text") or "⭐ Reviews",
                url=reviews_url,
            )
        )

    if row:
        b.row(*row)

    return b.as_markup()


# =========================================================
# FSM
# =========================================================

class EditState(StatesGroup):
    waiting_value = State()
    waiting_photo = State()
    waiting_balance = State()


router = Router()


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def valid_https(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme == "https" and bool(parsed.netloc)
    except Exception:
        return False


# =========================================================
# WELCOME / PREVIEW
# =========================================================

async def show_preview(target: Message):
    text = get_setting("welcome_text") or DEFAULT_WELCOME
    photo = get_setting("welcome_photo")
    markup = welcome_inline_keyboard()

    # No HTML parsing here so admin can safely use < > & in welcome text.
    if photo:
        try:
            await target.answer_photo(
                photo=photo,
                caption=text,
                reply_markup=markup,
                parse_mode=None,
            )
            return
        except Exception:
            # If an old/deleted file_id is stored, remove it and fall back to text.
            set_setting("welcome_photo", "")

    await target.answer(
        text,
        reply_markup=markup,
        parse_mode=None,
    )


async def show_admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return

    await message.answer(
        "👑 <b>EasyIncomezBot Admin Panel</b>\n\n"
        "নিচের বাটন থেকে Welcome, Photo, Open App, Channel, "
        "Support, Group, Reviews এবং User Balance পরিবর্তন করুন।",
        reply_markup=admin_keyboard(),
    )


# =========================================================
# START
# =========================================================

@router.message(Command("start"))
async def start_handler(message: Message):
    save_user(message.from_user)

    await show_preview(message)

    await message.answer(
        "👇 নিচের মেনু থেকেও অপশনগুলো ব্যবহার করতে পারবেন।",
        reply_markup=user_menu(),
    )


@router.message(Command("admin"))
async def admin_handler(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ আপনি Admin নন।")
        return

    await show_admin_panel(message)

    await message.answer(
        "Admin shortcuts:",
        reply_markup=admin_reply_menu(),
    )


# =========================================================
# ADMIN REPLY BUTTONS
# =========================================================

@router.message(F.text == "⚙️ Admin Panel")
async def admin_menu_button(message: Message):
    await admin_handler(message)


@router.message(F.text == "📊 Statistics")
async def stats_button(message: Message):
    if not is_admin(message.from_user.id):
        return

    await message.answer(
        f"📊 <b>Statistics</b>\n\n"
        f"👤 Users: <b>{user_count()}</b>\n"
        f"💰 Total Balance: <b>{total_balance():.2f}</b>",
        reply_markup=admin_keyboard(),
    )


# =========================================================
# ADMIN CALLBACKS
# =========================================================

EDIT_MAP = {
    "open": ("open_text", "open_url", "🚀 Open App"),
    "channel": ("channel_text", "channel_url", "📢 Channel"),
    "support": ("support_text", "support_url", "💬 Support"),
    "group": ("group_text", "group_url", "👥 Group"),
    "reviews": ("reviews_text", "reviews_url", "⭐ Reviews"),
}


@router.callback_query(F.data.startswith("edit:"))
async def edit_callback(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Not allowed", show_alert=True)
        return

    action = callback.data.split(":", 1)[1]
    await callback.answer()

    if action in EDIT_MAP:
        text_key, url_key, label = EDIT_MAP[action]

        current_text = get_setting(text_key)
        current_url = get_setting(url_key)

        await state.update_data(
            kind="link",
            text_key=text_key,
            url_key=url_key,
            label=label,
        )
        await state.set_state(EditState.waiting_value)

        await callback.message.answer(
            f"✏️ <b>{escape(label)}</b>\n\n"
            f"বর্তমান Button Text:\n"
            f"<code>{escape(current_text)}</code>\n\n"
            f"বর্তমান Link:\n"
            f"<code>{escape(current_url or 'Not set')}</code>\n\n"
            "এক লাইনে এভাবে পাঠান:\n"
            "<code>Button Text | https://example.com</code>\n\n"
            "Open App হলে অবশ্যই HTTPS Mini App URL দিন।",
        )

    elif action == "welcome":
        await state.update_data(kind="welcome")
        await state.set_state(EditState.waiting_value)

        await callback.message.answer(
            "📝 নতুন Welcome Text পাঠান।\n\n"
            "আপনি যত লাইন চান দিতে পারবেন।"
        )

    elif action == "photo":
        await state.set_state(EditState.waiting_photo)

        await callback.message.answer(
            "🖼️ এখন একটি Telegram Photo পাঠান।\n"
            "Photo-টি /start-এর Welcome message-এর উপরে দেখানো হবে।"
        )

    elif action == "remove_photo":
        set_setting("welcome_photo", "")

        await callback.message.answer(
            "✅ Welcome Photo remove করা হয়েছে।",
            reply_markup=admin_keyboard(),
        )

    elif action == "balance":
        await state.set_state(EditState.waiting_balance)

        await callback.message.answer(
            "👤 Balance Edit\n\n"
            "এই format-এ পাঠান:\n"
            "<code>USER_ID | AMOUNT</code>\n\n"
            "উদাহরণ:\n"
            "<code>123456789 | 250.50</code>",
        )


@router.callback_query(F.data == "show:settings")
async def settings_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Not allowed", show_alert=True)
        return

    await callback.answer()

    photo_status = "Set" if get_setting("welcome_photo") else "Not set"

    text = (
        "⚙️ <b>Current Settings</b>\n\n"
        f"🚀 Open App:\n<code>{escape(get_setting('open_url') or 'Not set')}</code>\n\n"
        f"📢 Channel:\n<code>{escape(get_setting('channel_url') or 'Not set')}</code>\n\n"
        f"💬 Support:\n<code>{escape(get_setting('support_url') or 'Not set')}</code>\n\n"
        f"👥 Group:\n<code>{escape(get_setting('group_url') or 'Not set')}</code>\n\n"
        f"⭐ Reviews:\n<code>{escape(get_setting('reviews_url') or 'Not set')}</code>\n\n"
        f"🖼️ Welcome Photo: <code>{photo_status}</code>"
    )

    await callback.message.answer(
        text,
        reply_markup=admin_keyboard(),
    )


@router.callback_query(F.data == "show:preview")
async def preview_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Not allowed", show_alert=True)
        return

    await callback.answer()
    await show_preview(callback.message)


# =========================================================
# ADMIN FSM: TEXT / LINKS
# =========================================================

@router.message(EditState.waiting_value, F.text)
async def edit_text_handler(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    data = await state.get_data()
    kind = data.get("kind")

    # Welcome text
    if kind == "welcome":
        new_text = message.text.strip()

        if not new_text:
            await message.answer(
                "❌ Text খালি হতে পারবে না। আবার পাঠান।"
            )
            return

        set_setting("welcome_text", new_text)
        await state.clear()

        await message.answer(
            "✅ Welcome Text saved!",
            reply_markup=admin_keyboard(),
        )
        return

    # Button text + URL
    if kind == "link":
        parts = message.text.split("|", 1)

        if len(parts) != 2:
            await message.answer(
                "❌ Format ভুল।\n\n"
                "এভাবে পাঠান:\n"
                "<code>Button Text | https://example.com</code>",
            )
            return

        button_text = parts[0].strip()
        url = parts[1].strip()

        if not button_text:
            await message.answer(
                "❌ Button Text খালি হতে পারবে না।"
            )
            return

        if not valid_https(url):
            await message.answer(
                "❌ Link অবশ্যই valid HTTPS URL হতে হবে।"
            )
            return

        set_setting(data["text_key"], button_text)
        set_setting(data["url_key"], url)

        await state.clear()

        await message.answer(
            "✅ Successfully saved!\n\n"
            f"🔘 Button: {escape(button_text)}\n"
            f"🔗 URL: <code>{escape(url)}</code>",
            reply_markup=admin_keyboard(),
        )
        return

    await state.clear()


# =========================================================
# ADMIN PHOTO
# =========================================================

@router.message(EditState.waiting_photo, F.photo)
async def photo_handler(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    file_id = message.photo[-1].file_id
    set_setting("welcome_photo", file_id)

    await state.clear()

    await message.answer(
        "✅ Welcome Photo saved!",
        reply_markup=admin_keyboard(),
    )


@router.message(EditState.waiting_photo)
async def photo_wrong_type(message: Message):
    if is_admin(message.from_user.id):
        await message.answer(
            "❌ একটি Telegram Photo পাঠান।"
        )


# =========================================================
# ADMIN BALANCE
# =========================================================

@router.message(EditState.waiting_balance, F.text)
async def balance_handler(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    parts = message.text.split("|", 1)

    if len(parts) != 2:
        await message.answer(
            "❌ Format:\n<code>USER_ID | AMOUNT</code>",
        )
        return

    try:
        user_id = int(parts[0].strip())
        amount = float(parts[1].strip())
    except ValueError:
        await message.answer(
            "❌ USER_ID integer এবং AMOUNT number হতে হবে।"
        )
        return

    if amount < 0:
        await message.answer(
            "❌ Balance negative করা যাবে না।"
        )
        return

    if get_user(user_id) is None:
        await message.answer(
            "❌ এই User ID database-এ নেই।"
        )
        return

    set_balance(user_id, amount)
    await state.clear()

    await message.answer(
        f"✅ Balance updated.\n\n"
        f"👤 User ID: <code>{user_id}</code>\n"
        f"💰 Balance: <b>{amount:.2f}</b>",
        reply_markup=admin_keyboard(),
    )


# =========================================================
# USER MENU
# =========================================================

async def send_link_or_not(
    message: Message,
    url_key: str,
    text_key: str,
):
    url = get_setting(url_key)

    if not url:
        await message.answer(
            "⚠️ এই link এখনো Admin সেট করেননি।"
        )
        return

    button_text = get_setting(text_key) or "Open"

    await message.answer(
        f"<b>{escape(button_text)}</b>",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔗 Open",
                        url=url,
                    )
                ]
            ]
        ),
    )


@router.message(F.text == "🚀 Open App")
async def user_open_app(message: Message):
    url = get_setting("open_url")

    if not url:
        await message.answer(
            "⚠️ Open App link এখনো সেট করা হয়নি।"
        )
        return

    await message.answer(
        "🚀 Mini App খুলুন:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=get_setting("open_text") or "🚀 Open App",
                        web_app=WebAppInfo(url=url),
                    )
                ]
            ]
        ),
    )


@router.message(F.text == "📢 Channel")
async def user_channel(message: Message):
    await send_link_or_not(
        message,
        "channel_url",
        "channel_text",
    )


@router.message(F.text == "💬 Support")
async def user_support(message: Message):
    await send_link_or_not(
        message,
        "support_url",
        "support_text",
    )


@router.message(F.text == "👥 Group")
async def user_group(message: Message):
    await send_link_or_not(
        message,
        "group_url",
        "group_text",
    )


@router.message(F.text == "⭐ Reviews")
async def user_reviews(message: Message):
    await send_link_or_not(
        message,
        "reviews_url",
        "reviews_text",
    )


@router.message(F.text == "💰 My Balance")
async def user_balance(message: Message):
    save_user(message.from_user)

    row = get_user(message.from_user.id)
    balance = row[3] if row else 0

    await message.answer(
        f"💰 <b>Your Balance</b>\n\n"
        f"💵 Balance: <b>{balance:.2f}</b>",
    )


@router.message(F.text == "🔗 Referral")
async def referral(message: Message, bot: Bot):
    me = await bot.me()

    link = (
        f"https://t.me/{me.username}?start={message.from_user.id}"
        if me.username
        else "Bot username not available"
    )

    await message.answer(
        "🔗 <b>Your Referral Link</b>\n\n"
        f"<code>{escape(link)}</code>\n\n"
        "এই লিংক ভবিষ্যতের referral reward system-এ ব্যবহার করা যাবে।"
    )


# =========================================================
# CANCEL
# =========================================================

@router.message(Command("cancel"))
async def cancel_handler(
    message: Message,
    state: FSMContext,
):
    await state.clear()
    await message.answer(
        "❌ Current edit cancelled."
    )


# =========================================================
# MAIN
# =========================================================

async def main():
    if BOT_TOKEN == "PASTE_YOUR_BOT_TOKEN_HERE":
        raise RuntimeError(
            "BOT_TOKEN সেট করুন। Environment variable BOT_TOKEN "
            "অথবা কোডের BOT_TOKEN-এ token বসান।"
        )

    init_db()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        ),
    )

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    logging.basicConfig(level=logging.INFO)

    print("EasyIncomezBot is running...")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
