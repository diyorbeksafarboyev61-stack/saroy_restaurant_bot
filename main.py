import asyncio
import logging
import sys
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

SUPER_ADMIN_ID = 8491225415

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def init_db():
    conn = sqlite3.connect("restaurant.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
        )
    """)
    cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (SUPER_ADMIN_ID,))
    conn.commit()
    conn.close()

init_db()

def is_admin(user_id: int) -> bool:
    if user_id == SUPER_ADMIN_ID:
        return True
    conn = sqlite3.connect("restaurant.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

class AdminState(StatesGroup):
    waiting_for_new_admin_id = State()

# 1. Boshliq (Direktor) uchun asosiy menyu
def get_director_menu():
    keyboard = [
        [KeyboardButton(text="📄 Bugungi ro'yxat"), KeyboardButton(text="⚠️️ Kimlar buyurtma bermadi?")],
        [KeyboardButton(text="💬 Povarlarga xabar"), KeyboardButton(text="📦 Tarix")],
        [KeyboardButton(text="✅ Sotib olindi"), KeyboardButton(text="🧹 Ro'yxatni tozalash")],
        [KeyboardButton(text="👥 Povarlar"), KeyboardButton(text="🏷 Povar turlari")],
        [KeyboardButton(text="➕ Yangi boshliq tayinlash")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# 2. Oshpaz uchun asosiy menyu
def get_chef_menu():
    keyboard = [
        [KeyboardButton(text="📝 Tovarlar kiritish / Buyurtma berish")],
        [KeyboardButton(text="📄 Mening bugungi ro'yxatim"), KeyboardButton(text="📦 Mening tarixim")],
        [KeyboardButton(text="💬 Boshliqqa xabar")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    if is_admin(user_id):
        await message.answer("Assalomu alaykum, Direktor janoblari! Saroy Restaurant boshqaruv paneli:", reply_markup=get_director_menu())
    else:
        await message.answer("Assalomu alaykum! Saroy Restaurant oshpazlar paneliga xush kelibsiz.", reply_markup=get_chef_menu())

# --- Direktor funksiyalari ---
@dp.message(F.text == "📄 Bugungi ro'yxat")
async def dir_today_list(message: types.Message):
    if is_admin(message.from_user.id):
        await message.answer("📄 Bugungi umumiy mahsulotlar ro'yxati (Hozircha bo'sh):")

@dp.message(F.text == "⚠️ Kimlar buyurtma bermadi?")
async def dir_who_didnt_order(message: types.Message):
    if is_admin(message.from_user.id):
        await message.answer("⚠️ Hali mahsulot kiritmagan oshpazlar ro'yxati:")

@dp.message(F.text == "💬 Povarlarga xabar")
async def dir_msg_to_chefs(message: types.Message):
    if is_admin(message.from_user.id):
        await message.answer("💬 Povarlarga yuboriladigan xabarni kiriting:")

@dp.message(F.text == "📦 Tarix")
async def dir_history(message: types.Message):
    if is_admin(message.from_user.id):
        await message.answer("📦 O'tgan kunlardagi buyurtmalar arxivi:")

@dp.message(F.text == "✅ Sotib olindi")
async def dir_purchased(message: types.Message):
    if is_admin(message.from_user.id):
        await message.answer("✅ Bugungi mahsulotlar xarid qilingani tasdiqlandi.")

@dp.message(F.text == "🧹 Ro'yxatni tozalash")
async def dir_clear_list(message: types.Message):
    if is_admin(message.from_user.id):
        await message.answer("🧹 Kun yakunidagi eski ro'yxatlar tozalandi.")

@dp.message(F.text == "👥 Povarlar")
async def dir_chefs(message: types.Message):
    if is_admin(message.from_user.id):
        await message.answer("👥 Xodimlar (povarlar) ro'yxati va boshqaruvi:")

@dp.message(F.text == "🏷 Povar turlari")
async def dir_chef_types(message: types.Message):
    if is_admin(message.from_user.id):
        await message.answer("🏷 Povar yo'nalishlari va turlari:")

@dp.message(F.text == "➕ Yangi boshliq tayinlash")
async def add_admin_start(message: types.Message, state: FSMContext):
    if message.from_user.id == SUPER_ADMIN_ID:
        await message.answer("Yangi boshliq qilmoqchi bo'lgan odamning **Telegram ID raqamini** yuboring:\n*(Masalan: 123456789)*")
        await state.set_state(AdminState.waiting_for_new_admin_id)
    else:
        await message.answer("Kechirasiz, faqat bosh direktor yangi boshliq tayinlay oladi.")

@dp.message(AdminState.waiting_for_new_admin_id)
async def save_new_admin(message: types.Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("Iltimos, faqat raqamlardan iborat to'g'ri Telegram ID kiriting:")
        return
    
    new_admin_id = int(text)
    conn = sqlite3.connect("restaurant.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (new_admin_id,))
    conn.commit()
    conn.close()

    await state.clear()
    await message.answer(f"Muvaffaqiyatli! ID si `{new_admin_id}` bo'lgan foydalanuvchi endi **Boshliq** etib tayinlandi.", parse_mode="Markdown")

# --- Oshpaz funksiyalari ---
@dp.message(F.text == "📝 Tovarlar kiritish / Buyurtma berish")
async def chef_add_order(message: types.Message):
    await message.answer("📝 Kerakli mahsulot va miqdorni yuboring:")

@dp.message(F.text == "📄 Mening bugungi ro'yxatim")
async def chef_my_today(message: types.Message):
    await message.answer("📄 O'zingiz bugun kiritgan mahsulotlar ro'yxati:")

@dp.message(F.text == "📦 Mening tarixim")
async def chef_my_history(message: types.Message):
    await message.answer("📦 O'tgan kunlardagi buyurtmalaringiz:")

@dp.message(F.text == "💬 Boshliqqa xabar")
async def chef_msg_to_admin(message: types.Message):
    await message.answer("💬 Rahbariyatga yubormoqchi bo'lgan xabaringizni yozing:")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
