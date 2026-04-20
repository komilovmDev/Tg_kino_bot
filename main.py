import json
import logging
import os
import time

from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.utils import executor
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 2064891580))

if not API_TOKEN:
    raise RuntimeError('API_TOKEN is not set')
# if not ADMIN_ID:
#     raise RuntimeError('ADMIN_ID is not set')

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# 🔥 KANALLAR (majburiy obuna)
CHANNELS = [
    '@spritefx_tp',
    # '@kanal2',
]

CHANNEL_ID = -1003928462353

DB_FILE = 'kino_db.json'
USERS_FILE = 'users.json'

# ===== DB =====
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

            # eski formatni yangiga o'tkazish
            for k, v in data.items():
                if isinstance(v, int):
                    data[k] = {"msg_id": v, "count": 0}

            return data
    return {}

def save_db(db):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

kino_db = load_db()

# ===== USERS =====
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return set(json.load(f))
    return set()

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(list(users), f)

users = load_users()

# ===== ACTIVE USERS =====
active_users = {}

# ===== ANTI SPAM =====
last_used = {}

# ===== CHECK SUB =====
async def check_sub(user_id: int):
    for ch in CHANNELS:
        try:
            member = await bot.get_chat_member(ch, user_id)
            if member.status not in ['member', 'creator', 'administrator']:
                return False
        except:
            return False
    return True

# ===== START =====
@dp.message_handler(commands=['start'])
async def start_handler(message: Message):
    if not await check_sub(message.from_user.id):
        btn = types.InlineKeyboardMarkup()

        for ch in CHANNELS:
            btn.add(types.InlineKeyboardButton(
                f"📢 {ch}",
                url=f"https://t.me/{ch[1:]}"
            ))

        btn.add(types.InlineKeyboardButton(
            "✅ Tekshirish",
            callback_data="check_sub"
        ))

        await message.answer(
            "❗ Botdan foydalanish uchun kanallarga obuna bo‘ling:",
            reply_markup=btn
        )
        return

    await message.answer("🎬 Kino botga xush kelibsiz!\nKod yuboring (k1, k2 ...)")

# ===== CHECK BUTTON =====
@dp.callback_query_handler(lambda c: c.data == "check_sub")
async def check_button(call: types.CallbackQuery):
    if await check_sub(call.from_user.id):
        await call.message.edit_text("✅ Endi foydalanishingiz mumkin!")
    else:
        await call.answer("❌ Hali obuna bo‘lmadingiz", show_alert=True)

# ===== ADD =====
@dp.message_handler(commands=['add'])
async def add_kino(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        _, kod, msg_id = message.text.split()

        kino_db[kod.lower()] = {
            "msg_id": int(msg_id),
            "count": 0
        }

        save_db(kino_db)
        await message.answer(f"✅ Qo‘shildi: {kod}")
    except:
        await message.answer("❌ Format: /add k1 45")

# ===== DELETE =====
@dp.message_handler(commands=['delete'])
async def delete_kino(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        _, kod = message.text.split()
        kod = kod.lower()

        if kod in kino_db:
            del kino_db[kod]
            save_db(kino_db)
            await message.answer("✅ O‘chirildi")
        else:
            await message.answer("❌ Topilmadi")
    except:
        await message.answer("❌ Format: /delete k1")

# ===== STATS =====
@dp.message_handler(commands=['stats'])
async def stats(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    now = time.time()
    active_24h = sum(1 for t in active_users.values() if now - t < 86400)

    await message.answer(
        f"📊 Statistika:\n\n"
        f"👤 Userlar: {len(users)}\n"
        f"⚡ Aktiv (24h): {active_24h}\n"
        f"🎬 Kinolar: {len(kino_db)}"
    )

# ===== TOP =====
@dp.message_handler(commands=['top'])
async def top_kino(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    if not kino_db:
        await message.answer("📭 Bo‘sh")
        return

    sorted_kino = sorted(
        kino_db.items(),
        key=lambda x: x[1]["count"],
        reverse=True
    )

    text = "📈 TOP kinolar:\n\n"

    for i, (kod, data) in enumerate(sorted_kino[:10], start=1):
        text += f"{i}. {kod} — {data['count']} marta\n"

    await message.answer(text)

# ===== CHANNEL POST AUTO SAVE =====
@dp.channel_post_handler(content_types=types.ContentType.ANY)
async def save_post(message: types.Message):
    kod = None

    if message.caption:
        kod = message.caption.strip().lower()
    elif message.text:
        kod = message.text.strip().lower()

    if not kod or not kod.startswith('k'):
        return

    kino_db[kod] = {
        "msg_id": message.message_id,
        "count": 0
    }

    save_db(kino_db)

# ===== MAIN MESSAGE =====
@dp.message_handler(content_types=types.ContentType.ANY)
async def message_handler(message: Message):
    user_id = message.from_user.id

    # anti spam
    if user_id in last_used and time.time() - last_used[user_id] < 2:
        return
    last_used[user_id] = time.time()

    # user save
    users.add(user_id)
    save_users(users)

    # active user
    active_users[user_id] = time.time()

    if not message.text or message.text.startswith('/'):
        return

    if not await check_sub(user_id):
        await message.answer("❗ Avval obuna bo‘ling /start")
        return

    kod = message.text.strip().lower()

    if kod not in kino_db:
        await message.answer("❌ Bunday kod yo‘q")
        return

    kino = kino_db[kod]
    kino["count"] += 1
    save_db(kino_db)

    try:
        await bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=CHANNEL_ID,
            message_id=kino["msg_id"]
        )
    except:
        await message.answer("❌ Xatolik")

# ===== STARTUP =====
async def on_startup(_):
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Bot ishga tushdi")

# ===== RUN =====
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
