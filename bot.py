import firebase_admin
from firebase_admin import credentials, db
from telegram import *
from telegram.ext import *
import time
import uuid
from config import BOT_TOKEN, ADMIN_PASSWORD, FIREBASE_DB

# 🔥 Firebase Init
cred = credentials.Certificate("firebase.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': FIREBASE_DB
})

# 🔥 Sessions
sessions = {}

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [["👑 Admin", "🧑‍💻 Reseller"]]
    await update.message.reply_text(
        "🔥 Welcome to MI TV AI Bot\n\nSelect Role:",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )

# ================= MAIN HANDLER =================
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    text = update.message.text

    if user_id not in sessions:
        sessions[user_id] = {}

    s = sessions[user_id]

    # ========= ROLE =========
    if text == "👑 Admin":
        s.clear()
        s["role"] = "admin"
        await update.message.reply_text("🔐 Enter Admin Password:")

    elif text == "🧑‍💻 Reseller":
        s.clear()
        s["role"] = "reseller"
        await update.message.reply_text("📱 Enter Number:")

    # ========= ADMIN LOGIN =========
    elif s.get("role") == "admin" and not s.get("login"):
        if text == ADMIN_PASSWORD:
            s["login"] = True
            await admin_panel(update)
        else:
            await update.message.reply_text("❌ Wrong Password")

    # ========= ADMIN PANEL =========
    elif text == "➕ Add Reseller":
        s["add_reseller"] = {}
        await update.message.reply_text("Enter Name:")

    elif "add_reseller" in s:
        ar = s["add_reseller"]

        if "name" not in ar:
            ar["name"] = text
            await update.message.reply_text("Enter Number:")

        elif "number" not in ar:
            ar["number"] = text
            await update.message.reply_text("Enter Password:")

        elif "password" not in ar:
            ar["password"] = text
            db.reference("resellers").push(ar)
            await update.message.reply_text("✅ Reseller Added")
            del s["add_reseller"]

    elif text == "📢 Send Notification":
        s["notify"] = {}
        await update.message.reply_text("Enter Title:")

    elif "notify" in s:
        n = s["notify"]

        if "title" not in n:
            n["title"] = text
            await update.message.reply_text("Enter Description:")

        elif "desc" not in n:
            n["desc"] = text
            await update.message.reply_text("Send Image URL or type skip")

        elif "img" not in n:
            n["img"] = text if text != "skip" else ""
            n["time"] = int(time.time())

            db.reference("notifications").push(n)
            await update.message.reply_text("✅ Notification Sent")
            del s["notify"]

    elif text == "📊 Tracking":
        data = db.reference("tracking").get()
        msg = "📡 Live Tracking:\n\n"

        if data:
            for k, v in data.items():
                msg += f"{k} | {v.get('channel')} | {v.get('status')}\n"

        await update.message.reply_text(msg)

    # ========= RESELLER LOGIN =========
    elif s.get("role") == "reseller" and not s.get("number"):
        s["number"] = text
        await update.message.reply_text("Enter Password:")

    elif s.get("role") == "reseller" and not s.get("login"):
        data = db.reference("resellers").get()

        for k, v in data.items():
            if v["number"] == s["number"] and v["password"] == text:
                s["login"] = True
                s["reseller_id"] = k
                await reseller_panel(update)
                return

        await update.message.reply_text("❌ Login Failed")

    # ========= ADD CLIENT =========
    elif text == "➕ Add Client":
        s["client"] = {}
        await update.message.reply_text("Client Name:")

    elif "client" in s:
        c = s["client"]

        if "name" not in c:
            c["name"] = text
            await update.message.reply_text("Client Number:")

        elif "number" not in c:
            c["number"] = text
            uid = str(uuid.uuid4())[:8]

            m3u = f"https://mitv-tan.vercel.app/api/m3u?user={uid}"

            db.reference(f"clients/{s['reseller_id']}").push({
                "name": c["name"],
                "number": c["number"],
                "m3u": m3u,
                "time": int(time.time())
            })

            # Post Generate
            msg = f"""
🔥 MITV PANEL 🔥

👤 Name: {c['name']}
📱 Number: {c['number']}
🔗 M3U: {m3u}
"""

            wa = f"https://wa.me/{c['number']}?text={msg}"

            await update.message.reply_text(msg)
            await update.message.reply_text(f"📤 WhatsApp Send:\n{wa}")

            del s["client"]

    elif text == "📂 My Clients":
        data = db.reference(f"clients/{s['reseller_id']}").get()

        msg = "📋 Clients:\n\n"
        if data:
            for v in data.values():
                msg += f"{v['name']} - {v['m3u']}\n"

        await update.message.reply_text(msg)

# ================= PANELS =================
async def admin_panel(update):
    kb = [
        ["➕ Add Reseller", "📢 Send Notification"],
        ["📊 Tracking"]
    ]
    await update.message.reply_text(
        "👑 Admin Panel",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )

async def reseller_panel(update):
    kb = [
        ["➕ Add Client", "📂 My Clients"]
    ]
    await update.message.reply_text(
        "🧑‍💻 Reseller Panel",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )

# ================= MAIN =================
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT, handle))

print("🚀 BOT RUNNING...")
app.run_polling()