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
CHANNEL_ID = int(os.getenv("CHANNEL_ID", -1003928462353))

if not API_TOKEN:
    raise RuntimeError("API_TOKEN yo‘q")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# FILES
KINO_DB_FILE = "kino_db.json"
CHANNEL_FILE = "channels.json"

last_used = {}

# LOAD / SAVE
def load_json(file, default):
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


kino_db = load_json(KINO_DB_FILE, {})
CHANNELS = load_json(CHANNEL_FILE, ["@spritefx_tp"])

# eski formatni fix qilish
for k, v in kino_db.items():
    if isinstance(v, int):
        kino_db[k] = {"msg_id": v, "count": 0}


# ADMIN
def admin_only(func):
    @wraps(func)
    async def wrapper(message: Message):
        if message.from_user.id != ADMIN_ID:
            return await message.answer("❌ Ruxsat yo‘q")
        return await func(message)
    return wrapper


# SUB CHECK
async def check_sub(user_id: int):
    for ch in CHANNELS:
        try:
            member = await bot.get_chat_member(ch, user_id)
            if member.status not in ["member", "creator", "administrator"]:
                return False
        except:
            return False
    return True


# START
@dp.message_handler(commands=["start"])
async def start(message: Message):
    if not await check_sub(message.from_user.id):
        kb = types.InlineKeyboardMarkup()
        for ch in CHANNELS:
            kb.add(types.InlineKeyboardButton(f"📢 {ch}", url=f"https://t.me/{ch[1:]}"))
        kb.add(types.InlineKeyboardButton("✅ Tekshirish", callback_data="check"))
        return await message.answer("❗ Avval obuna bo‘ling:", reply_markup=kb)

    await message.answer("🎬 Kino botga xush kelibsiz!\nKod yuboring (k1, k2 ...)")


# CHECK BUTTON
@dp.callback_query_handler(lambda c: c.data == "check")
async def check_callback(call: types.CallbackQuery):
    if await check_sub(call.from_user.id):
        await call.message.edit_text("✅ Obuna tasdiqlandi")
    else:
        await call.answer("❌ Obuna bo‘lmadingiz", show_alert=True)


# ADD KINO
@dp.message_handler(commands=["add"])
@admin_only
async def add_kino(message: Message):
    try:
        _, kod, msg_id = message.text.split()
        kino_db[kod.lower()] = {"msg_id": int(msg_id), "count": 0}
        save_json(KINO_DB_FILE, kino_db)
        await message.answer("✅ Qo‘shildi")
    except:
        await message.answer("❌ /add k1 123")


# DELETE
@dp.message_handler(commands=["delete"])
@admin_only
async def delete_kino(message: Message):
    try:
        _, kod = message.text.split()
        if kod in kino_db:
            del kino_db[kod]
            save_json(KINO_DB_FILE, kino_db)
            await message.answer("✅ O‘chirildi")
        else:
            await message.answer("❌ Topilmadi")
    except:
        await message.answer("❌ /delete k1")


# TOP
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


# CHANNEL COMMANDS
@dp.message_handler(commands=["addchannel"])
@admin_only
async def add_channel(message: Message):
    try:
        _, ch = message.text.split()
        if ch not in CHANNELS:
            CHANNELS.append(ch)
            save_json(CHANNEL_FILE, CHANNELS)
        await message.answer("✅ Qo‘shildi")
    except:
        await message.answer("❌ /addchannel @kanal")


@dp.message_handler(commands=["removechannel"])
@admin_only
async def remove_channel(message: Message):
    try:
        _, ch = message.text.split()
        if ch in CHANNELS:
            CHANNELS.remove(ch)
            save_json(CHANNEL_FILE, CHANNELS)
        await message.answer("❌ O‘chirildi")
    except:
        await message.answer("❌ /removechannel @kanal")


@dp.message_handler(commands=["channels"])
@admin_only
async def list_channels(message: Message):
    await message.answer("\n".join(CHANNELS) or "Bo‘sh")


# SAVE POST
@dp.channel_post_handler(content_types=types.ContentType.ANY)
async def save_post(message: types.Message):
    kod = (message.text or message.caption or "").lower().strip()

    if not kod.startswith("k"):
        return

    kino_db[kod] = {"msg_id": message.message_id, "count": 0}
    save_json(KINO_DB_FILE, kino_db)
    logging.info(f"Saved: {kod}")


# MAIN
@dp.message_handler(content_types=types.ContentType.TEXT)
async def handle(message: Message):
    user_id = message.from_user.id

    if user_id in last_used and time.time() - last_used[user_id] < 2:
        return
    last_used[user_id] = time.time()

    if not await check_sub(user_id):
        return await message.answer("❗ Obuna bo‘ling")

    kod = message.text.lower().strip()

    if kod not in kino_db:
        return await message.answer("❌ Topilmadi")

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
    except Exception as e:
        logging.error(e)
        await message.answer("❌ Xatolik")


# START
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    executor.start_polling(dp, skip_updates=True)
