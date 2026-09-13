import json
import os
import re
import base64
import aiohttp
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

TOKEN = "8674003152:AAFssXZsCNSHQkwY7mEfMh4rlkvpJaJEPE4"
DATA_FILE = "users_data.json"
KEYS_FILE = "keys_data.json"

DEFAULT_KEYS = {
    "12H-ABC1-9X7Y": 0.5, "12H-DEF2-4K8M": 0.5, "12H-GHI3-2P5Q": 0.5,
    "1D-ALFA-9012": 24, "1D-BETA-3456": 24, "1D-GAMA-7890": 24,
    "3D-FAST-1111": 24 * 3, "3D-QUICK-2222": 24 * 3,
    "7D-WK01-9988": 24 * 7, "7D-WK02-7766": 24 * 7, "ADEM-VIP-FREE": 24 * 7,
    "15D-HALF-0011": 24 * 15, "15D-HALF-0022": 24 * 15,
    "30D-MON1-8811": 24 * 30, "ADEM-VIP-2026": 24 * 30, "ISML-VIP-SSI799XQMVW9": 24 * 30,
    "90D-LONG-9991": 24 * 90
}

user_states = {}

def load_json(filename):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def get_user(user_id):
    data = load_json(DATA_FILE)
    uid = str(user_id)
    if uid not in data:
        data[uid] = {
            "is_vip": False,
            "vip_expire": None,
            "used_key": None,
            "accounts": [],          # قائمة الحسابات المضافة متعددة
            "active_account_idx": 0, # الحساب الحالي المحدد
            "spam_status": False,
            "guess_status": False
        }
        save_json(DATA_FILE, data)
    return data[uid]

def update_user(user_id, key, value):
    data = load_json(DATA_FILE)
    uid = str(user_id)
    if uid in data:
        data[uid][key] = value
        save_json(DATA_FILE, data)

def check_user_vip(user):
    if not user.get("is_vip"):
        return False
    expire_str = user.get("vip_expire")
    if not expire_str:
        return False
    try:
        expire_time = datetime.fromisoformat(expire_str)
        if datetime.now() > expire_time:
            return False
    except:
        return False
    return True

def parse_jwt_token(jwt_str):
    try:
        parts = jwt_str.split('.')
        if len(parts) < 2:
            return None
        payload_base64 = parts[1]
        payload_base64 += '=' * (-len(payload_base64) % 4)
        decoded_bytes = base64.urlsafe_b64decode(payload_base64)
        payload_data = json.loads(decoded_bytes.decode('utf-8'))
        return payload_data
    except Exception as e:
        print(f"JWT Parse Error: {e}")
        return None

# القائمة الرئيسية المطابقة للصورة الثانية
def get_main_menu_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("📁 قائمة حساباتي", callback_data="my_accounts"),
            InlineKeyboardButton("➕ إضافة حساب جديد", callback_data="add_account")
        ],
        [
            InlineKeyboardButton("⚙️ التحكم في الحساب", callback_data="account_control"),
            InlineKeyboardButton("🌍 تغيير اللغة", callback_data="change_lang")
        ],
        [
            InlineKeyboardButton("📞 تواصل مع المسؤول", callback_data="contact_admin"),
            InlineKeyboardButton("❓ المساعدة", callback_data="help_menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# قائمة التحكم بالحساب المطابقة للصورة الأولى
def get_account_menu_keyboard(user):
    spam_icon = "🟢 يعمل" if user.get("spam_status") else "🔴 متوقف"
    guess_icon = "🟢 يعمل" if user.get("guess_status") else "🔴 متوقف"
    
    keyboard = [
        [InlineKeyboardButton(f"⚡ حالة سبام الدخول: {spam_icon}", callback_data="none")],
        [InlineKeyboardButton(f"🧠 حالة التخمين الذكي: {guess_icon}", callback_data="none")],
        [
            InlineKeyboardButton("🔍 فحص الإيميل", callback_data="check_email"),
            InlineKeyboardButton("🟢 ربط إيميل استرداد", callback_data="link_email")
        ],
        [
            InlineKeyboardButton("🌐 المنصات المرتبطة", callback_data="platforms"),
            InlineKeyboardButton("❌ إلغاء المعلق", callback_data="cancel_operation")
        ],
        [
            InlineKeyboardButton("🔓 فك ربط الإيميل", callback_data="unlink_email"),
            InlineKeyboardButton("🔄 تغيير الإيميل", callback_data="change_email")
        ],
        [
            InlineKeyboardButton("✍ تعيين بايو طويل", callback_data="set_bio"),
            InlineKeyboardButton("🔴 إلغاء التوكن (Re...)", callback_data="revoke_token")
        ],
        [InlineKeyboardButton("🗑 حذف الحساب من البوت", callback_data="delete_account")],
        [InlineKeyboardButton("🚀 تشغيل التخمين الذكي", callback_data="toggle_guess")],
        [InlineKeyboardButton("🚀 تشغيل سبام Login", callback_data="toggle_spam")],
        [InlineKeyboardButton("🔙 رجوع لقائمة الحسابات", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid)
    
    if not check_user_vip(user):
        update_user(uid, "is_vip", False)
        user_states[uid] = "waiting_for_key"
        msg = (
            "🤖 SAIF BOT [Advanced Engine]\n\n"
            "⚠️ انتهى اشتراكك أو أنك لم تفعل البوت بعد!\n"
            "أرسل كود التفعيل الخاص بك (يفتح جهازاً واحداً فقط):\n\n"
            "لشراء كود جديد، تواصل مع المطور:\n@adem_ar28"
        )
        if update.message:
            await update.message.reply_text(msg)
        return

    txt = (
        "🤖 **SAIF BOT - القائمة الرئيسية**\n\n"
        "أهلاً بك عزيزي المستخدم. اختر إحدى الخيارات أدناه لإدارة حساباتك وتنفيذ العمليات:"
    )
    if update.message:
        await update.message.reply_text(txt, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
        
    uid = update.message.from_user.id
    txt = update.message.text.strip()
    user = get_user(uid)
    state = user_states.get(uid)
    
    if state == "waiting_for_key" or not check_user_vip(user):
        keys_db = load_json(KEYS_FILE)
        if txt in DEFAULT_KEYS:
            if txt in keys_db and keys_db[txt] != str(uid):
                await update.message.reply_text("❌ هذا المفتاح مستخدم بالفعل ومقفل على جهاز مستخدم آخر!")
                return
            
            hours = DEFAULT_KEYS[txt]
            expire_time = datetime.now() + timedelta(hours=hours)
            keys_db[txt] = str(uid)
            save_json(KEYS_FILE, keys_db)
            
            data_all = load_json(DATA_FILE)
            data_all[str(uid)]["is_vip"] = True
            data_all[str(uid)]["vip_expire"] = expire_time.isoformat()
            data_all[str(uid)]["used_key"] = txt
            save_json(DATA_FILE, data_all)
            
            if uid in user_states:
                del user_states[uid]
            await update.message.reply_text(f"✅ تم تفعيل المفتاح بنجاح! استمتع بجميع الميزات والخصائص المزة.\n\nأرسل /start للوصول للقائمة.")
        else:
            await update.message.reply_text("❌ المفتاح غير صالح أو منتهي الصلاحية! تواصل مع المطور شراء تفعيل.")
        return

    # حالة إضافة حساب جديد عبر إرسال التوكن
    if state == "waiting_for_token":
        jwt_match = re.search(r'jwt_token=([A-Za-z0-9_\-\.]+)', txt) or ('.' in txt and len(txt) > 50)
        if jwt_match:
            token_val = jwt_match.group(1) if hasattr(jwt_match, 'group') and jwt_match.groups() else txt
            parsed = parse_jwt_token(token_val)
            if parsed and "user" in parsed:
                acc_data = parsed["user"]
                accounts = user.get("accounts", [])
                
                new_acc = {
                    "token": token_val,
                    "info": acc_data,
                    "email": "None",
                    "bio": "None"
                }
                accounts.append(new_acc)
                update_user(uid, "accounts", accounts)
                update_user(uid, "active_account_idx", len(accounts) - 1)
                user_states[uid] = None
                
                await update.message.reply_text(
                    f"✅ **تم إضافة الحساب واستخراج البيانات بنجاح!**\n\n"
                    f"🏷 اللقب: `{acc_data.get('game_nickname')}`\n"
                    f"🆔 الايدي: `{acc_data.get('uid')}`\n"
                    f"🌍 المنطقة: `{acc_data.get('region')}`\n\n"
                    f"أرسل /start لعرض القائمة الرئيسية.",
                    parse_mode="Markdown"
                )
                return
            else:
                await update.message.reply_text("❌ التوكن المدخل غير صالح أو تالف! أرسل رابطاً صحيحاً.")
                return
        else:
            await update.message.reply_text("❌ يرجى إرسال رابط JWT Token صالح يحتوي على بيانات الحساب.")
            return

    if state == "waiting_for_email":
        accounts = user.get("accounts", [])
        idx = user.get("active_account_idx", 0)
        if accounts and len(accounts) > idx:
            accounts[idx]["email"] = txt
            update_user(uid, "accounts", accounts)
        user_states[uid] = None
        await update.message.reply_text(f"✅ تم ربط الإيميل بنجاح:\n{txt}\n\nأرسل /start للعودة للقائمة.")
        return

    if state == "waiting_for_bio":
        accounts = user.get("accounts", [])
        idx = user.get("active_account_idx", 0)
        if accounts and len(accounts) > idx:
            accounts[idx]["bio"] = txt
            update_user(uid, "accounts", accounts)
        user_states[uid] = None
        await update.message.reply_text(f"✅ تم تحديث البايو الطويل بنجاح:\n{txt}\n\nأرسل /start للعودة للقائمة.")
        return

    await update.message.reply_text("⚙️ استخدم الأزرار الظاهرة في القائمة عبر إرسال /start")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    user = get_user(uid)
    
    if not check_user_vip(user):
        await query.message.reply_text("❌ انتهت صلاحية اشتراكك! أرسل /start لإدخال كود جديد.")
        return

    data = query.data
    if data == "none":
        return

    # تفاعلات القائمة الرئيسية
    if data == "add_account":
        user_states[uid] = "waiting_for_token"
        await query.message.reply_text("➕ أرسل الآن رابط الـ JWT Token الخاص بالحساب الجديد ليتم إضافته:")

    elif data == "my_accounts":
        accounts = user.get("accounts", [])
        if not accounts:
            await query.message.reply_text("📂 لا توجد أي حسابات مضافة حالياً. اضغط على 'إضافة حساب جديد'.")
            return
        
        kb = []
        for idx, acc in enumerate(accounts):
            info = acc.get("info", {})
            name = info.get("game_nickname", f"حساب {idx+1}")
            kb.append([InlineKeyboardButton(f"👤 {name} (ID: {info.get('uid')})", callback_data=f"select_acc_{idx}")])
        kb.append([InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="back_to_main")])
        await query.message.edit_text("📁 **قائمة حساباتك المضافة:**\nاختر الحساب للتحكم به:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif data.startswith("select_acc_"):
        idx = int(data.split("_")[-1])
        update_user(uid, "active_account_idx", idx)
        accounts = user.get("accounts", [])
        acc = accounts[idx]["info"]
        txt = (
            f"👤 **معلومات الحساب المحدد:**\n"
            f"🏷 اللقب: `{acc.get('game_nickname', 'Unknown')}`\n"
            f"🆔 الايدي: `{acc.get('uid', 'None')}`\n"
            f"🌍 المنطقة: `{acc.get('region', 'None')}`\n"
        )
        await query.message.edit_text(txt, reply_markup=get_account_menu_keyboard(user), parse_mode="Markdown")

    elif data == "account_control":
        accounts = user.get("accounts", [])
        if not accounts:
            await query.message.reply_text("⚠️ يرجى إضافة حساب أولاً عبر زر 'إضافة حساب جديد'.")
            return
        idx = user.get("active_account_idx", 0)
        acc = accounts[idx]["info"]
        txt = (
            f"👤 **التحكم في الحساب النشط:**\n"
            f"🏷 اللقب: `{acc.get('game_nickname', 'Unknown')}`\n"
            f"🆔 الايدي: `{acc.get('uid', 'None')}`\n"
        )
        await query.message.edit_text(txt, reply_markup=get_account_menu_keyboard(user), parse_mode="Markdown")

    elif data == "change_lang":
        await query.message.reply_text("🌍 اللغة الحالية: العربية (Default)")

    elif data == "contact_admin":
        await query.message.reply_text("📞 للتواصل مع المطور المسؤول:\n@adem_ar28")

    elif data == "help_menu":
        await query.message.reply_text("❓ مساعدة البوت:\nقم بإضافة حسابك عبر الـ JWT Token، ثم اختر 'التحكم في الحساب' لتنفيذ العمليات.")

    # تفاعلات قائمة التحكم بالحساب
    elif data == "check_email":
        accounts = user.get("accounts", [])
        idx = user.get("active_account_idx", 0)
        email = accounts[idx].get("email", "None") if accounts else "None"
        await query.message.reply_text(f"📧 الإيميل المرتبط بالحساب النشط: {email}")

    elif data == "link_email":
        user_states[uid] = "waiting_for_email"
        await query.message.reply_text("أرسل بريد الاسترداد الجديد للحساب النشط الآن:")

    elif data == "unlink_email":
        accounts = user.get("accounts", [])
        idx = user.get("active_account_idx", 0)
        if accounts:
            accounts[idx]["email"] = "None"
            update_user(uid, "accounts", accounts)
        await query.message.reply_text("🔓 تم فك ربط الإيميل بنجاح.")

    elif data == "change_email":
        user_states[uid] = "waiting_for_email"
        await query.message.reply_text("أرسل البريد الجديد لتغييره:")

    elif data == "set_bio":
        user_states[uid] = "waiting_for_bio"
        await query.message.reply_text("أرسل البايو الطويل الجديد للحساب النشط الآن:")

    elif data == "revoke_token":
        accounts = user.get("accounts", [])
        idx = user.get("active_account_idx", 0)
        if accounts:
            accounts.pop(idx)
            update_user(uid, "accounts", accounts)
            update_user(uid, "active_account_idx", 0)
        await query.message.reply_text("🔴 تم إلغاء وإبطال التوكن الحالي وحذف الحساب من الجلسة.")

    elif data == "toggle_guess":
        st = not user.get("guess_status", False)
        update_user(uid, "guess_status", st)
        status_txt = "يعمل 🟢" if st else "متوقف 🔴"
        await query.message.reply_text(f"🧠 تم تغيير حالة التخمين الذكي إلى: {status_txt}")

    elif data == "toggle_spam":
        st = not user.get("spam_status", False)
        update_user(uid, "spam_status", st)
        status_txt = "يعمل 🟢" if st else "متوقف 🔴"
        await query.message.reply_text(f"⚡ تم تغيير حالة سبام Login إلى: {status_txt}")

    elif data == "cancel_operation":
        if uid in user_states:
            user_states[uid] = None
        await query.message.reply_text("❌ تم إلغاء العملية المعلقة بنجاح.")

    elif data == "delete_account":
        accounts = user.get("accounts", [])
        idx = user.get("active_account_idx", 0)
        if accounts:
            accounts.pop(idx)
            update_user(uid, "accounts", accounts)
            update_user(uid, "active_account_idx", 0)
        await query.message.reply_text("🗑 تم حذف الحساب المحدد من قائمة حساباتك نهائياً.")

    elif data == "platforms":
        await query.message.reply_text("🌐 المنصة المفعلة حالياً: Free Fire (منطقة ME)")

    elif data == "back_to_main":
        await query.message.edit_text("🤖 **SAIF BOT - القائمة الرئيسية**", reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
    print("🚀 SAIF BOT [Multi-Account Engine] يعمل الآن بكامل طاقته...")
    app.run_polling()
