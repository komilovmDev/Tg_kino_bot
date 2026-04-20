import asyncio
import json
import logging
import os
import time
from functools import wraps

from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.types import Message
from aiogram.utils import executor
from aiogram.utils.exceptions import BotBlocked
from dotenv import load_dotenv

import db

load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", -1003928462353))

if not API_TOKEN:
    raise RuntimeError("API_TOKEN yo'q")
if not ADMIN_ID:
    raise RuntimeError("ADMIN_ID yo'q")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

KINO_DB_FILE = "kino_db.json"
CHANNEL_FILE = "channels.json"

last_used: dict = {}

LANG_FLAGS = {
    'ru': '🇷🇺 RU', 'uz': '🇺🇿 UZ', 'uk': '🇺🇦 UK', 'en': '🇺🇸 EN',
    'de': '🇩🇪 DE', 'fr': '🇫🇷 FR', 'tr': '🇹🇷 TR', 'ar': '🇸🇦 AR',
    'kk': '🇰🇿 KK', 'az': '🇦🇿 AZ', 'ky': '🇰🇬 KY', 'tg': '🇹🇯 TG',
    'es': '🇪🇸 ES', 'it': '🇮🇹 IT', 'pt': '🇵🇹 PT', 'zh': '🇨🇳 ZH',
    'ja': '🇯🇵 JA', 'ko': '🇰🇷 KO', 'hi': '🇮🇳 HI', 'fa': '🇮🇷 FA',
}


# ─── LOAD / SAVE ──────────────────────────────────────────────────────────────

def load_json(file, default):
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


kino_db = load_json(KINO_DB_FILE, {})
# migrate old format: plain int → {msg_id, count}
for _k, _v in kino_db.items():
    if isinstance(_v, int):
        kino_db[_k] = {"msg_id": _v, "count": 0}

CHANNELS: list = load_json(CHANNEL_FILE, ["@spritefx_tp"])


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def admin_only(func):
    @wraps(func)
    async def wrapper(message: Message):
        if message.from_user.id != ADMIN_ID:
            return await message.answer("❌ Ruxsat yo'q")
        return await func(message)
    return wrapper


async def check_sub(user_id: int) -> bool:
    for ch in CHANNELS:
        try:
            member = await bot.get_chat_member(ch, user_id)
            if member.status not in ["member", "creator", "administrator"]:
                return False
        except Exception as e:
            logging.warning(f"check_sub {user_id} in {ch}: {e}")
            return False
    return True


async def fetch_and_save_photo(user_id: int):
    try:
        photos = await bot.get_user_profile_photos(user_id, limit=1)
        if photos.total_count > 0:
            file_id = photos.photos[0][-1].file_id
            await db.save_photo(user_id, file_id)
    except Exception as e:
        logging.warning(f"fetch_photo {user_id}: {e}")


# ─── MIDDLEWARE ───────────────────────────────────────────────────────────────

class UserMiddleware(BaseMiddleware):
    async def on_pre_process_message(self, message: types.Message, _data: dict):
        if message.from_user and not message.from_user.is_bot:
            is_new = await db.upsert_user(message.from_user)
            if is_new:
                asyncio.create_task(fetch_and_save_photo(message.from_user.id))

    async def on_pre_process_callback_query(self, call: types.CallbackQuery, _data: dict):
        if call.from_user and not call.from_user.is_bot:
            await db.upsert_user(call.from_user)


dp.middleware.setup(UserMiddleware())


# ─── START ────────────────────────────────────────────────────────────────────

@dp.message_handler(commands=["start"])
async def start(message: Message):
    if not await check_sub(message.from_user.id):
        kb = types.InlineKeyboardMarkup()
        for ch in CHANNELS:
            kb.add(types.InlineKeyboardButton(f"📢 {ch}", url=f"https://t.me/{ch[1:]}"))
        kb.add(types.InlineKeyboardButton("✅ Tekshirish", callback_data="check"))
        return await message.answer(
            "❗ Botdan foydalanish uchun kanallarga obuna bo'ling:",
            reply_markup=kb
        )
    await message.answer("🎬 Kino botga xush kelibsiz!\nKod yuboring (k1, k2 ...)")


@dp.callback_query_handler(lambda c: c.data == "check")
async def check_callback(call: types.CallbackQuery):
    if await check_sub(call.from_user.id):
        await call.message.edit_text("✅ Obuna tasdiqlandi")
    else:
        await call.answer("❌ Hali obuna bo'lmadingiz", show_alert=True)


# ─── ADMIN: KINO ──────────────────────────────────────────────────────────────

@dp.message_handler(commands=["add"])
@admin_only
async def add_kino(message: Message):
    try:
        _, kod, msg_id = message.text.split()
        kino_db[kod.lower()] = {"msg_id": int(msg_id), "count": 0}
        save_json(KINO_DB_FILE, kino_db)
        await message.answer(f"✅ Kino qo'shildi: {kod}")
    except ValueError:
        await message.answer("❌ Format: /add k1 123")


@dp.message_handler(commands=["delete"])
@admin_only
async def delete_kino(message: Message):
    try:
        _, kod = message.text.split()
        kod = kod.lower()
        if kod in kino_db:
            del kino_db[kod]
            save_json(KINO_DB_FILE, kino_db)
            await message.answer(f"✅ O'chirildi: {kod}")
        else:
            await message.answer("❌ Topilmadi")
    except ValueError:
        await message.answer("❌ Format: /delete k1")


@dp.message_handler(commands=["list"])
@admin_only
async def list_kino(message: Message):
    if not kino_db:
        return await message.answer("📭 Bazada hech narsa yo'q")
    lines = [f"{kod} — {v['count']} ko'rildi" for kod, v in sorted(kino_db.items())]
    await message.answer("📋 Barcha kinolar:\n\n" + "\n".join(lines))


@dp.message_handler(commands=["top"])
@admin_only
async def top(message: Message):
    if not kino_db:
        return await message.answer("📭 Bo'sh")
    sorted_kino = sorted(kino_db.items(), key=lambda x: x[1]["count"], reverse=True)
    lines = [f"{i}. {kod} — {v['count']} marta" for i, (kod, v) in enumerate(sorted_kino[:10], 1)]
    await message.answer("📈 TOP kinolar:\n\n" + "\n".join(lines))


# ─── ADMIN: CHANNELS ──────────────────────────────────────────────────────────

@dp.message_handler(commands=["addchannel"])
@admin_only
async def add_channel(message: Message):
    try:
        _, ch = message.text.split()
        if ch not in CHANNELS:
            CHANNELS.append(ch)
            save_json(CHANNEL_FILE, CHANNELS)
        await message.answer(f"✅ Qo'shildi: {ch}")
    except ValueError:
        await message.answer("❌ Format: /addchannel @kanal")


@dp.message_handler(commands=["removechannel"])
@admin_only
async def remove_channel(message: Message):
    try:
        _, ch = message.text.split()
        if ch in CHANNELS:
            CHANNELS.remove(ch)
            save_json(CHANNEL_FILE, CHANNELS)
        await message.answer(f"✅ O'chirildi: {ch}")
    except ValueError:
        await message.answer("❌ Format: /removechannel @kanal")


@dp.message_handler(commands=["channels"])
@admin_only
async def list_channels(message: Message):
    text = "📢 Kanallar:\n\n" + "\n".join(f"• {ch}" for ch in CHANNELS)
    await message.answer(text)


# ─── ADMIN: СТАТИСТИКА ────────────────────────────────────────────────────────

@dp.message_handler(commands=["stat"])
@admin_only
async def stat_handler(message: Message):
    s = await db.get_stats()
    total = s["total"] or 1

    lang_lines = []
    other_count = 0
    for row in s["langs"]:
        code = (row["language_code"] or "").lower()
        if code in LANG_FLAGS:
            pct = round(row["cnt"] / total * 100, 1)
            lang_lines.append(f"{LANG_FLAGS[code]}: {pct}%")
        else:
            other_count += row["cnt"]
    if other_count:
        lang_lines.append(f"🏳️ Прочие: {round(other_count / total * 100, 1)}%")

    await message.answer(
        f"📊 Статистика\n\n"
        f"Пользователи:\n"
        f"👥 Всего: {s['total']}\n"
        f"🟢 Живые: {s['alive']}\n"
        f"💀 Мёртвые: {s['dead']}\n"
        f"🚫 Заблок: {s['blocked']}\n\n"
        f"Языки:\n" + "\n".join(lang_lines or ["Нет данных"]) + "\n"
        f"———\n\n"
        f"🆕 Новые: {s['new_today']} / {s['new_7d']} / {s['new_30d']}\n"
        f"   (сегодня / 7д / 30д)\n\n"
        f"🔍 В поиске: {s['searching']}\n"
        f"💬 Активных (24ч): {s['active_24h']}\n"
        f"✅ Запросов: {s['searches_today']} / {s['searches_7d']}\n"
        f"   (сегодня / 7д)\n\n"
        f"🎬 Кино в базе: {len(kino_db)}\n"
        f"📢 Кanallar: {len(CHANNELS)}\n"
        f"📈 Ср. запросов/юзер: {s['avg_searches']}"
    )


# ─── ADMIN: ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ ─────────────────────────────────────────────

@dp.message_handler(commands=["user"])
@admin_only
async def user_profile(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        return await message.answer("❌ Format: /user 123456789")
    try:
        uid = int(parts[1])
    except ValueError:
        return await message.answer("❌ ID должен быть числом")

    user = await db.get_user(uid)
    if not user:
        return await message.answer("❌ Пользователь не найден в базе")

    history = await db.get_user_history(uid)
    found_count = sum(1 for h in history if h["found"])

    name = " ".join(filter(None, [user["first_name"], user["last_name"]])) or "Без имени"
    username = f"@{user['username']}" if user["username"] else "—"
    lang_code = (user["language_code"] or "").lower()
    lang = LANG_FLAGS.get(lang_code, f"🏳️ {user['language_code'] or '?'}")
    status = "🚫 Заблокировал" if user["is_blocked"] else "✅ Активен"

    history_lines = [
        f"  {'✅' if h['found'] else '❌'} {h['kod']} — {str(h['created_at'])[:16]}"
        for h in history[:10]
    ]
    history_text = "\n".join(history_lines) if history_lines else "  Нет запросов"

    caption = (
        f"👤 <b>Профиль пользователя</b>\n\n"
        f"🆔 ID: <code>{uid}</code>\n"
        f"📛 Имя: {name}\n"
        f"🔗 Username: {username}\n"
        f"🌐 Язык: {lang}\n"
        f"📅 Зарегистрирован: {str(user['created_at'])[:16]}\n"
        f"🕐 Последний визит: {str(user['last_seen'])[:16]}\n"
        f"📊 Статус: {status}\n\n"
        f"🔍 Запросов: {len(history)} (найдено: {found_count})\n\n"
        f"📜 История (последние 10):\n{history_text}"
    )

    if user["photo_file_id"]:
        await message.answer_photo(photo=user["photo_file_id"], caption=caption, parse_mode="HTML")
    else:
        await message.answer(caption, parse_mode="HTML")


# ─── CHANNEL POSTS ────────────────────────────────────────────────────────────

@dp.channel_post_handler(content_types=types.ContentType.ANY)
async def save_post(message: types.Message):
    kod = (message.text or message.caption or "").lower().strip()
    if not kod.startswith("k"):
        return
    kino_db[kod] = {"msg_id": message.message_id, "count": 0}
    save_json(KINO_DB_FILE, kino_db)
    logging.info(f"Saved from channel: {kod} → {message.message_id}")


# ─── MAIN HANDLER ─────────────────────────────────────────────────────────────

@dp.message_handler(content_types=types.ContentType.TEXT)
async def handle(message: Message):
    user_id = message.from_user.id

    if user_id in last_used and time.time() - last_used[user_id] < 2:
        return
    last_used[user_id] = time.time()

    if not await check_sub(user_id):
        return await message.answer("❗ Avval obuna bo'ling /start")

    kod = message.text.lower().strip()
    found = kod in kino_db
    await db.log_search(user_id, kod, found)

    if not found:
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
        await db.mark_blocked(user_id)
    except Exception as e:
        logging.error(f"copy_message error kod={kod}: {e}")
        await message.answer("❌ Xatolik")


# ─── STARTUP ──────────────────────────────────────────────────────────────────

async def on_startup(_):
    await db.init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Bot started")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
