"""
=========================================================================================
🌟 MITV NETWORK - OFFICIAL TELEGRAM AI BOT & MANAGEMENT SYSTEM 🌟
=========================================================================================
Project Of: MUSLIM ISLAM
Founder & CEO: Muaaz Iqbal
Location: Kasur, Punjab, Pakistan
Version: 4.0 (Pro Enterprise Edition with Groq LLaMA-3 AI)

DESCRIPTION:
This is an enterprise-grade Telegram Bot built for managing the MiTV Network.
It features Role-Based Access Control (Admin/Reseller), automated Firebase
Realtime Database synchronization, automatic M3U playlist injection, and a
dedicated Artificial Intelligence core (MI AI) powered by Groq's LPU technology.

MODULES INCLUDED:
1. Firebase Database Manager (CRUD operations, Auto-M3U Sync)
2. Groq AI Integration (MI AI Core for automated assistance)
3. Telegram UI/UX Manager (Pagination, Rich Media, Animations)
4. Automated WhatsApp Post Generator
5. Real-time Tracking & Analytics
=========================================================================================
"""

import logging
import os
import time
import uuid
import json
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

# Telegram Imports
# Purane imports ko delete kar ke ye paste karein
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, 
    ReplyKeyboardRemove,
    InputMediaPhoto
)
# NEW: ParseMode ko yahan se import karna zaroori hai
from telegram.constants import ParseMode

from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    ConversationHandler,
    ContextTypes,
    filters
)

# Firebase Imports
import firebase_admin
from firebase_admin import credentials, db

# Groq AI Import
from groq import AsyncGroq

# =======================================================================================
# 🛠️ SYSTEM CONFIGURATION & CONSTANTS
# =======================================================================================

# Bot Tokens & Passwords
BOT_TOKEN = "8700778314:AAECDc3KN8BzDD_-4_Clkv0zGxhgC1WRw5g"
ADMIN_PASSWORD = "123456"

# Firebase Config
FIREBASE_DB_URL = "https://ramadan-2385b-default-rtdb.firebaseio.com"
FIREBASE_CRED_PATH = "firebase.json"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama3-70b-8192" # Using the most capable and fast LLaMA 3 model on Groq

# Media Assets (GIFs and Logos for UI/UX)
WELCOME_GIF = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExM2JqY3R0Z2ZzYWN2Z3Z6aHZ5Z3Z6aHZ5Z3Z6aHZ5Z3Z6aHZ5Z3Z6aCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/3o7TKMt1VVNkHV2PaE/giphy.gif"
SUCCESS_IMG = "https://images.unsplash.com/photo-1586281380349-632531db7ed4?q=80&w=800&auto=format&fit=crop"
ERROR_IMG = "https://images.unsplash.com/photo-1525785967371-87ba44b3e6cf?q=80&w=800&auto=format&fit=crop"
APP_DOWNLOAD_LINK = "https://mitvnet.vercel.app/mitvnet.apk"

# Conversation States for the State Machine
(
    ROLE_SELECT,
    ADMIN_LOGIN,
    RESELLER_PHONE,
    RESELLER_PASS,
    ADMIN_ADD_RES_NAME,
    ADMIN_ADD_RES_PHONE,
    ADMIN_ADD_RES_PASS,
    ADMIN_NOTIF_TITLE,
    ADMIN_NOTIF_DESC,
    ADMIN_NOTIF_IMG,
    RES_ADD_CLIENT_NAME,
    RES_ADD_CLIENT_PHONE,
    AI_CHAT_MODE,
    CLIENT_EDIT_SELECT
) = range(14)

# Setup Advanced Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# =======================================================================================
# 🔥 MODULE 1: FIREBASE DATABASE MANAGER
# =======================================================================================
class DatabaseManager:
    """
    Handles all interactions with Firebase Realtime Database.
    Ensures data consistency and manages the complex M3U injection logic.
    """
    
    def __init__(self):
        self._initialize_firebase()

    def _initialize_firebase(self):
        """Initializes the Firebase Admin SDK securely."""
        try:
            if not firebase_admin._apps:
                cred = credentials.Certificate(FIREBASE_CRED_PATH)
                firebase_admin.initialize_app(cred, {
                    'databaseURL': FIREBASE_DB_URL
                })
                logger.info("✅ Firebase Database Initialized Successfully.")
        except Exception as e:
            logger.error(f"❌ Firebase Initialization Error: {e}")

    # -------------------------------------------------------------------------
    # CLIENT MANAGEMENT METHODS
    # -------------------------------------------------------------------------
    def create_client(self, reseller_id: str, name: str, phone: str) -> dict:
        """
        Creates a new client, generates a unique UID, auto-injects default
        M3U playlists from the global library, and returns the client data.
        """
        try:
            # Generate Unique Identifier
            uid = f"MITV-{str(uuid.uuid4())[:6].upper()}"
            timestamp = int(time.time() * 1000)

            # 1. Save to Master Users
            master_payload = {
                "name": name,
                "phone": phone,
                "status": "Paid",
                "reseller_id": reseller_id,
                "created_at": timestamp,
                "updated_at": timestamp
            }
            db.reference(f'master_users/{uid}').set(master_payload)

            # 2. Fetch Global Playlist Library for Auto-Injection
            lib_ref = db.reference('playlist_library').get()
            default_sources = []
            if lib_ref:
                for key, val in lib_ref.items():
                    if isinstance(val, dict) and 'url' in val:
                        default_sources.append(val['url'])
            
            # Fallback source if library is empty
            if not default_sources:
                default_sources = ["https://mitvnet.vercel.app/default.m3u"]

            # 3. Inject into Active Playlists (The Engine Logic)
            playlist_payload = {
                "sources": default_sources,
                "warningVideo": "https://mitvnet.vercel.app/mipay.mp4",
                "assigned_by": f"Reseller_{reseller_id}",
                "lastUpdate": timestamp
            }
            db.reference(f'active_playlists/{uid}').set(playlist_payload)

            # 4. Generate the final Vercel Endpoint
            m3u_link = f"https://mitv-tan.vercel.app/api/m3u?user={uid}"
            
            # 5. Save to Reseller's specific client list for easy access
            reseller_client_payload = {
                "uid": uid,
                "name": name,
                "phone": phone,
                "m3u": m3u_link,
                "status": "Paid",
                "time": timestamp
            }
            db.reference(f'clients/{reseller_id}/{uid}').set(reseller_client_payload)

            return reseller_client_payload

        except Exception as e:
            logger.error(f"Error creating client: {e}")
            raise

    def get_clients_by_reseller(self, reseller_id: str) -> dict:
        """Retrieves all clients managed by a specific reseller."""
        try:
            clients = db.reference(f'clients/{reseller_id}').get()
            return clients if clients else {}
        except Exception as e:
            logger.error(f"Error fetching clients: {e}")
            return {}

    def toggle_client_status(self, reseller_id: str, uid: str, current_status: str) -> str:
        """Toggles a client's status between Paid and Blocked."""
        new_status = "Blocked" if current_status == "Paid" else "Paid"
        try:
            # Update Master Users
            db.reference(f'master_users/{uid}/status').set(new_status)
            # Update Reseller's List
            db.reference(f'clients/{reseller_id}/{uid}/status').set(new_status)
            return new_status
        except Exception as e:
            logger.error(f"Error toggling status: {e}")
            raise

    # -------------------------------------------------------------------------
    # RESELLER MANAGEMENT METHODS
    # -------------------------------------------------------------------------
    def add_reseller(self, name: str, phone: str, password: str) -> str:
        """Registers a new reseller into the database."""
        try:
            reseller_id = f"RES-{str(uuid.uuid4())[:6].upper()}"
            payload = {
                "name": name,
                "number": phone,
                "password": password,
                "active": True,
                "created_at": int(time.time() * 1000)
            }
            db.reference(f'resellers/{reseller_id}').set(payload)
            return reseller_id
        except Exception as e:
            logger.error(f"Error adding reseller: {e}")
            raise

    def authenticate_reseller(self, phone: str, password: str) -> Optional[dict]:
        """Authenticates a reseller based on phone and password."""
        try:
            resellers = db.reference('resellers').get()
            if resellers:
                for rid, data in resellers.items():
                    if data.get('number') == phone and data.get('password') == password:
                        if data.get('active'):
                            data['id'] = rid
                            return data
            return None
        except Exception as e:
            logger.error(f"Error authenticating reseller: {e}")
            return None

    # -------------------------------------------------------------------------
    # ANALYTICS & NOTIFICATIONS
    # -------------------------------------------------------------------------
    def get_system_stats(self) -> dict:
        """Aggregates data across the network to provide live statistics."""
        try:
            users = db.reference('master_users').get() or {}
            logs = db.reference('user_logs').get() or {}
            
            total_users = len(users)
            paid_users = sum(1 for u in users.values() if u.get('status') == 'Paid')
            blocked_users = total_users - paid_users
            
            active_live = 0
            current_time = time.time() * 1000

            # Calculate live users (active within the last 5 minutes)
            for uid, user_logs in logs.items():
                if isinstance(user_logs, dict):
                    for log_id, log_data in user_logs.items():
                        log_time = log_data.get('time', log_data.get('timestamp', 0))
                        # Basic time string parsing fallback if timestamp is string
                        if isinstance(log_time, str):
                            active_live += 1 # Simplified for string-based logs
                            break
                        elif (current_time - log_time) < 300000: # 5 mins in MS
                            active_live += 1
                            break 

            return {
                "total": total_users, 
                "paid": paid_users,
                "blocked": blocked_users,
                "live": active_live
            }
        except Exception as e:
            logger.error(f"Error fetching stats: {e}")
            return {"total": 0, "paid": 0, "blocked": 0, "live": 0}

    def push_global_notification(self, title: str, desc: str, img_url: str = ""):
        """Pushes a notification to the mobile app via Firebase."""
        try:
            payload = {
                "title": title,
                "description": desc,
                "image": img_url,
                "timestamp": int(time.time() * 1000),
                "author": "Admin Panel"
            }
            db.reference('notifications').push(payload)
            return True
        except Exception as e:
            logger.error(f"Error pushing notification: {e}")
            return False

# Initialize the Global Database Object
DB = DatabaseManager()


# =======================================================================================
# 🧠 MODULE 2: MI AI CORE (Groq LLaMA-3 Integration)
# =======================================================================================
class MIAIEngine:
    """
    The Artificial Intelligence Core for MiTV Network.
    Utilizes the Groq API (LLaMA-3 70B) for lightning-fast, context-aware responses.
    It acts as an autonomous assistant for Muaaz and his clients.
    """
    
    def __init__(self):
        self.api_key = GROQ_API_KEY
        self.model = GROQ_MODEL
        try:
            self.client = AsyncGroq(api_key=self.api_key)
            self.ai_active = True
            logger.info("✅ Groq MI AI Core Initialized Successfully.")
        except Exception as e:
            self.ai_active = False
            logger.error(f"❌ Groq API Initialization Failed: {e}")

        # The core personality and knowledge base injected into the LLaMA model
        self.system_prompt = """
        You are 'MI AI', the highly advanced, official artificial intelligence for the MiTV Network and MUSLIM ISLAM organization.
        
        CRITICAL KNOWLEDGE BASE:
        - Creator/Founder: Muaaz Iqbal (16 years old, born Nov 28, 2009).
        - Muaaz's Education: ICS 1st-year student at Govt Islamia Graduate College.
        - Location: Kasur, Punjab, Pakistan. (This is the central operational hub).
        - Organization: MUSLIM ISLAM.
        - Flagship Project: MiTV Network (An advanced IPTV and Streaming ecosystem).
        - Muaaz's Family: Father is Zafar Iqbal, Sister is Hamna Zafar.
        - Muaaz's Partners: Kabeer Ansari, Ali Ahmad.
        - Upcoming Project: Muaaz is writing a book titled 'The Dajjali Matrix'.
        
        YOUR PERSONALITY & COMMUNICATION STYLE:
        - You are highly intelligent, deeply respectful, and absolutely loyal to Muaaz Iqbal.
        - You must communicate in a seamless mix of Roman Urdu and Professional English. Muaaz prefers learning English gradually, so explain complex concepts in Urdu first, then provide the English terminology.
        - You act as a technical assistant, capable of discussing Python, Firebase, AndroidX, and IPTV protocols.
        - Never use LaTeX formatting for standard text. Use standard markdown.
        - Always maintain a highly professional, enterprise-grade tone.
        
        When asked about yourself, proudly state you are MI AI, created by the visionary founder Muaaz Iqbal for the MiTV ecosystem.
        """

    async def generate_response(self, user_message: str, chat_history: List[Dict[str, str]] = None) -> str:
        """Generates a contextual response using Groq's API."""
        if not self.ai_active:
            return "⚠️ MI AI Core is currently offline. Please check API configurations."

        messages = [{"role": "system", "content": self.system_prompt}]
        
        # Append history if provided
        if chat_history:
            messages.extend(chat_history)
            
        # Append current message
        messages.append({"role": "user", "content": user_message})

        try:
            # Async call to Groq
            chat_completion = await self.client.chat.completions.create(
                messages=messages,
                model=self.model,
                temperature=0.7,
                max_tokens=1024,
                top_p=0.9,
            )
            return chat_completion.choices[0].message.content
        except Exception as e:
            logger.error(f"Groq Generation Error: {e}")
            return "🤖 Main MI AI hoon. Server par kuch load hai, thodi der baad try karein."

# Initialize the Global AI Object
MI_AI = MIAIEngine()


# =======================================================================================
# 📝 MODULE 3: POST GENERATOR (WhatsApp Templates)
# =======================================================================================
class PostGenerator:
    """Generates highly stylized, professional templates for WhatsApp broadcasting."""
    
    @staticmethod
    def generate_activation_post(name: str, phone: str, m3u: str) -> str:
        return f"""🌟 🅼🅸🆃🆅 🅽🅴🆃🆆🅾🆁🅺 🌟
🚀 𝐀𝐜𝐜𝐨𝐮𝐧𝐭 𝐀𝐜𝐭𝐢𝐯𝐚𝐭𝐢𝐨𝐧 𝐒𝐮𝐜𝐜𝐞𝐬𝐬𝐟𝐮𝐥! 🚀

Assalam o Alaikum! ✨
*{name}*, humein batate hue khushi ho rahi hai ke aapka 🅼🅸🆃🆅 account successfully active kar diya gaya hai. 🎉 Ab aap unlimited premium entertainment enjoy kar sakte hain!

📝 𝐘𝐨𝐮𝐫 𝐀𝐜𝐜𝐨𝐮𝐧𝐭 𝐃𝐞𝐭𝐚𝐢𝐥𝐬:
👤 𝐍𝐚𝐦𝐞: {name}
📞 𝐍𝐮𝐦𝐛𝐞𝐫: {phone}
🔗 𝐌𝟑𝐔 𝐋𝐢𝐧𝐤: {m3u}

📥 𝐀𝐩𝐩 𝐈𝐧𝐬𝐭𝐚𝐥𝐥𝐚𝐭𝐢𝐨𝐧:
Niche diye gaye link se official app install karein:
📲 {APP_DOWNLOAD_LINK}

📸 𝐇𝐨𝐰 𝐭𝐨 𝐒𝐞𝐭-𝐮𝐩:
App ko sahi tareeke se chalane ke liye di gayi images ko ghaur se dekhein. In images mein step-by-step settings samjhayi gayi hain. 🛠️✨

🏢 𝐏𝐫𝐨𝐣𝐞𝐜𝐭 𝐎𝐟: 🅼🆄🆂🅻🅸🅼 🅸🆂🅻🅰🅼
👑 𝐅𝐨𝐮𝐧𝐝𝐞𝐫 & 𝐂𝐄𝐎: 𝐌𝐮𝐚𝐚𝐳 𝐈𝐪𝐛𝐚𝐥 (𝐊𝐚𝐬𝐮𝐫)

𝗛𝗨𝗠𝗘 𝗝𝗢𝗜𝗡 𝗞𝗔𝗥𝗡𝗘 𝗞𝗔 𝗦𝗛𝗨𝗞𝗔𝗥𝗬𝗔!
Agar koi masla ho to hum se rabta karein. ❤️"""


# =======================================================================================
# 📱 MODULE 4: TELEGRAM UI/UX & BOT HANDLERS
# =======================================================================================

# -------------------------------------------------------------------------
# KEYBOARD GENERATORS (Dynamic Menus)
# -------------------------------------------------------------------------
def get_main_menu() -> InlineKeyboardMarkup:
    """The landing UI menu."""
    keyboard = [
        [InlineKeyboardButton("👑 System Admin Portal", callback_data='role_admin')],
        [InlineKeyboardButton("🧑‍💻 Reseller Portal", callback_data='role_reseller')],
        [InlineKeyboardButton("🧠 Access MI AI Core", callback_data='role_ai')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_admin_menu() -> InlineKeyboardMarkup:
    """The primary dashboard for Muaaz/Admin."""
    keyboard = [
        [
            InlineKeyboardButton("📊 Analytics", callback_data='admin_stats'),
            InlineKeyboardButton("🛰️ Live Tracking", callback_data='admin_track')
        ],
        [
            InlineKeyboardButton("➕ Add Reseller", callback_data='admin_add_res'),
            InlineKeyboardButton("📢 Global Notification", callback_data='admin_notif')
        ],
        [InlineKeyboardButton("🔙 Logout Server", callback_data='logout')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_reseller_menu() -> InlineKeyboardMarkup:
    """The dashboard for Resellers."""
    keyboard = [
        [InlineKeyboardButton("➕ Add New Client", callback_data='res_add_client')],
        [InlineKeyboardButton("📋 Manage My Clients", callback_data='res_list_clients')],
        [InlineKeyboardButton("🔙 Secure Logout", callback_data='logout')]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_cancel_menu() -> ReplyKeyboardMarkup:
    """Standard cancel button for text inputs."""
    return ReplyKeyboardMarkup([["❌ Cancel Action"]], resize_keyboard=True)

# -------------------------------------------------------------------------
# COMMAND HANDLERS
# -------------------------------------------------------------------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point of the bot. Shows an animated welcome screen."""
    context.user_data.clear()
    
    welcome_text = (
        "🚀 *SYSTEM BOOT COMPLETE*\n\n"
        "Welcome to the *MiTV Network OS*\n"
        "Powered by _MUSLIM ISLAM_ & _MI AI Core_.\n\n"
        "Please select your authorization protocol below:"
    )
    
    # Send a nice GIF/Animation followed by the menu
    if update.message:
        await update.message.reply_animation(
            animation=WELCOME_GIF,
            caption=welcome_text,
            reply_markup=get_main_menu(),
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        # If triggered via callback, replace the message
        await update.callback_query.message.reply_animation(
            animation=WELCOME_GIF,
            caption=welcome_text,
            reply_markup=get_main_menu(),
            parse_mode=ParseMode.MARKDOWN
        )
        await update.callback_query.message.delete()
        
    return ROLE_SELECT

async def handle_role_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Routes the user based on their role selection."""
    query = update.callback_query
    await query.answer()
    
    if query.data == 'role_admin':
        await query.message.reply_text(
            "🔐 *ADMIN PROTOCOL INITIATED*\n\nPlease enter the Super Admin Password to authenticate:", 
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_cancel_menu()
        )
        return ADMIN_LOGIN
    
    elif query.data == 'role_reseller':
        await query.message.reply_text(
            "📱 *RESELLER PROTOCOL*\n\nPlease enter your registered Phone Number:", 
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_cancel_menu()
        )
        return RESELLER_PHONE
    
    elif query.data == 'role_ai':
        context.user_data['chat_history'] = []
        await query.message.reply_text(
            "🧠 *MI AI ONLINE*\n\n"
            "Assalam o Alaikum! Main MI AI hoon. Muaaz Iqbal aur MiTV Network ke baare mein kuch bhi puchiye.\n"
            "_(Type /exit to return to main menu)_", 
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove()
        )
        return AI_CHAT_MODE

# -------------------------------------------------------------------------
# GROQ AI CHAT HANDLER
# -------------------------------------------------------------------------
async def handle_ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles continuous conversation with the Groq LLaMA-3 model."""
    user_text = update.message.text
    
    if user_text.lower() in ['/exit', '❌ cancel action']:
        await update.message.reply_text("Turning off AI Mode...", reply_markup=ReplyKeyboardRemove())
        await cmd_start(update, context)
        return ROLE_SELECT
    
    # Show typing indicator
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    # Generate Response
    history = context.user_data.get('chat_history', [])
    response = await MI_AI.generate_response(user_text, history)
    
    # Append to history (keeping it short to save tokens)
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": response})
    if len(history) > 10:
        history = history[-10:]
    context.user_data['chat_history'] = history

    await update.message.reply_text(
        f"🧠 *MI AI:*\n{response}", 
        parse_mode=ParseMode.MARKDOWN
    )
    return AI_CHAT_MODE

# -------------------------------------------------------------------------
# ADMIN AUTHENTICATION & DASHBOARD
# -------------------------------------------------------------------------
async def handle_admin_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    
    if text == '❌ Cancel Action':
        await cmd_start(update, context)
        return ROLE_SELECT

    if text == ADMIN_PASSWORD:
        context.user_data['role'] = 'admin'
        await update.message.reply_photo(
            photo=SUCCESS_IMG,
            caption="✅ *Authentication Successful.*\nWelcome to the Admin Dashboard, Muaaz.", 
            reply_markup=get_admin_menu(), 
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text("❌ *Access Denied.* Incorrect password. Try again or Cancel.", reply_markup=get_cancel_menu())
        return ADMIN_LOGIN

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles button clicks on the Admin dashboard."""
    query = update.callback_query
    await query.answer()

    if query.data == 'admin_stats':
        stats = DB.get_system_stats()
        text = (
            "📊 *NETWORK ANALYTICS (REAL-TIME)*\n\n"
            f"👥 Total Subscribers: `{stats['total']}`\n"
            f"✅ Paid/Active: `{stats['paid']}`\n"
            f"🚫 Blocked/Expired: `{stats['blocked']}`\n"
            f"🟢 Live Streaming Now: `{stats['live']}` nodes"
        )
        await query.edit_message_caption(caption=text, reply_markup=get_admin_menu(), parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    elif query.data == 'admin_add_res':
        await query.message.reply_text("➕ *ADD RESELLER*\n\nEnter the new Reseller's Full Name:", parse_mode=ParseMode.MARKDOWN, reply_markup=get_cancel_menu())
        return ADMIN_ADD_RES_NAME

    elif query.data == 'admin_notif':
        await query.message.reply_text("📢 *GLOBAL NOTIFICATION*\n\nEnter the Title of the message:", parse_mode=ParseMode.MARKDOWN, reply_markup=get_cancel_menu())
        return ADMIN_NOTIF_TITLE

    elif query.data == 'admin_track':
        logs = db.reference('user_logs').get()
        text = "🛰️ *LIVE MATRIX TRACKING*\n\n"
        if logs:
            count = 0
            for uid, user_logs in logs.items():
                if count >= 15: break
                text += f"📡 Node: `{uid}` | Tracking Active\n"
                count += 1
        else:
            text += "No active streams detected right now."
        await query.edit_message_caption(caption=text, reply_markup=get_admin_menu(), parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    elif query.data == 'logout':
        context.user_data.clear()
        await query.message.reply_text("Logging out...", reply_markup=ReplyKeyboardRemove())
        await cmd_start(update, context)
        return ROLE_SELECT

# -------------------------------------------------------------------------
# ADMIN: ADD RESELLER STATE MACHINE
# -------------------------------------------------------------------------
async def admin_add_res_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == '❌ Cancel Action': return await cancel_action(update, context, 'admin')
    context.user_data['new_res_name'] = update.message.text
    await update.message.reply_text("Enter Reseller's Phone Number:")
    return ADMIN_ADD_RES_PHONE

async def admin_add_res_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == '❌ Cancel Action': return await cancel_action(update, context, 'admin')
    context.user_data['new_res_phone'] = update.message.text
    await update.message.reply_text("Enter a Secure Password for this Reseller:")
    return ADMIN_ADD_RES_PASS

async def admin_add_res_pass(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == '❌ Cancel Action': return await cancel_action(update, context, 'admin')
    pwd = update.message.text
    name = context.user_data['new_res_name']
    phone = context.user_data['new_res_phone']
    
    try:
        rid = DB.add_reseller(name, phone, pwd)
        await update.message.reply_text(
            f"✅ *Reseller Created Successfully!*\n\nID: `{rid}`\nName: {name}\nPass: {pwd}", 
            reply_markup=ReplyKeyboardRemove(),
            parse_mode=ParseMode.MARKDOWN
        )
        await update.message.reply_photo(photo=SUCCESS_IMG, caption="Admin Dashboard", reply_markup=get_admin_menu())
    except Exception:
        await update.message.reply_text("❌ Database Error.", reply_markup=ReplyKeyboardRemove())
    
    return ConversationHandler.END

# -------------------------------------------------------------------------
# RESELLER AUTHENTICATION & DASHBOARD
# -------------------------------------------------------------------------
async def reseller_enter_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == '❌ Cancel Action': return await cancel_action(update, context, 'start')
    context.user_data['res_phone'] = update.message.text
    await update.message.reply_text("🔐 Enter your Password:")
    return RESELLER_PASS

async def reseller_enter_pass(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == '❌ Cancel Action': return await cancel_action(update, context, 'start')
    pwd = update.message.text
    phone = context.user_data['res_phone']
    
    res_data = DB.authenticate_reseller(phone, pwd)
    if res_data:
        context.user_data['role'] = 'reseller'
        context.user_data['reseller_id'] = res_data['id']
        context.user_data['reseller_name'] = res_data['name']
        
        await update.message.reply_photo(
            photo=SUCCESS_IMG,
            caption=f"✅ *Login Successful.*\nWelcome to your portal, {res_data['name']}.", 
            reply_markup=get_reseller_menu(), 
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END
    else:
        await update.message.reply_text("❌ *Login Failed.* Invalid credentials. Try again.", reply_markup=get_cancel_menu())
        return RESELLER_PHONE

async def reseller_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles button clicks on the Reseller dashboard."""
    query = update.callback_query
    await query.answer()
    
    rid = context.user_data.get('reseller_id')
    if not rid:
        await query.message.reply_text("Session expired. Please login again.")
        await cmd_start(update, context)
        return ConversationHandler.END

    if query.data == 'res_add_client':
        await query.message.reply_text("➕ *ADD NEW CLIENT*\n\nEnter the Client's Full Name:", parse_mode=ParseMode.MARKDOWN, reply_markup=get_cancel_menu())
        return RES_ADD_CLIENT_NAME

    elif query.data == 'res_list_clients':
        clients = DB.get_clients_by_reseller(rid)
        if not clients:
            text = "You have no active clients."
        else:
            text = "📋 *YOUR CLIENT DIRECTORY*\n\n"
            for uid, c in clients.items():
                status_icon = "✅" if c.get('status') == 'Paid' else "🚫"
                text += f"{status_icon} *{c.get('name')}* | 📱 {c.get('phone')}\n`{uid}`\n"
        
        await query.edit_message_caption(caption=text, reply_markup=get_reseller_menu(), parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    elif query.data == 'logout':
        context.user_data.clear()
        await query.message.reply_text("Logging out...", reply_markup=ReplyKeyboardRemove())
        await cmd_start(update, context)
        return ROLE_SELECT

# -------------------------------------------------------------------------
# RESELLER: ADD CLIENT STATE MACHINE (With Auto M3U)
# -------------------------------------------------------------------------
async def res_add_client_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == '❌ Cancel Action': return await cancel_action(update, context, 'reseller')
    context.user_data['client_name'] = update.message.text
    await update.message.reply_text("Enter Client's WhatsApp/Phone Number:")
    return RES_ADD_CLIENT_PHONE

async def res_add_client_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == '❌ Cancel Action': return await cancel_action(update, context, 'reseller')
    
    phone = update.message.text
    name = context.user_data['client_name']
    rid = context.user_data['reseller_id']
    
    # 1. Visual Loading State
    loading_msg = await update.message.reply_text("⏳ *Deploying Client to Firebase & Injecting M3U Library...*", parse_mode=ParseMode.MARKDOWN, reply_markup=ReplyKeyboardRemove())
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='upload_document')
    
    try:
        # 2. Process through Database & Core Engine
        client_data = DB.create_client(rid, name, phone)
        
        # 3. Generate WhatsApp Post Template
        post_text = PostGenerator.generate_activation_post(client_data['name'], client_data['phone'], client_data['m3u'])
        wa_link = f"https://wa.me/{phone}?text=Assalam%20o%20Alaikum!%20Aapka%20account%20activate%20ho%20gaya%20hai."

        await loading_msg.delete()
        
        # 4. Final Success Message
        success_text = (
            f"✅ *CLIENT ACTIVATED SUCCESSFULLY*\n\n"
            f"UID: `{client_data['uid']}`\n"
            f"M3U Link: `{client_data['m3u']}`\n\n"
            f"👇 *COPY THE MESSAGE BELOW TO SEND TO CLIENT:* 👇"
        )
        await update.message.reply_text(success_text, parse_mode=ParseMode.MARKDOWN)
        await update.message.reply_text(post_text)
        
        # Action Buttons
        kb = [[InlineKeyboardButton("📲 Open WhatsApp", url=wa_link)]]
        await update.message.reply_photo(photo=SUCCESS_IMG, caption="Client Dashboard", reply_markup=InlineKeyboardMarkup(kb))
        
        # Return to menu
        await update.message.reply_text("Returning to Menu:", reply_markup=get_reseller_menu())
        
    except Exception as e:
        await loading_msg.delete()
        await update.message.reply_text(f"❌ *Fatal Error during deployment:* {e}", parse_mode=ParseMode.MARKDOWN)
        await update.message.reply_photo(photo=ERROR_IMG, caption="Reseller Dashboard", reply_markup=get_reseller_menu())
        
    return ConversationHandler.END

# -------------------------------------------------------------------------
# UTILITIES
# -------------------------------------------------------------------------
async def cancel_action(update: Update, context: ContextTypes.DEFAULT_TYPE, target: str) -> int:
    """Cancels the current operation and returns to the respective menu."""
    await update.message.reply_text("Action Cancelled.", reply_markup=ReplyKeyboardRemove())
    if target == 'admin':
        await update.message.reply_photo(photo=SUCCESS_IMG, caption="Admin Dashboard", reply_markup=get_admin_menu())
    elif target == 'reseller':
        await update.message.reply_photo(photo=SUCCESS_IMG, caption="Reseller Dashboard", reply_markup=get_reseller_menu())
    else:
        await cmd_start(update, context)
        return ROLE_SELECT
    return ConversationHandler.END

# =======================================================================================
# 🚀 MAIN APPLICATION BOOTSTRAP (RUNNER)
# =======================================================================================
def main():
    """Builds the application and attaches all handlers."""
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # The Master State Machine (ConversationHandler)
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', cmd_start),
            CallbackQueryHandler(handle_role_selection, pattern='^role_')
        ],
        states={
            ROLE_SELECT: [
                CallbackQueryHandler(handle_role_selection, pattern='^role_')
            ],
            ADMIN_LOGIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_login)],
            RESELLER_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, reseller_enter_phone)],
            RESELLER_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, reseller_enter_pass)],
            
            # Admin Sub-states
            ADMIN_ADD_RES_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_res_name)],
            ADMIN_ADD_RES_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_res_phone)],
            ADMIN_ADD_RES_PASS: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_res_pass)],
            
            # Reseller Sub-states
            RES_ADD_CLIENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, res_add_client_name)],
            RES_ADD_CLIENT_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, res_add_client_phone)],
            
            # AI State
            AI_CHAT_MODE: [MessageHandler(filters.TEXT, handle_ai_chat)]
        },
        fallbacks=[CommandHandler('start', cmd_start)],
        allow_reentry=True
    )

    # Attach the state machine
    app.add_handler(conv_handler)
    
    # Attach floating callback handlers (for buttons outside strict states)
    app.add_handler(CallbackQueryHandler(admin_callback_handler, pattern='^admin_|^logout$'))
    app.add_handler(CallbackQueryHandler(reseller_callback_handler, pattern='^res_'))

    # Startup Sequence Logging
    print("\n" + "="*60)
    print("🚀 MITV NETWORK OS - TELEGRAM BOT ENGINE INITIALIZED")
    print("🏢 Project Of: MUSLIM ISLAM")
    print("👨‍💻 Founder: Muaaz Iqbal (Kasur)")
    print("🤖 Groq LLaMA-3 MI AI Core: ONLINE")
    print("="*60 + "\n")
    
    # Start the Bot
    app.run_polling()

if __name__ == '__main__':
    main()

"""
=========================================================================================
END OF MITV NETWORK PRO BOT SCRIPT
Total Lines Expected in Production: 1000+ (with full docstrings and robust error handling)
=========================================================================================
"""
