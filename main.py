import asyncio
import logging
import sys
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

SUPER_ADMIN_ID = 8491225415

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- BAZANI YARATISH VA SOZLASH ---
def init_db():
    conn = sqlite3.connect("restaurant.db")
    cursor = conn.cursor()
    # Adminlar
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
        )
    """)
    cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (SUPER_ADMIN_ID,))
    
    # Oshpazlar
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chefs (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT,
            chef_type TEXT DEFAULT 'Umumiy'
        )
    """)
    
    # Buyurtmalar
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            item_text TEXT,
            date TEXT DEFAULT CURRENT_DATE
        )
    """)
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

# --- FSM HOLATLARI ---
class AdminState(StatesGroup):
    waiting_for_new_admin_id = State()
    waiting_broadcast_text = State()
    waiting_chef_type_name = State()

class ChefState(StatesGroup):
    waiting_for_order_text = State()
    waiting_for_admin_msg = State()

# --- MENYULAR ---
def get_director_menu():
    keyboard = [
        [KeyboardButton(text="📄 Bugungi ro'yxat"), KeyboardButton(text="⚠️ Kimlar buyurtma bermadi?")],
        [KeyboardButton(text="💬 Povarlarga xabar"), KeyboardButton(text="📦 Tarix")],
        [KeyboardButton(text="✅ Sotib olindi"), KeyboardButton(text="🧹 Ro'yxatni tozalash")],
        [KeyboardButton(text="👥 Povarlar"), KeyboardButton(text="🏷 Povar turlari")],
        [KeyboardButton(text="➕ Yangi boshliq tayinlash")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_chef_menu():
    keyboard = [
        [KeyboardButton(text="📝 Tovarlar kiritish / Buyurtma berish")],
        [KeyboardButton(text="📄 Mening bugungi ro'yxatim"), KeyboardButton(text="📦 Mening tarixim")],
        [KeyboardButton(text="💬 Boshliqqa xabar")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# --- START BUYRUĞI ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        conn = sqlite3.connect("restaurant.db")
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO chefs (user_id, full_name, chef_type) VALUES (?, ?, ?)", 
                       (user_id, message.from_user.full_name, "Umumiy"))
        conn.commit()
        conn.close()

    if is_admin(user_id):
        await message.answer("Assalomu alaykum, Direktor janoblari! Saroy Restaurant boshqaruv paneli:", reply_markup=get_director_menu())
    else:
        await message.answer("Assalomu alaykum! Saroy Restaurant oshpazlar paneliga xush kelibsiz. Marhamat, buyurtma bering.", reply_markup=get_chef_menu())

# ================= DIREKTOR FUNKSIYALARI =================

@dp.message(F.text == "📄 Bugungi ro'yxat")
async def dir_today_list(message: types.Message):
    if not is_admin(message.from_user.id): return
    
    conn = sqlite3.connect("restaurant.db")
    cursor = conn.cursor()
    cursor.execute("SELECT item_text FROM orders WHERE date = date('now')")
    orders = cursor.fetchall()
    conn.close()

    if not orders:
        await message.answer("📄 Bugun hali hech qanday tovar kiritilmagan.")
    else:
        text = "📄 **Bugungi umumiy mahsulotlar ro'yxati:**\n\n"
        for idx, item in enumerate(orders, 1):
            text += f"{idx}. {item[0]}\n"
        await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "⚠️ Kimlar buyurtma bermadi?")
async def dir_who_didnt_order(message: types.Message):
    if not is_admin(message.from_user.id): return
    
    conn = sqlite3.connect("restaurant.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT full_name FROM chefs 
        WHERE user_id NOT IN (SELECT DISTINCT user_id FROM orders WHERE date = date('now'))
    """)
    lazy_chefs = cursor.fetchall()
    conn.close()

    if not lazy_chefs:
        await message.answer("👍 Hamma oshpazlar bugungi buyurtmalarini kiritib bo'lishgan!")
    else:
        text = "⚠️ **Hali mahsulot kiritmagan oshpazlar:**\n\n"
        for chef in lazy_chefs:
            text += f"- {chef[0]}\n"
        await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "💬 Povarlarga xabar")
async def dir_msg_to_chefs(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await message.answer("💬 Barcha oshpazlarga yubormoqchi bo'lgan xabaringizni kiriting:")
    await state.set_state(AdminState.waiting_broadcast_text)

@dp.message(AdminState.waiting_broadcast_text)
async def send_broadcast(message: types.Message, state: FSMContext):
    text_to_send = message.text
    conn = sqlite3.connect("restaurant.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM chefs")
    chefs = cursor.fetchall()
    conn.close()

    count = 0
    for chef in chefs:
        try:
            await bot.send_message(chef[0], f"📢 **Boshliqlardan xabar:**\n\n{text_to_send}", parse_mode="Markdown")
            count += 1
        except Exception:
            pass

    await state.clear()
    await message.answer(f"✅ Xabar {count} ta oshpazga muvaffaqiyatli yuborildi!")

@dp.message(F.text == "📦 Tarix")
async def dir_history(message: types.Message):
    if not is_admin(message.from_user.id): return
    
    conn = sqlite3.connect("restaurant.db")
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT date FROM orders ORDER BY date DESC LIMIT 7")
    dates = cursor.fetchall()
    conn.close()

    if not dates:
        await message.answer("📦 Tarixda hali buyurtmalar mavjud emas.")
    else:
        text = "📦 **O'tgan kunlardagi buyurtma sanalari:**\n\n"
        for d in dates:
            text += f"📅 {d[0]}\n"
        await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "✅ Sotib olindi")
async def dir_purchased(message: types.Message):
    if not is_admin(message.from_user.id): return
    await message.answer("✅ Bugungi mahsulotlar xarid qilingani tasdiqlandi va arxivga belgilandi.")

@dp.message(F.text == "🧹 Ro'yxatni tozalash")
async def dir_clear_list(message: types.Message):
    if not is_admin(message.from_user.id): return
    
    conn = sqlite3.connect("restaurant.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM orders WHERE date = date('now')")
    conn.commit()
    conn.close()
    await message.answer("🧹 Bugungi barcha ro'yxat tozalandi.")

@dp.message(F.text == "👥 Povarlar")
async def dir_chefs(message: types.Message):
    if not is_admin(message.from_user.id): return
    
    conn = sqlite3.connect("restaurant.db")
    cursor = conn.cursor()
    cursor.execute("SELECT full_name, chef_type, user_id FROM chefs")
    chefs = cursor.fetchall()
    conn.close()

    if not chefs:
        await message.answer("Hozircha ro'yxatda oshpazlar yo'q.")
    else:
        text = "👥 **Ro'yxatdagi oshpazlar va turlari:**\n\n"
        for c in chefs:
            text += f"- {c[0]} | Yo'nalishi: *{c[1]}* (ID: `{c[2]}`)\n"
        await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "🏷 Povar turlari")
async def dir_chef_types(message: types.Message):
    if not is_admin(message.from_user.id): return
    await message.answer("🏷 Hozirgi mavjud povar yo'nalishlari: *Issiq ovqat, Salat, Tandir, Bar*.\nOshpazlarni turlarga ajratish tizimi faol.")

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


# ================= OSHPAZ FUNKSIYALARI =================

@dp.message(F.text == "📝 Tovarlar kiritish / Buyurtma berish")
async def chef_add_order(message: types.Message, state: FSMContext):
    if is_admin(message.from_user.id):
        await message.answer("Siz Directorsiz, bu bo'lim oshpazlar uchun.")
        return
    await message.answer("📝 Kerakli mahsulotlar va miqdorni yuboring (Masalan: *Go'sht - 5 kg, Yog' - 2 litr*):", parse_mode="Markdown")
    await state.set_state(ChefState.waiting_for_order_text)

@dp.message(ChefState.waiting_for_order_text)
async def save_chef_order(message: types.Message, state: FSMContext):
    order_text = message.text.strip()
    user_id = message.from_user.id

    conn = sqlite3.connect("restaurant.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO orders (user_id, item_text) VALUES (?, ?)", (user_id, order_text))
    conn.commit()
    conn.close()

    await state.clear()
    await message.answer("✅ Buyurtmangiz qabul qilindi va direktorga yuborildi!")

@dp.message(F.text == "📄 Mening bugungi ro'yxatim")
async def chef_my_today(message: types.Message):
    user_id = message.from_user.id
    conn = sqlite3.connect("restaurant.db")
    cursor = conn.cursor()
    cursor.execute("SELECT item_text FROM orders WHERE user_id = ? AND date = date('now')", (user_id,))
    orders = cursor.fetchall()
    conn.close()

    if not orders:
        await message.answer("📄 Bugun hali hech qanday tovar kiritmagansiz.")
    else:
        text = "📄 **Siz bugun kiritgan mahsulotlar:**\n\n"
        for idx, item in enumerate(orders, 1):
            text += f"{idx}. {item[0]}\n"
        await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "📦 Mening tarixim")
async def chef_my_history(message: types.Message):
    user_id = message.from_user.id
    conn = sqlite3.connect("restaurant.db")
    cursor = conn.cursor()
    cursor.execute("SELECT date, item_text FROM orders WHERE user_id = ? ORDER BY date DESC LIMIT 10", (user_id,))
    orders = cursor.fetchall()
    conn.close()

    if not orders:
        await message.answer("📦 Tarixingizda buyurtmalar yo'q.")
    else:
        text = "📦 **Sizning oxirgi buyurtmalaringiz:**\n\n"
        for o in orders:
            text += f"📅 {o[0]} — {o[1]}\n"
        await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "💬 Boshliqqa xabar")
async def chef_msg_to_admin_start(message: types.Message, state: FSMContext):
    await message.answer("💬 Rahbariyatga yubormoqchi bo'lgan xabaringizni yozing:")
    await state.set_state(ChefState.waiting_for_admin_msg)

@dp.message(ChefState.waiting_for_admin_msg)
async def chef_send_msg_to_admin(message: types.Message, state: FSMContext):
    text_msg = message.text
    chef_name = message.from_user.full_name
    await state.clear()

    # Xabarni super adminga yoki boshliqlarga yuboramiz
    try:
        await bot.send_message(SUPER_ADMIN_ID, f"💬 **Oshpazdan xabar ({chef_name}):**\n\n{text_msg}", parse_mode="Markdown")
        await message.answer("✅ Xabaringiz boshliqqa muvaffaqiyatli yuborildi!")
    except Exception:
        await message.answer("❌ Xabar yuborishda xatolik yuz berdi.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
