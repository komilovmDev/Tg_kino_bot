import asyncio
import json
import logging
import os
import time

from functools import wraps

from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.utils import executor
from aiogram.utils.exceptions import BotBlocked
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

if not API_TOKEN:
    raise RuntimeError("API_TOKEN yo‘q")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# ─── CONFIG ─────────────────────────────
CHANNELS = ['@spritefx_tp']
CHANNEL_ID = -1003928462353

KINO_DB_FILE = "kino_db.json"
USERS_FILE = "users.json"

last_used = {}
users = set()


# ─── DB HELPERS ─────────────────────────
def load_json(file, default):
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


kino_db = load_json(KINO_DB_FILE, {})


# ─── SUB CHECK ─────────────────────────
async def check_sub(user_id: int):
    for ch in CHANNELS:
        try:
            member = await bot.get_chat_member(ch, user_id)
            if member.status not in ["member", "creator", "administrator"]:
                return False
        except:
            return False
    return True


# ─── ADMIN DECORATOR ────────────────────
def admin_only(func):
    @wraps(func)
    async def wrapper(message: Message):
        if message.from_user.id != ADMIN_ID:
            return await message.answer("❌ Ruxsat yo‘q")
        return await func(message)
    return wrapper


# ─── START ─────────────────────────────
@dp.message_handler(commands=["start"])
async def start(message: Message):
    if not await check_sub(message.from_user.id):
        kb = types.InlineKeyboardMarkup()
        for ch in CHANNELS:
            kb.add(types.InlineKeyboardButton(f"📢 {ch}", url=f"https://t.me/{ch[1:]}"))
        kb.add(types.InlineKeyboardButton("✅ Tekshirish", callback_data="check"))
        return await message.answer("❗ Avval obuna bo‘ling:", reply_markup=kb)

    await message.answer("🎬 Kino botga xush kelibsiz!\nKod yuboring (k1, k2 ...)")


# ─── CHECK SUB BUTTON ───────────────────
@dp.callback_query_handler(lambda c: c.data == "check")
async def check(call: types.CallbackQuery):
    if await check_sub(call.from_user.id):
        await call.message.edit_text("✅ Obuna tasdiqlandi")
    else:
        await call.answer("❌ Hali obuna bo‘lmadingiz", show_alert=True)


# ─── ADD KINO ───────────────────────────
@dp.message_handler(commands=["add"])
@admin_only
async def add_kino(message: Message):
    try:
        _, kod, msg_id = message.text.split()
        kino_db[kod.lower()] = {"msg_id": int(msg_id), "count": 0}
        save_json(KINO_DB_FILE, kino_db)
        await message.answer("✅ Qo‘shildi")
    except:
        await message.answer("❌ Format: /add k1 123")


# ─── DELETE KINO ────────────────────────
@dp.message_handler(commands=["delete"])
@admin_only
async def delete_kino(message: Message):
    try:
        _, kod = message.text.split()
        kod = kod.lower()

        if kod in kino_db:
            del kino_db[kod]
            save_json(KINO_DB_FILE, kino_db)
            await message.answer("✅ O‘chirildi")
        else:
            await message.answer("❌ Topilmadi")
    except:
        await message.answer("❌ Format: /delete k1")


# ─── TOP LIST ───────────────────────────
@dp.message_handler(commands=["top"])
@admin_only
async def top(message: Message):
    if not kino_db:
        return await message.answer("📭 Bo‘sh")

    sorted_kino = sorted(kino_db.items(), key=lambda x: x[1]["count"], reverse=True)

    text = "📈 TOP kinolar:\n\n"
    for i, (kod, v) in enumerate(sorted_kino[:10], 1):
        text += f"{i}. {kod} — {v['count']} marta\n"

    await message.answer(text)


# ─── STATS ──────────────────────────────
@dp.message_handler(commands=["stats"])
@admin_only
async def stats(message: Message):
    await message.answer(
        f"📊 Statistika:\n\n"
        f"👤 Users: {len(users)}\n"
        f"🎬 Kinolar: {len(kino_db)}"
    )


# ─── CHANNEL SAVE POST ──────────────────
@dp.channel_post_handler(content_types=types.ContentType.ANY)
async def save_post(message: types.Message):
    kod = (message.text or message.caption or "").lower().strip()

    if not kod.startswith("k"):
        return

    kino_db[kod] = {
        "msg_id": message.message_id,
        "count": 0
    }

    save_json(KINO_DB_FILE, kino_db)
    logging.info(f"Saved: {kod}")


# ─── MAIN HANDLER ───────────────────────
@dp.message_handler(content_types=types.ContentType.TEXT)
async def handle(message: Message):
    user_id = message.from_user.id

    # anti spam
    if user_id in last_used and time.time() - last_used[user_id] < 2:
        return
    last_used[user_id] = time.time()

    if not await check_sub(user_id):
        return await message.answer("❗ Avval obuna bo‘ling")

    kod = message.text.lower().strip()

    if kod not in kino_db:
        return await message.answer("❌ Kod topilmadi")

    kino_db[kod]["count"] += 1
    save_json(KINO_DB_FILE, kino_db)

    try:
        await bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=CHANNEL_ID,
            message_id=kino_db[kod]["msg_id"]
        )
    except BotBlocked:
        await message.answer("❌ Bot bloklangan")
    except:
        await message.answer("❌ Xatolik")


# ─── START BOT ──────────────────────────
async def on_startup(_):
    logging.info("Bot ishga tushdi")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
