import json
import logging
import os

from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.utils import executor
from dotenv import load_dotenv

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
DB_FILE = 'kino_db.json'


def load_db() -> dict:
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_db(db: dict):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


kino_db = load_db()


async def check_sub(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'creator', 'administrator']
    except Exception as e:
        logging.warning(f'check_sub error for {user_id}: {e}')
        return False


@dp.message_handler(commands=['start'])
async def start_handler(message: Message):
    if not await check_sub(message.from_user.id):
        btn = types.InlineKeyboardMarkup()
        btn.add(types.InlineKeyboardButton(
            "📢 Obuna bo'lish",
            url=f"https://t.me/{CHANNEL_USERNAME[1:]}"
        ))
        btn.add(types.InlineKeyboardButton(
            "✅ Tekshirish",
            callback_data="check_sub"
        ))
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


@dp.message_handler(commands=['add'])
async def add_kino(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Sizda ruxsat yo'q.")
        return
    try:
        _, kod, msg_id = message.text.split()
        kino_db[kod.lower()] = int(msg_id)
        save_db(kino_db)
        await message.answer(f"✅ Qo'shildi:\n{kod} → {msg_id}")
    except ValueError:
        await message.answer("❌ Format: /add k1 45")


@dp.message_handler(commands=['delete'])
async def delete_kino(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Sizda ruxsat yo'q.")
        return
    try:
        _, kod = message.text.split()
        kod = kod.lower()
        if kod in kino_db:
            del kino_db[kod]
            save_db(kino_db)
            await message.answer(f"✅ O'chirildi: {kod}")
        else:
            await message.answer(f"❌ Bunday kod yo'q: {kod}")
    except ValueError:
        await message.answer("❌ Format: /delete k1")


@dp.message_handler(commands=['list'])
async def list_kino(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Sizda ruxsat yo'q.")
        return
    if not kino_db:
        await message.answer("📭 Bazada hech narsa yo'q.")
        return
    lines = [f"{kod} → {msg_id}" for kod, msg_id in sorted(kino_db.items())]
    await message.answer("📋 Barcha kinolar:\n\n" + "\n".join(lines))


@dp.message_handler(commands=['test'])
async def test(message: Message):
    await message.answer("✅ Bot ishlayapti!")


@dp.channel_post_handler(content_types=types.ContentType.ANY)
async def save_post(message: types.Message):
    kod = None
    if message.caption:
        kod = message.caption.strip().lower()
    elif message.text:
        kod = message.text.strip().lower()

    if not kod:
        logging.info("Channel post received without caption/text, skipping")
        return

    kino_db[kod] = message.message_id
    save_db(kino_db)
    logging.info(f"Saved from channel: {kod} → {message.message_id}")


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
    if kod not in kino_db:
        await message.answer("❌ Bunday kod yo'q.")
        return

    try:
        await bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=CHANNEL_ID,
            message_id=kino_db[kod]
        )
    except Exception as e:
        logging.error(f"copy_message error for kod={kod}: {e}")
        await message.answer("❌ Kino topilmadi yoki xatolik.")


async def on_startup(_):
    await bot.delete_webhook(drop_pending_updates=True)
    logging.info("Bot started, webhook deleted")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
