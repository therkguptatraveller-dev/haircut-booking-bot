import os
import logging
import sqlite3
import re
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# .env se load
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))
DB_PATH = os.getenv("DB_PATH", "haircut_bot.db")

# Conversation states
SHOP_NAME, MOBILE, CITY, PINCODE, CHAIRS, START_TIME, END_TIME = range(7)

# Database connection
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Tables create
def create_tables():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_name TEXT NOT NULL,
            city TEXT NOT NULL,
            pincode TEXT NOT NULL,
            total_chairs INTEGER NOT NULL,
            work_start TEXT NOT NULL,
            work_end TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            mobile TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now'))
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            booking_date TEXT NOT NULL,
            slot_time TEXT NOT NULL,
            chair_number INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (shop_id) REFERENCES shops(id)
        )
    ''')

    conn.commit()
    conn.close()
    logger.info("Database tables ready!")

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_id = user.id

    text = (
        f"नमस्ते {user.first_name} जी! 👋\n"
        "💈 Haircut Time Booking Bot में आपका स्वागत है!\n"
        "\"अब घंटों की लाइन खत्म। आपकी बारी, आपके समय पर।\""
    )

    keyboard = [
        [InlineKeyboardButton("📅 हेयरकट बुक करें / Book Haircutting Time", callback_data="book_appointment")],
        [InlineKeyboardButton("📖 मेरे अपॉइंटमेंट / My Appointments", callback_data="my_bookings")],
        [InlineKeyboardButton("🏪 दुकान रजिस्टर करें / Register My Shop", callback_data="register_shop")],
    ]

    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("🔧 Admin Panel", callback_data="admin_panel")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup)

# Button callback
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "register_shop":
        await query.message.reply_text(
            "🏪 दुकान रजिस्ट्रेशन शुरू!\n"
            "पहला स्टेप: दुकान का नाम बताएं (जैसे: Galaxy Unisex Saloon)",
            reply_markup=ReplyKeyboardRemove()
        )
        return SHOP_NAME
    elif data == "book_appointment":
        await query.message.reply_text("Booking शुरू करते हैं... (अभी विकास में है)")
    elif data == "my_bookings":
        await query.message.reply_text("आपके अपॉइंटमेंट: अभी कोई नहीं दिख रहा")
    elif data == "admin_panel" and query.from_user.id == ADMIN_ID:
        await query.message.reply_text("Admin panel खुल गया! 🔧")
    else:
        await query.message.reply_text(f"Button clicked: {data}")

# Shop registration steps
async def shop_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['shop_name'] = update.message.text.strip()
    await update.message.reply_text("📱 Shop Owner का Mobile Number बताएं:", reply_markup=ReplyKeyboardRemove())
    return MOBILE

async def mobile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['mobile'] = update.message.text.strip()
    await update.message.reply_text("🏙️ City का नाम बताएं (जैसे: Shankargarh):", reply_markup=ReplyKeyboardRemove())
    return CITY

async def city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['city'] = update.message.text.strip()
    await update.message.reply_text("📍 PIN Code (6 अंक) बताएं:", reply_markup=ReplyKeyboardRemove())
    return PINCODE

async def pincode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pin = update.message.text.strip()
    if len(pin) == 6 and pin.isdigit():
        context.user_data['pincode'] = pin
        await update.message.reply_text("🪑 कुल कुर्सियों की संख्या बताएं (जैसे: 3):", reply_markup=ReplyKeyboardRemove())
        return CHAIRS
    else:
        await update.message.reply_text("गलत PIN! 6 अंकों का नंबर डालें:", reply_markup=ReplyKeyboardRemove())
        return PINCODE

async def chairs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chairs_str = update.message.text.strip()
    if chairs_str.isdigit() and int(chairs_str) > 0:
        context.user_data['total_chairs'] = int(chairs_str)
        await update.message.reply_text("⏰ खुलने का समय (जैसे: 08:00 AM):", reply_markup=ReplyKeyboardRemove())
        return START_TIME
    else:
        await update.message.reply_text("कुर्सियां संख्या गलत! नंबर डालें:", reply_markup=ReplyKeyboardRemove())
        return CHAIRS

async def start_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    time_str = update.message.text.strip()
    if re.match(r'^(0?[1-9]|1[0-2]):[0-5][0-9] ?[AP]M$', time_str.upper()):
        context.user_data['work_start'] = time_str.upper()
        await update.message.reply_text("⏰ बंद होने का समय (जैसे: 08:30 PM):", reply_markup=ReplyKeyboardRemove())
        return END_TIME
    else:
        await update.message.reply_text("समय गलत! 12-hour format में लिखें (जैसे: 08:00 AM):", reply_markup=ReplyKeyboardRemove())
        return START_TIME

async def end_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    time_str = update.message.text.strip()
    if re.match(r'^(0?[1-9]|1[0-2]):[0-5][0-9] ?[AP]M$', time_str.upper()):
        context.user_data['work_end'] = time_str.upper()

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO shops (shop_name, city, pincode, total_chairs, work_start, work_end, owner_id, mobile, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            ''', (
                context.user_data['shop_name'],
                context.user_data['city'],
                context.user_data['pincode'],
                context.user_data['total_chairs'],
                context.user_data['work_start'],
                context.user_data['work_end'],
                update.effective_user.id,
                context.user_data['mobile']
            ))
            shop_id = cursor.lastrowid
            conn.commit()
            conn.close()

            # Admin notification
            admin_text = (
                f"🆕 Nayi shop registration pending!\n\n"
                f"Shop ID: {shop_id}\n"
                f"नाम: {context.user_data['shop_name']}\n"
                f"Owner ID: {update.effective_user.id}\n"
                f"City: {context.user_data['city']}\n"
                f"PIN: {context.user_data['pincode']}\n"
                f"कुर्सियां: {context.user_data['total_chairs']}\n"
                f"समय: {context.user_data['work_start']} से {context.user_data['work_end']}\n"
                f"Mobile: {context.user_data['mobile']}\n\n"
                "Approve ya Reject karo:"
            )

            keyboard = [
                [InlineKeyboardButton("✔ Approve", callback_data=f"approve_shop_{shop_id}")],
                [InlineKeyboardButton("❌ Reject", callback_data=f"reject_shop_{shop_id}")]
            ]

            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_text,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

            await update.message.reply_text(
                f"🎉 दुकान रजिस्टर हो गई!\n"
                f"Admin approval ke liye pending hai.\n"
                f"Details: {context.user_data['shop_name']} ({context.user_data['city']})\n"
                f"Admin ko notification bhej diya gaya hai."
            )
        except Exception as e:
            logger.error(f"Registration error: {e}")
            await update.message.reply_text("Kuch galat ho gaya! Fir se try karo ya /cancel karo.")

        context.user_data.clear()
        return ConversationHandler.END
    else:
        await update.message.reply_text("समय गलत! 12-hour format में लिखें (जैसे: 08:30 PM):", reply_markup=ReplyKeyboardRemove())
        return END_TIME

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("रजिस्ट्रेशन रद्द कर दिया गया।")
    context.user_data.clear()
    return ConversationHandler.END

# My shops
async def my_shops(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, shop_name, city, status FROM shops WHERE owner_id = ?", (user_id,))
    shops = cursor.fetchall()
    conn.close()

    if not shops:
        await update.message.reply_text("Abhi aapki koi shop registered nahi hai.")
        return

    text = "Aapki shops:\n"
    for shop in shops:
        text += f"- {shop['shop_name']} ({shop['city']}) - Status: {shop['status']}\n"
    await update.message.reply_text(text)

# Admin approve/reject
async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("approve_shop_"):
        shop_id = int(data.split("_")[2])
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE shops SET status = 'approved' WHERE id = ?", (shop_id,))
        conn.commit()
        conn.close()
        await query.message.edit_text(f"Shop ID {shop_id} approved! ✅")
    elif data.startswith("reject_shop_"):
        shop_id = int(data.split("_")[2])
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE shops SET status = 'rejected' WHERE id = ?", (shop_id,))
        conn.commit()
        conn.close()
        await query.message.edit_text(f"Shop ID {shop_id} rejected! ❌")

def main():
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN nahi mila!")
        return

    create_tables()

    print("Bot starting...")

    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(button_callback, pattern="^register_shop$"),
            CommandHandler("registershop", button_callback)
        ],
        states={
            SHOP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, shop_name)],
            MOBILE: [MessageHandler(filters.TEXT & ~filters.COMMAND, mobile)],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, city)],
            PINCODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, pincode)],
            CHAIRS: [MessageHandler(filters.TEXT & ~filters.COMMAND, chairs)],
            START_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, start_time)],
            END_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, end_time)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("myshops", my_shops))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(CallbackQueryHandler(admin_action, pattern="^(approve_shop|reject_shop)_"))

    application.run_polling()

if __name__ == '__main__':
    main()