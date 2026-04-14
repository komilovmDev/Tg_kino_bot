import logging
import os

from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.utils import executor
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')
if not API_TOKEN:
    raise RuntimeError('API_TOKEN is not set')

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# 📌 KANAL
CHANNEL_USERNAME = '@spritefx_tp'
CHANNEL_ID = -1003928462353

# 📌 DATABASE (vaqtinchalik)
kino_db = {}

# 📌 OBUNA TEKSHIRISH
async def check_sub(user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'creator', 'administrator']
    except:
        return False

# 📌 START
@dp.message_handler(commands=['start'])
async def start_handler(message: Message):
    if not await check_sub(message.from_user.id):
        btn = types.InlineKeyboardMarkup()
        btn.add(types.InlineKeyboardButton(
            "📢 Obuna bo‘lish",
            url=f"https://t.me/{CHANNEL_USERNAME[1:]}"
        ))
        btn.add(types.InlineKeyboardButton(
            "✅ Tekshirish",
            callback_data="check_sub"
        ))

        await message.answer(
            "❗ Botdan foydalanish uchun kanalga obuna bo‘ling:",
            reply_markup=btn
        )
        return

    await message.answer("🎬 Kino botga xush kelibsiz!\n\nKod yuboring (masalan: k1)")

# 📌 CHECK BUTTON
@dp.callback_query_handler(lambda c: c.data == "check_sub")
async def check_button(call: types.CallbackQuery):
    if await check_sub(call.from_user.id):
        await call.message.edit_text("✅ Rahmat! Endi kod yuboring.")
    else:
        await call.answer("❌ Hali obuna bo‘lmadingiz", show_alert=True)

# 📌 KINO QIDIRISH
@dp.message_handler(content_types=types.ContentType.TEXT)
async def kino_handler(message: Message):
    if message.text.startswith('/'):
        return

    if not await check_sub(message.from_user.id):
        await message.answer("❗ Avval kanalga obuna bo‘ling /start")
        return

    kod = message.text.lower()

    if kod in kino_db:
        msg_id = kino_db[kod]

        try:
            await bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=CHANNEL_ID,
                message_id=msg_id
            )
        except:
            await message.answer("❌ Kino topilmadi yoki xatolik.")
    else:
        await message.answer("❌ Bunday kod yo‘q.")

# 📌 ADMIN: QO‘SHISH
@dp.message_handler(commands=['add'])
async def add_kino(message: Message):
    try:
        _, kod, msg_id = message.text.split()
        kino_db[kod.lower()] = int(msg_id)

        await message.answer(f"✅ Qo‘shildi:\n{kod} → {msg_id}")
    except:
        await message.answer("❌ Format: /add k1 45")

# 📌 CHANNEL POST ID (console’da chiqadi)
@dp.channel_post_handler(content_types=types.ContentType.ANY)
async def save_post(message: types.Message):

    # 📌 kodni text yoki caption dan olamiz
    kod = None

    if message.caption:
        kod = message.caption.strip().lower()
    elif message.text:
        kod = message.text.strip().lower()

    if not kod:
        print("❌ Kod topilmadi (caption ham text ham yo‘q)")
        return

    msg_id = message.message_id
    kino_db[kod] = msg_id

    print(f"✅ SAVED: {kod} → {msg_id}")


# 📌 FORWARD QILINGAN POST ID
@dp.message_handler(content_types=types.ContentType.ANY)
async def get_forward_id(message: Message):
    if message.forward_from_chat:
        print("📌 FORWARD MESSAGE ID:", message.forward_from_message_id)

# 📌 🔥 WEBHOOKNI O‘CHIRISH (MUHIM FIX)
async def on_startup(dp):
    await bot.delete_webhook(drop_pending_updates=True)
    print("✅ Webhook o‘chirildi, bot ishga tushdi")

@dp.message_handler(commands=['test'])
async def test(message: Message):
    print("TEST OK")
    await message.answer("ok")


# 📌 RUN
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    executor.start_polling(
        dp,
        skip_updates=True,
        on_startup=on_startup
    )
