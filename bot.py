import firebase_admin
from firebase_admin import credentials, db
from telegram import *
from telegram.ext import *
import time, uuid
from config import *

cred = credentials.Certificate("firebase.json")
firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_DB})

sessions = {}

# 🔥 START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [["👑 Admin", "🧑‍💻 Reseller"]]

    await update.message.reply_photo(
        photo=LOGO_URL,
        caption="✨ *MI TV AI SYSTEM*\n\nSelect your role:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )

# 🔥 MAIN HANDLER
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.message.from_user.id)
    text = update.message.text

    if uid not in sessions:
        sessions[uid] = {}

    s = sessions[uid]

    # ROLE
    if text == "👑 Admin":
        s.clear()
        s["role"] = "admin"
        await update.message.reply_text("🔐 Enter Admin Password")

    elif text == "🧑‍💻 Reseller":
        s.clear()
        s["role"] = "reseller"
        await update.message.reply_text("📱 Enter Number")

    # ADMIN LOGIN
    elif s.get("role") == "admin" and not s.get("login"):
        if text == ADMIN_PASSWORD:
            s["login"] = True
            await admin_panel(update)
        else:
            await update.message.reply_text("❌ Wrong Password")

    # ADMIN MENU
    elif text == "➕ Add Reseller":
        s["add"] = {}
        await update.message.reply_text("Name?")

    elif "add" in s:
        a = s["add"]

        if "name" not in a:
            a["name"] = text
            await update.message.reply_text("Number?")

        elif "number" not in a:
            a["number"] = text
            await update.message.reply_text("Password?")

        else:
            a["password"] = text
            db.reference("resellers").push(a)
            await update.message.reply_text("✅ Reseller Added 🎉")
            del s["add"]

    # NOTIFICATION
    elif text == "📢 Notification":
        s["noti"] = {}
        await update.message.reply_text("Title?")

    elif "noti" in s:
        n = s["noti"]

        if "title" not in n:
            n["title"] = text
            await update.message.reply_text("Description?")

        elif "desc" not in n:
            n["desc"] = text
            await update.message.reply_text("Image URL or skip")

        else:
            n["img"] = text if text != "skip" else ""
            n["time"] = int(time.time())
            db.reference("notifications").push(n)

            # Send to all resellers
            resellers = db.reference("resellers").get()
            if resellers:
                for r in resellers.values():
                    try:
                        await context.bot.send_message(
                            chat_id=r.get("chat_id"),
                            text=f"📢 {n['title']}\n{n['desc']}"
                        )
                    except:
                        pass

            await update.message.reply_text("✅ Sent")
            del s["noti"]

    # TRACKING
    elif text == "📊 Tracking":
        data = db.reference("tracking").get()
        msg = "📡 Live Users:\n\n"

        if data:
            for k, v in data.items():
                msg += f"{k} | {v.get('channel')} | {v.get('status')}\n"

        await update.message.reply_text(msg)

    # RESELLER LOGIN
    elif s.get("role") == "reseller" and not s.get("number"):
        s["number"] = text
        await update.message.reply_text("Password?")

    elif s.get("role") == "reseller" and not s.get("login"):
        data = db.reference("resellers").get()

        for k, v in data.items():
            if v["number"] == s["number"] and v["password"] == text:
                s["login"] = True
                s["id"] = k

                # save chat_id
                db.reference(f"resellers/{k}/chat_id").set(uid)

                await reseller_panel(update)
                return

        await update.message.reply_text("❌ Login Failed")

    # ADD CLIENT
    elif text == "➕ Add Client":
        s["client"] = {}
        await update.message.reply_text("Client Name?")

    elif "client" in s:
        c = s["client"]

        if "name" not in c:
            c["name"] = text
            await update.message.reply_text("Number?")

        else:
            c["number"] = text
            uidc = str(uuid.uuid4())[:8]

            m3u = f"https://mitv-tan.vercel.app/api/m3u?user={uidc}"

            db.reference(f"clients/{s['id']}").push({
                "name": c["name"],
                "number": c["number"],
                "m3u": m3u
            })

            msg = f"🔥 MITV\nName: {c['name']}\nNumber: {c['number']}\nM3U: {m3u}"
            wa = f"https://wa.me/{c['number']}?text={msg}"

            await update.message.reply_text(msg)
            await update.message.reply_text(f"📤 Send:\n{wa}")

            del s["client"]

# PANELS
async def admin_panel(update):
    kb = [["➕ Add Reseller", "📢 Notification"], ["📊 Tracking"]]
    await update.message.reply_text("👑 Admin Panel", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

async def reseller_panel(update):
    kb = [["➕ Add Client"]]
    await update.message.reply_text("🧑‍💻 Reseller Panel", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

# RUN
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT, handle))

print("🔥 BOT RUNNING")
app.run_polling()