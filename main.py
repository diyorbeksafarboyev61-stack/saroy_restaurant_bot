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

def get_main_menu(user_id: int):
    keyboard = []
    if is_admin(user_id):
        keyboard.append([KeyboardButton(text="📊 Hisobotlar"), KeyboardButton(text="📢 Xabar tarqatish")])
        keyboard.append([KeyboardButton(text="➕ Yangi boshliq tayinlash")])
    keyboard.append([KeyboardButton(text="📋 Buyurtma berish")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    if is_admin(user_id):
        await message.answer("Assalomu alaykum, Direktor janoblari! Saroy Restaurant boshqaruv paneliga xush kelibsiz.", reply_markup=get_main_menu(user_id))
    else:
        await message.answer("Assalomu alaykum! Saroy Restaurant botiga xush kelibsiz. Marhamat, buyurtma berishingiz mumkin.", reply_markup=get_main_menu(user_id))

@dp.message(F.text == "📊 Hisobotlar")
async def admin_reports(message: types.Message):
    if is_admin(message.from_user.id):
        await message.answer("📊 Bugungi umumiy hisobotlar va tushumlar:")

@dp.message(F.text == "📢 Xabar tarqatish")
async def admin_broadcast(message: types.Message):
    if is_admin(message.from_user.id):
        await message.answer("📢 Barcha foydalanuvchilarga yuboriladigan xabarni kiriting:")

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

@dp.message(F.text == "📋 Buyurtma berish")
async def make_order(message: types.Message):
    await message.answer("🍽 Menudan taomlarni tanlang.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
