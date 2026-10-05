import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)

# Loggingni sozlash
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- SOZLAMALAR ---
# Bu yerga o'zingizning Telegram bot tokeningizni kiriting
TOKEN = "SIZNING_BOT_TOKENINGIZ"

# Bu yerga boshliqning (direktorning) Telegram dagi ID raqamini yozing
DIRECTOR_CHAT_ID = 123456789  # O'z ID raqamingizga o'zgartiring

# Suhbat holatlari
WAITING_FOR_CHEF_MESSAGE = 1
WAITING_FOR_DIRECTOR_REPLY = 2


# --- START BUYrug'I ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # Oshpazlar uchun menyu tugmasi
    keyboard = [[InlineKeyboardButton("💬 Boshliqqa xabar yozish", callback_data="write_to_director")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Agar foydalanuvchi boshliq bo'lsa
    if user.id == DIRECTOR_CHAT_ID:
        await update.message.reply_text(
            f"Assalomu alaykum, Rahbar janoblari! Bot ishga tushdi.\n"
            f"Oshpazlardan keladigan xabarlar shu yerga keladi va siz ularga to'g'ridan-to'g'ri javob yozishingiz mumkin."
        )
    else:
        await update.message.reply_text(
            f"Assalomu alaykum, {user.first_name}!\n"
            f"Saroy restaurant xodimlar botiga xush kelibsiz. Boshliqqa xabar yuborish uchun pastdagi tugmani bosing:",
            reply_markup=reply_markup,
        )


# --- OSHPAZ TOMONIDAN XABAR YOZISHNI BOSHLASH ---
async def start_writing_to_director(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "Marhamat, boshliqqa yubormoqchi bo'lgan xabaringizni yozing (taklif, muammo yoki hisobot):"
    )
    return WAITING_FOR_CHEF_MESSAGE


# --- OSHPAZNING XABARINI QABUL QILIB, BOSHFAQQA YUBORISH ---
async def receive_chef_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chef_text = update.message.text

    # Oshpazning ID sini va ma'lumotlarini saqlab qo'shamiz (keyin javob qaytarish uchun)
    context.user_data["last_chef_id"] = user.id

    # Boshliqqa yuboriladigan xabar va javob berish tugmasi
    keyboard = [
        [InlineKeyboardButton("✍️ Javob yozish", callback_data=f"reply_to_chef_{user.id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message_to_director = (
        f"📩 **Yangi xabar (Oshpazdan)!**\n\n"
        f"👤 **Kimdan:** {user.full_name} (@{user.username or 'yo‘q'})\n"
        f"🆔 **ID:** `{user.id}`\n\n"
        f"💬 **Xabar matni:**\n{chef_text}"
    )

    # Boshliqqa xabarni yuboramiz
    await context.bot.send_message(
        chat_id=DIRECTOR_CHAT_ID,
        text=message_to_director,
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )

    await update.message.reply_text(
        "✅ Xabaringiz boshliqqa muvaffaqiyatli yuborildi! Javob kelishini kuting."
    )
    return ConversationHandler.END


# --- BOSHLIQ "JAVOB YOZISH" TUGMASINI BOSGANDA ---
async def director_click_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Callback datadan oshpazning ID raqamini ajratib olamiz (masalan: reply_to_chef_12345678)
    data_parts = query.data.split("_")
    chef_id = int(data_parts[-1])
    
    # Vaqtincha xotirada qaysi oshpazga javob yozilayotganini saqlaymiz
    context.user_data["reply_to_chef_id"] = chef_id

    await query.message.reply_text(
        f"✍️ Ushbu oshpazga yubormoqchi bo'lgan javobingizni hozir yozib yuboring:"
    )
    return WAITING_FOR_DIRECTOR_REPLY


# --- BOSHLIQNING JAVOBINI OSHPAZGA YETKAZISH ---
async def send_director_reply_to_chef(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chef_id = context.user_data.get("reply_to_chef_id")
    director_reply_text = update.message.text

    if not chef_id:
        await update.message.reply_text("❌ Xatolik: Qaysi oshpazga javob yozilishi aniqlanmadi.")
        return ConversationHandler.END

    try:
        # Javobni oshpazga jo'natamiz
        await context.bot.send_message(
            chat_id=chef_id,
            text=f"👨‍💼 **Boshliqdan javob:**\n\n{director_reply_text}",
            parse_mode="Markdown",
        )
        await update.message.reply_text("✅ Javobingiz oshpazga muvaffaqiyatli yuborildi!")
    except Exception as e:
        await update.message.reply_text(f"❌ Xabarni yuborishda xatolik yuz berdi: {e}")

    return ConversationHandler.END


# --- BEKOR QILISH ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Amaliyot bekor qilindi.")
    return ConversationHandler.END


def main():
    # Bot ilovasini yaratish
    app = ApplicationBuilder().token(TOKEN).build()

    # Oshpazning xabar yuborish jarayoni uchun ConversationHandler
    chef_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_writing_to_director, pattern="^write_to_director$")],
        states={
            WAITING_FOR_CHEF_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_chef_message)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Boshliqning javob yozish jarayoni uchun ConversationHandler
    director_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(director_click_reply, pattern="^reply_to_chef_")],
        states={
            WAITING_FOR_DIRECTOR_REPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_director_reply_to_chef)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Handlerlarni qo'shish
    app.add_handler(CommandHandler("start", start))
    app.add_handler(chef_conv_handler)
    app.add_handler(director_conv_handler)

    print("Bot ishga tushdi...")
    app.run_polling()


if __name__ == "__main__":
    main()
