import logging
import os

from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.utils import executor
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')
if not API_TOKEN:
    raise RuntimeError('API_TOKEN is not set. Create a .env file or set the environment variable.')

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# 📌 MAJBURIY OBUNA KANALI
CHANNEL_USERNAME = '@spritefx_tp'  # majburiy obuna uchun
CHANNEL_ID = -1003928462353  # private kanal ID

# 📌 Kino bazasi (ID -> message_id)
kino_db = {
    "k1": 10,
    "k2": 15,
    "k3": 20
}

# 📌 FOYDALANUVCHI OBUNA TEKSHIRISH
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
        btn.add(types.InlineKeyboardButton("📢 Obuna bo‘lish", url=f"https://t.me/{CHANNEL_USERNAME[1:]}"))
        btn.add(types.InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub"))
        
        await message.answer("❗ Botdan foydalanish uchun kanalga obuna bo‘ling:", reply_markup=btn)
        return
    
    await message.answer("🎬 Kino botga xush kelibsiz!\n\nKino kodini yuboring (masalan: k1)")

# 📌 CHECK BUTTON
@dp.callback_query_handler(lambda c: c.data == "check_sub")
async def check_button(call: types.CallbackQuery):
    if await check_sub(call.from_user.id):
        await call.message.edit_text("✅ Rahmat! Endi kino kod yuboring.")
    else:
        await call.answer("❌ Hali obuna bo‘lmadingiz", show_alert=True)

# 📌 KINO QIDIRISH
@dp.message_handler()
async def kino_handler(message: Message):
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
            await message.answer("❌ Kino topilmadi yoki xatolik yuz berdi.")
    else:
        await message.answer("❌ Bunday kodli kino yo‘q.")

# 📌 ADMIN: KINO QO‘SHISH
@dp.message_handler(commands=['add'])
async def add_kino(message: Message):
    # format: /add k10 25
    try:
        _, kod, msg_id = message.text.split()
        kino_db[kod] = int(msg_id)
        await message.answer(f"✅ Qo‘shildi: {kod}")
    except:
        await message.answer("❌ Format: /add k10 25")

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    executor.start_polling(dp, skip_updates=True)