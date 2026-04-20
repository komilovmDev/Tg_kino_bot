import asyncio
import json
import logging
import os
from functools import wraps

from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.types import Message
from aiogram.utils import executor
from aiogram.utils.exceptions import BotBlocked
from dotenv import load_dotenv

import db

load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

if not API_TOKEN:
    raise RuntimeError('API_TOKEN is not set')
if not ADMIN_ID:
    raise RuntimeError('ADMIN_ID is not set')

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

CHANNEL_USERNAME = '@spritefx_tp'
CHANNEL_ID = -1003928462353
KINO_DB_FILE = 'kino_db.json'

LANG_FLAGS = {
    'ru': '🇷🇺 RU', 'uz': '🇺🇿 UZ', 'uk': '🇺🇦 UK', 'en': '🇺🇸 EN',
    'de': '🇩🇪 DE', 'fr': '🇫🇷 FR', 'tr': '🇹🇷 TR', 'ar': '🇸🇦 AR',
    'kk': '🇰🇿 KK', 'az': '🇦🇿 AZ', 'ky': '🇰🇬 KY', 'tg': '🇹🇯 TG',
    'es': '🇪🇸 ES', 'it': '🇮🇹 IT', 'pt': '🇵🇹 PT', 'zh': '🇨🇳 ZH',
    'ja': '🇯🇵 JA', 'ko': '🇰🇷 KO', 'hi': '🇮🇳 HI', 'fa': '🇮🇷 FA',
}


# ─── KINO DB ──────────────────────────────────────────────────────────────────

def load_kino_db() -> dict:
    if os.path.exists(KINO_DB_FILE):
        with open(KINO_DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_kino_db(data: dict):
    with open(KINO_DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


kino_db = load_kino_db()


# ─── HELPERS ──────────────────────────────────────────────────────────────────

async def fetch_and_save_photo(user_id: int):
    try:
        photos = await bot.get_user_profile_photos(user_id, limit=1)
        if photos.total_count > 0:
            file_id = photos.photos[0][-1].file_id
            await db.save_photo(user_id, file_id)
    except Exception as e:
        logging.warning(f'fetch_photo error for {user_id}: {e}')


async def check_sub(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'creator', 'administrator']
    except Exception as e:
        logging.warning(f'check_sub error for {user_id}: {e}')
        return False


def admin_only(func):
    @wraps(func)
    async def wrapper(message: Message):
        if message.from_user.id != ADMIN_ID:
            await message.answer("❌ Sizda ruxsat yo'q.")
            return
        await func(message)
    return wrapper


# ─── MIDDLEWARE: авто-регистрация пользователей ───────────────────────────────

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


# ─── USER COMMANDS ────────────────────────────────────────────────────────────

@dp.message_handler(commands=['start'])
async def start_handler(message: Message):
    if not await check_sub(message.from_user.id):
        btn = types.InlineKeyboardMarkup()
        btn.add(types.InlineKeyboardButton(
            "📢 Obuna bo'lish", url=f"https://t.me/{CHANNEL_USERNAME[1:]}"
        ))
        btn.add(types.InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub"))
        await message.answer(
            "❗ Botdan foydalanish uchun kanalga obuna bo'ling:",
            reply_markup=btn
        )
        return
    await message.answer("🎬 Kino botga xush kelibsiz!\n\nKod yuboring (masalan: k1)")


@dp.callback_query_handler(lambda c: c.data == "check_sub")
async def check_button(call: types.CallbackQuery):
    if await check_sub(call.from_user.id):
        await call.message.edit_text("✅ Rahmat! Endi kod yuboring.")
    else:
        await call.answer("❌ Hali obuna bo'lmadingiz", show_alert=True)


@dp.message_handler(commands=['test'])
async def test(message: Message):
    await message.answer("✅ Bot ishlayapti!")


# ─── ADMIN: KINO MANAGEMENT ───────────────────────────────────────────────────

@dp.message_handler(commands=['add'])
@admin_only
async def add_kino(message: Message):
    try:
        _, kod, msg_id = message.text.split()
        kino_db[kod.lower()] = int(msg_id)
        save_kino_db(kino_db)
        await message.answer(f"✅ Qo'shildi: {kod} → {msg_id}")
    except ValueError:
        await message.answer("❌ Format: /add k1 45")


@dp.message_handler(commands=['delete'])
@admin_only
async def delete_kino(message: Message):
    try:
        _, kod = message.text.split()
        kod = kod.lower()
        if kod in kino_db:
            del kino_db[kod]
            save_kino_db(kino_db)
            await message.answer(f"✅ O'chirildi: {kod}")
        else:
            await message.answer(f"❌ Bunday kod yo'q: {kod}")
    except ValueError:
        await message.answer("❌ Format: /delete k1")


@dp.message_handler(commands=['list'])
@admin_only
async def list_kino(message: Message):
    if not kino_db:
        await message.answer("📭 Bazada hech narsa yo'q.")
        return
    lines = [f"{kod} → {msg_id}" for kod, msg_id in sorted(kino_db.items())]
    await message.answer("📋 Barcha kinolar:\n\n" + "\n".join(lines))


# ─── ADMIN: СТАТИСТИКА ────────────────────────────────────────────────────────

@dp.message_handler(commands=['stat'])
@admin_only
async def stat_handler(message: Message):
    s = await db.get_stats()
    total = s['total'] or 1

    lang_lines = []
    other_count = 0
    for row in s['langs']:
        code = (row['language_code'] or '').lower()
        if code in LANG_FLAGS:
            pct = round(row['cnt'] / total * 100, 1)
            lang_lines.append(f"{LANG_FLAGS[code]}: {pct}%")
        else:
            other_count += row['cnt']

    if other_count:
        lang_lines.append(f"🏳️ Прочие: {round(other_count / total * 100, 1)}%")

    langs_text = "\n".join(lang_lines) if lang_lines else "Нет данных"

    text = (
        f"📊 Статистика\n\n"
        f"Пользователи:\n"
        f"👥 Всего: {s['total']}\n"
        f"🟢 Живые: {s['alive']}\n"
        f"💀 Мёртвые: {s['dead']}\n"
        f"🚫 Заблок: {s['blocked']}\n\n"
        f"Языки:\n{langs_text}\n"
        f"———\n\n"
        f"🆕 Новые: {s['new_today']} / {s['new_7d']} / {s['new_30d']}\n"
        f"   (сегодня / 7д / 30д)\n\n"
        f"🔍 В поиске: {s['searching']}\n"
        f"💬 Активных (24ч): {s['active_24h']}\n"
        f"✅ Запросов: {s['searches_today']} / {s['searches_7d']}\n"
        f"   (сегодня / 7д)\n\n"
        f"📈 Ср. запросов/юзер: {s['avg_searches']}"
    )
    await message.answer(text)


# ─── ADMIN: ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ ─────────────────────────────────────────────

@dp.message_handler(commands=['user'])
@admin_only
async def user_profile(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Format: /user 123456789")
        return

    try:
        uid = int(parts[1])
    except ValueError:
        await message.answer("❌ ID должен быть числом")
        return

    user = await db.get_user(uid)
    if not user:
        await message.answer("❌ Пользователь не найден в базе")
        return

    history = await db.get_user_history(uid)
    found_count = sum(1 for h in history if h['found'])

    name = ' '.join(filter(None, [user['first_name'], user['last_name']])) or 'Без имени'
    username = f"@{user['username']}" if user['username'] else '—'
    lang_code = (user['language_code'] or '').lower()
    lang = LANG_FLAGS.get(lang_code, f"🏳️ {user['language_code'] or '?'}")
    status = "🚫 Заблокировал" if user['is_blocked'] else "✅ Активен"

    history_lines = []
    for h in history[:10]:
        icon = "✅" if h['found'] else "❌"
        dt = str(h['created_at'])[:16]
        history_lines.append(f"  {icon} {h['kod']} — {dt}")
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

    if user['photo_file_id']:
        await message.answer_photo(
            photo=user['photo_file_id'],
            caption=caption,
            parse_mode='HTML'
        )
    else:
        await message.answer(caption, parse_mode='HTML')


# ─── CHANNEL POSTS ────────────────────────────────────────────────────────────

@dp.channel_post_handler(content_types=types.ContentType.ANY)
async def save_post(message: types.Message):
    kod = None
    if message.caption:
        kod = message.caption.strip().lower()
    elif message.text:
        kod = message.text.strip().lower()

    if not kod:
        return

    kino_db[kod] = message.message_id
    save_kino_db(kino_db)
    logging.info(f"Saved from channel: {kod} → {message.message_id}")


# ─── MAIN MESSAGE HANDLER ─────────────────────────────────────────────────────

@dp.message_handler(content_types=types.ContentType.ANY)
async def message_handler(message: Message):
    if message.forward_from_chat:
        logging.info(f"Forward message ID: {message.forward_from_message_id}")
        return

    if not message.text or message.text.startswith('/'):
        return

    if not await check_sub(message.from_user.id):
        await message.answer("❗ Avval kanalga obuna bo'ling /start")
        return

    kod = message.text.lower()
    found = kod in kino_db

    await db.log_search(message.from_user.id, kod, found)

    if not found:
        await message.answer("❌ Bunday kod yo'q.")
        return

    try:
        await bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=CHANNEL_ID,
            message_id=kino_db[kod]
        )
    except BotBlocked:
        await db.mark_blocked(message.from_user.id)
    except Exception as e:
        logging.error(f"copy_message error for kod={kod}: {e}")
        await message.answer("❌ Kino topilmadi yoki xatolik.")


# ─── STARTUP ──────────────────────────────────────────────────────────────────

async def on_startup(_):
    await db.init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Bot started")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
