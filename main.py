import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

TOKEN = "8785641875:AAExm-gmleckq0va16fFZEt6Yq9lGVRpLxI"

router = Router()

# Ma'lumotlar bazasini yaratish
def init_db():
    conn = sqlite3.connect("saroy.db")
    cursor = conn.cursor()
    
    # Foydalanuvchilar jadvali
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            full_name TEXT,
            role TEXT,
            chef_type TEXT
        )
    """)
    
    # Buyurtmalar jadvali
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chef_id INTEGER,
            product_text TEXT,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Xabarlar holati (kim xabar oldi)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            chef_id INTEGER PRIMARY KEY,
            notified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()

init_db()

# Holatlar (FSM)
class OrderState(StatesGroup):
    waiting_for_product = State()

class BroadcastState(StatesGroup):
    waiting_for_message = State()

# Klaviaturalar
def get_admin_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📄 Bugungi ro'yxat"), KeyboardButton(text="⚠️ Kimlar buyurtma bermadi?")],
            [KeyboardButton(text="💬 Povarlarga xabar"), KeyboardButton(text="👥 Povarlar")],
            [KeyboardButton(text="🧹 Ro'yxatni tozalash")]
        ],
        resize_keyboard=True
    )

def get_chef_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Tovarlar kiritish / Buyurtma berish")],
            [KeyboardButton(text="📄 Mening bugungi ro'yxatim")]
        ],
        resize_keyboard=True
    )

# /start buyrug'i
@router.message(Command("start"))
async def cmd_start(message: Message):
    db = sqlite3.connect("saroy.db")
    cursor = db.cursor()
    
    cursor.execute("SELECT telegram_id FROM users WHERE role = 'director'")
    director = cursor.fetchone()
    
    cursor.execute("SELECT role FROM users WHERE telegram_id = ?", (message.from_user.id,))
    user = cursor.fetchone()

    if not user:
        if not director:
            cursor.execute("INSERT OR REPLACE INTO users (telegram_id, full_name, role) VALUES (?, ?, ?)",
                           (message.from_user.id, message.from_user.full_name, "director"))
            db.commit()
            db.close()
            await message.answer("Siz tizimdagi Boshliq (Direktor) sifatida ro'yxatdan o'tdingiz!", reply_markup=get_admin_keyboard())
            return

        cursor.execute("INSERT OR IGNORE INTO users (telegram_id, full_name, role) VALUES (?, ?, ?)",
                       (message.from_user.id, message.from_user.full_name, "pending"))
        db.commit()
        db.close()
        
        await message.answer("Assalomu alaykum! Saroy Restaurant botiga xush kelibsiz. Boshliq sizni tasdiqlashini kuting.")
    elif user[0] == "director":
        db.close()
        await message.answer("Xush kelibsiz, Boshliq!", reply_markup=get_admin_keyboard())
    elif user[0] == "chef":
        db.close()
        await message.answer("Xush kelibsiz, Oshpaz!", reply_markup=get_chef_keyboard())
    else:
        db.close()
        await message.answer("Sizning so'rovingiz hali tasdiqlanmagan.")

# Boshliq uchun povarlar ro'yxati va ularni tasdiqlash
@router.message(F.text == "👥 Povarlar")
async def show_pending_users(message: Message):
    db = sqlite3.connect("saroy.db")
    cursor = db.cursor()
    cursor.execute("SELECT telegram_id, full_name, role FROM users WHERE role = 'pending'")
    users = cursor.fetchall()
    db.close()

    if not users:
        await message.answer("Hozircha tasdiqlashni kutayotgan xodimlar yo'q.")
        return

    for u in users:
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="Oshpaz qilish", callback_data=f"make_chef_{u[0]}"))
        await message.answer(f"Foydalanuvchi: {u[1]} (ID: {u[0]})", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("make_chef_"))
async def make_chef(callback: CallbackQuery):
    chef_id = int(callback.data.split("_")[2])
    db = sqlite3.connect("saroy.db")
    cursor = db.cursor()
    cursor.execute("UPDATE users SET role = 'chef' WHERE telegram_id = ?", (chef_id,))
    db.commit()
    db.close()

    await callback.message.edit_text("Foydalanuvchi oshpaz etib tasdiqlandi!")
    await callback.bot.send_message(chef_id, "Tabriklaymiz! Boshliq sizni oshpaz sifatida tasdiqladi. Endi menyudan foydalanishingiz mumkin.", reply_markup=get_chef_keyboard())

# Boshliq xabar yuborishi
@router.message(F.text == "💬 Povarlarga xabar")
async def start_broadcast(message: Message, state: FSMContext):
    await message.answer("Oshpazlarga yubormoqchi bo'lgan xabaringizni yozing:")
    await state.set_state(BroadcastState.waiting_for_message)

@router.message(BroadcastState.waiting_for_message)
async def send_broadcast(message: Message, state: FSMContext):
    text = message.text
    db = sqlite3.connect("saroy.db")
    cursor = db.cursor()
    
    cursor.execute("SELECT telegram_id FROM users WHERE role = 'chef'")
    chefs = cursor.fetchall()
    
    cursor.execute("DELETE FROM notifications")
    for chef in chefs:
        cursor.execute("INSERT INTO notifications (chef_id) VALUES (?)", (chef[0],))
    db.commit()
    db.close()

    for chef in chefs:
        try:
            await message.bot.send_message(chef[0], f"📢 **Boshliqdan xabar:**\n\n{text}")
        except:
            pass

    await message.answer("Xabar barcha oshpazlarga yuborildi!", reply_markup=get_admin_keyboard())
    await state.clear()

# Oshpaz buyurtma berishi
@router.message(F.text == "📝 Tovarlar kiritish / Buyurtma berish")
async def start_order(message: Message, state: FSMContext):
    await message.answer("Kerakli mahsulotlar va miqdorini yozib yuboring (masalan: Go'sht - 5 kg, Yog' - 3 litr):")
    await state.set_state(OrderState.waiting_for_product)

@router.message(OrderState.waiting_for_product)
async def save_order(message: Message, state: FSMContext):
    product_text = message.text
    db = sqlite3.connect("saroy.db")
    cursor = db.cursor()
    
    cursor.execute("INSERT INTO orders (chef_id, product_text) VALUES (?, ?)", (message.from_user.id, product_text))
    cursor.execute("DELETE FROM notifications WHERE chef_id = ?", (message.from_user.id,))
    
    db.commit()
    db.close()

    await message.answer("Buyurtmangiz qabul qilindi va ro'yxatga qo'shildi!", reply_markup=get_chef_keyboard())
    await state.clear()

# Boshliq uchun "Bugungi ro'yxat"
@router.message(F.text == "📄 Bugungi ro'yxat")
async def show_today_orders(message: Message):
    db = sqlite3.connect("saroy.db")
    cursor = db.cursor()
    cursor.execute("SELECT product_text FROM orders")
    orders = cursor.fetchall()
    db.close()

    if not orders:
        await message.answer("Bugun hali hech qanday mahsulot kiritilmadi.")
        return

    result = "📄 **Bugungi kiritilgan tovarlar ro'yxati:**\n\n"
    for i, ord_item in enumerate(orders, 1):
        result += f"{i}. {ord_item[0]}\n"

    await message.answer(result)

# Kimlar buyurtma bermadi?
@router.message(F.text == "⚠️ Kimlar buyurtma bermadi?")
async def show_missing_orders(message: Message):
    db = sqlite3.connect("saroy.db")
    cursor = db.cursor()
    cursor.execute("""
        SELECT u.full_name FROM users u
        JOIN notifications n ON u.telegram_id = n.chef_id
    """)
    missing_chefs = cursor.fetchall()
    db.close()

    if not missing_chefs:
        await message.answer("Barcha oshpazlar buyurtma yuborishgan yoki xabar yuborilmagan.")
        return

    result = "⚠️ **Hali buyurtma bermagan oshpazlar:**\n\n"
    for c in missing_chefs:
        result += f"• {c[0]}\n"

    await message.answer(result)

# Ro'yxatni tozalash
@router.message(F.text == "🧹 Ro'yxatni tozalash")
async def clear_orders(message: Message):
    db = sqlite3.connect("saroy.db")
    cursor = db.cursor()
    cursor.execute("DELETE FROM orders")
    cursor.execute("DELETE FROM notifications")
    db.commit()
    db.close()

    await message.answer("Bugungi barcha buyurtmalar tozalandi!", reply_markup=get_admin_keyboard())

async def main():
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    
    await bot.delete_webhook(drop_pending_updates=True)
    print("Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
