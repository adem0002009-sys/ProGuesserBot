import os
import json
import logging
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# --- إعداد التسجيل (Logging) ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- جلب المتغيرات البيئية من Render ---
TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_ID_STR = os.getenv("ADMIN_ID", "8629120109")

try:
    ADMIN_ID = int(ADMIN_ID_STR)
except ValueError:
    ADMIN_ID = 8629120109

USERS_FILE = "users_data.json"
KEYS_FILE = "keys_data.json"

# --- دوال تخزين وقراءة البيانات (JSON) ---
def load_json(filename):
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_json(filename, data):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        logger.error(f"خطأ في حفظ الملف {filename}: {e}")

# --- إعداد سيرفر Flask لضمان عمل البوت 24/7 ---
app = Flask('')

@app.route('/')
def home():
    return "SAIF BOT is running 24/7 successfully!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# --- أوامر البوت ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    
    welcome_text = (
        f"مرحباً بك يا {first_name} في بوت الإدارة الخاص بـ SAIF BOT 🚀\n\n"
        "الأوامر المتاحة:\n"
        "• `/addid [Player_ID]` - لحفظ وإرسال الآيدي الخاص بك.\n"
    )
    
    if user_id == ADMIN_ID:
        welcome_text += "\nأوامر الأدمن الخاصة بك:\n• `/gen [ساعات]` - لتوليد مفتاح اشتراك جديد."
        
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

# أمر حفظ الآيدي (مع إضافة strip لتفادي الفراغات المخفية)
async def add_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    args = context.args
    
    if not args:
        await update.message.reply_text("❌ خطأ! يرجى كتابة الآيدي بعد الأمر. مثال:\n`/addid 123456789`", parse_mode="Markdown")
        return
        
    player_id = args[0].strip()
    users_data = load_json(USERS_FILE)
    
    users_data[user_id] = {
        "player_id": player_id,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_json(USERS_FILE, users_data)
    
    await update.message.reply_text(f"✅ تم حفظ الآيدي بنجاح:\n`{player_id}`", parse_mode="Markdown")

# أمر توليد المفاتيح (للأدمن فقط)
async def gen_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ هذا الأمر مخصص للأدمن فقط!")
        return
        
    args = context.args
    hours = 24  # القيمة الافتراضية يوم كامل
    if args and args[0].isdigit():
        hours = int(args[0])
        
    # توليد مفتاح عشوائي بسيط
    import random, string
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    key_name = f"KEY-{hours}H-{random_str}"
    
    expiry_time = (datetime.now() + timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    
    keys_data = load_json(KEYS_FILE)
    keys_data[key_name] = {
        "hours": hours,
        "expiry": expiry_time,
        "used": False
    }
    save_json(KEYS_FILE, keys_data)
    
    await update.message.reply_text(
        f"🔑 **تم توليد المفتاح بنجاح!**\n\n"
        f"المفتاح: `{key_name}`\n"
        f"الصلاحية: `{hours} ساعة`\n"
        f"ينتهي في: `{expiry_time}`",
        parse_mode="Markdown"
    )

# --- التشغيل الأساسي ---
def main():
    if not TOKEN:
        logger.error("لم يتم العثور على التوكن (TELEGRAM_TOKEN)!")
        return

    # تشغيل سيرفر الأب تايم في الخلفية
    keep_alive()

    # بناء بوت تيليجرام
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("addid", add_id))
    application.add_handler(CommandHandler("gen", gen_key))

    logger.info("Bot is starting polling...")
    application.run_polling()

if __name__ == '__main__':
    main()
