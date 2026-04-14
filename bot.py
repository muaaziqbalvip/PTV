"""
=========================================================================================
🌟 MITV NETWORK OS — TELEGRAM BOT ENGINE v6.0 (ULTRA ENTERPRISE EDITION) 🌟
=========================================================================================
Project Of   : MUSLIM ISLAM
Founder & CEO: Muaaz Iqbal (Born Nov 28, 2009 — 16 years old)
Location     : Kasur, Punjab, Pakistan
Version      : 6.0 — Powered by Claude claude-sonnet-4-20250514 (Anthropic)
Firebase DB  : ramadan-2385b
Vercel API   : https://mitv-tan.vercel.app/api/m3u?user=MITV-XXXXX

MAJOR UPGRADES IN v6.0:
  ✅ AI upgraded to Claude claude-sonnet-4-20250514 (Anthropic) — far superior to Groq LLaMA-3
  ✅ AI responds directly in Groups (no /start needed)
  ✅ Thinking/typing animation with multi-step status dots
  ✅ Full bot takeover if user says "bot control" — hands API to user
  ✅ Smooth callback routing — no more stuck states
  ✅ Rich inline button menus everywhere
  ✅ Group-aware AI (understands group context)
  ✅ Admin can broadcast to all users
  ✅ Reseller gets WhatsApp post + direct open button
  ✅ Deep client search by name/phone
  ✅ All errors handled silently
=========================================================================================

DATABASE STRUCTURE (Firebase Realtime DB):
  /master_users/{uid}            — name, phone, status, reseller_id, created_at, updated_at
  /active_playlists/{uid}        — sources[], warningVideo, assigned_by, lastUpdate
  /clients/{reseller_id}/{uid}   — uid, name, phone, m3u, status, time
  /resellers/{reseller_id}       — name, number, password, active, created_at
  /playlist_library/{push_id}    — name, url, added
  /notifications/{push_id}       — title, description, image, timestamp, author
  /user_logs/{uid}/{log_id}      — channel, ip, time, device
  /global_stats/{uid}            — total, active, dead, last_scan
  /bot_sessions/{telegram_id}    — role, reseller_id, reseller_name, last_active
=========================================================================================
"""

import logging
import os
import time
import uuid
import json
import asyncio
import re
import html
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

# ===========================================================================
# TELEGRAM IMPORTS
# ===========================================================================
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InputMediaPhoto,
    BotCommand,
    ChatAction,
)
from telegram.constants import ParseMode, ChatType
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from telegram.error import BadRequest, TelegramError

# ===========================================================================
# FIREBASE IMPORTS
# ===========================================================================
import firebase_admin
from firebase_admin import credentials, db

# ===========================================================================
# ANTHROPIC CLAUDE IMPORT (PRIMARY AI ENGINE)
# ===========================================================================
try:
    import anthropic
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False

# ===========================================================================
# GROQ FALLBACK IMPORT
# ===========================================================================
try:
    from groq import AsyncGroq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

# ===========================================================================
# ⚙️  SYSTEM CONFIGURATION
# ===========================================================================

BOT_TOKEN      = "8700778314:AAECDc3KN8BzDD_-4_Clkv0zGxhgC1WRw5g"
ADMIN_PASSWORD = "123456"

# Firebase
FIREBASE_DB_URL    = "https://ramadan-2385b-default-rtdb.firebaseio.com"
FIREBASE_CRED_PATH = "firebase.json"

# AI Keys (set as env vars for security)
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")
GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")

# AI Model — Claude claude-sonnet-4-20250514 (Anthropic) — MOST POWERFUL
CLAUDE_MODEL = "claude-sonnet-4-20250514"
GROQ_MODEL   = "llama3-70b-8192"    # fallback only

# Vercel
VERCEL_BASE       = "https://mitv-tan.vercel.app/api/m3u?user="
APP_DOWNLOAD_LINK = "https://mitvnet.vercel.app/mitvnet.apk"

# Media Assets
SUCCESS_IMG = "https://images.unsplash.com/photo-1586281380349-632531db7ed4?q=80&w=800&auto=format&fit=crop"
ERROR_IMG   = "https://images.unsplash.com/photo-1525785967371-87ba44b3e6cf?q=80&w=800&auto=format&fit=crop"
BANNER_IMG  = "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?q=80&w=800&auto=format&fit=crop"
WELCOME_GIF = "https://media1.giphy.com/media/3o7TKMt1VVNkHV2PaE/giphy.gif"

# Pagination
PAGE_SIZE = 5

# Group AI: bot responds when mentioned or reply
GROUP_AI_ENABLED = True

# Thinking animation frames
THINKING_FRAMES = [
    "🧠 *MI AI soch raha hai*",
    "🧠 *MI AI soch raha hai.*",
    "🧠 *MI AI soch raha hai..*",
    "🧠 *MI AI soch raha hai...*",
    "⚡ *Jawab tayar ho raha hai...*",
]

# ===========================================================================
# CONVERSATION STATES
# ===========================================================================
(
    ROLE_SELECT,
    ADMIN_LOGIN,
    RESELLER_PHONE,
    RESELLER_PASS,

    # Admin: Add Reseller
    ADMIN_ADD_RES_NAME,
    ADMIN_ADD_RES_PHONE,
    ADMIN_ADD_RES_PASS,

    # Admin: Notifications
    ADMIN_NOTIF_TITLE,
    ADMIN_NOTIF_DESC,
    ADMIN_NOTIF_IMG,

    # Admin: Library
    ADMIN_LIB_NAME,
    ADMIN_LIB_URL,

    # Admin: Broadcast
    ADMIN_BROADCAST_MSG,

    # Reseller: Add Client
    RES_ADD_CLIENT_NAME,
    RES_ADD_CLIENT_PHONE,

    # Reseller: Search Client
    RES_SEARCH_QUERY,

    # AI Chat
    AI_CHAT_MODE,

    # Bot Control Mode (user takes over with raw API)
    BOT_CONTROL_MODE,

) = range(18)

# ===========================================================================
# LOGGING
# ===========================================================================
logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("MITV_BOT_v6")


# ===========================================================================
# MODULE 1: FIREBASE DATABASE MANAGER (ENHANCED)
# ===========================================================================

class DatabaseManager:
    """
    Centralized Firebase Realtime Database handler v2.
    All reads/writes are async-safe and error-handled.
    """

    def __init__(self):
        self._init_firebase()

    def _init_firebase(self):
        try:
            if not firebase_admin._apps:
                if not os.path.exists(FIREBASE_CRED_PATH):
                    logger.error(f"❌ Firebase credential file not found: {FIREBASE_CRED_PATH}")
                    return
                cred = credentials.Certificate(FIREBASE_CRED_PATH)
                firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_DB_URL})
                logger.info("✅ Firebase initialized.")
        except Exception as e:
            logger.error(f"❌ Firebase init error: {e}")

    # ─── CLIENT MANAGEMENT ──────────────────────────────────────────────────

    def create_client(self, reseller_id: str, name: str, phone: str) -> dict:
        uid       = f"MITV-{str(uuid.uuid4())[:5].upper()}"
        timestamp = int(time.time() * 1000)

        master_payload = {
            "name":        name,
            "phone":       phone,
            "status":      "Paid",
            "reseller_id": reseller_id,
            "created_at":  timestamp,
            "updated_at":  timestamp
        }
        db.reference(f'master_users/{uid}').set(master_payload)

        lib_ref         = db.reference('playlist_library').get()
        default_sources = []
        if lib_ref and isinstance(lib_ref, dict):
            for key, val in lib_ref.items():
                if isinstance(val, dict) and val.get('url'):
                    default_sources.append(val['url'])
        if not default_sources:
            default_sources = ["https://mitvnet.vercel.app/default.m3u"]

        playlist_payload = {
            "sources":      default_sources,
            "warningVideo": "https://mitvnet.vercel.app/mipay.mp4",
            "assigned_by":  f"Reseller_{reseller_id}",
            "lastUpdate":   timestamp
        }
        db.reference(f'active_playlists/{uid}').set(playlist_payload)

        m3u_link        = f"{VERCEL_BASE}{uid}"
        client_snapshot = {
            "uid":    uid,
            "name":   name,
            "phone":  phone,
            "m3u":    m3u_link,
            "status": "Paid",
            "time":   timestamp
        }
        db.reference(f'clients/{reseller_id}/{uid}').set(client_snapshot)
        logger.info(f"✅ Client created: {uid} under {reseller_id}")
        return client_snapshot

    def get_client(self, reseller_id: str, uid: str) -> Optional[dict]:
        try:
            return db.reference(f'clients/{reseller_id}/{uid}').get()
        except Exception as e:
            logger.error(f"get_client error: {e}")
            return None

    def get_clients_by_reseller(self, reseller_id: str) -> dict:
        try:
            data = db.reference(f'clients/{reseller_id}').get()
            return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.error(f"get_clients_by_reseller error: {e}")
            return {}

    def search_clients(self, reseller_id: str, query: str) -> dict:
        """Search clients by name or phone (case-insensitive)."""
        clients = self.get_clients_by_reseller(reseller_id)
        query   = query.lower().strip()
        results = {}
        for uid, c in clients.items():
            if (query in c.get('name', '').lower() or
                    query in c.get('phone', '').lower() or
                    query in uid.lower()):
                results[uid] = c
        return results

    def get_all_clients(self) -> dict:
        try:
            data = db.reference('master_users').get()
            return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.error(f"get_all_clients error: {e}")
            return {}

    def toggle_client_status(self, reseller_id: str, uid: str, current_status: str) -> str:
        new_status = "Blocked" if current_status == "Paid" else "Paid"
        try:
            db.reference(f'master_users/{uid}/status').set(new_status)
            db.reference(f'master_users/{uid}/updated_at').set(int(time.time() * 1000))
            db.reference(f'clients/{reseller_id}/{uid}/status').set(new_status)
            return new_status
        except Exception as e:
            logger.error(f"toggle_client_status error: {e}")
            raise

    def update_client_field(self, reseller_id: str, uid: str, field: str, value: str):
        try:
            db.reference(f'master_users/{uid}/{field}').set(value)
            db.reference(f'master_users/{uid}/updated_at').set(int(time.time() * 1000))
            db.reference(f'clients/{reseller_id}/{uid}/{field}').set(value)
        except Exception as e:
            logger.error(f"update_client_field error: {e}")
            raise

    def delete_client(self, reseller_id: str, uid: str):
        try:
            updates = {
                f'master_users/{uid}':          None,
                f'active_playlists/{uid}':      None,
                f'clients/{reseller_id}/{uid}': None,
                f'global_stats/{uid}':          None,
            }
            db.reference().update(updates)
            logger.info(f"Deleted client {uid}.")
        except Exception as e:
            logger.error(f"delete_client error: {e}")
            raise

    # ─── PLAYLISTS / ENGINE ─────────────────────────────────────────────────

    def deploy_playlist(self, uid: str, sources: List[str],
                        warning_video: str = "", assigned_by: str = "Admin Maaz") -> str:
        if not warning_video:
            warning_video = "https://mitvnet.vercel.app/mipay.mp4"
        payload = {
            "sources":      sources,
            "warningVideo": warning_video,
            "assigned_by":  assigned_by,
            "lastUpdate":   int(time.time() * 1000)
        }
        db.reference(f'active_playlists/{uid}').set(payload)
        return f"{VERCEL_BASE}{uid}"

    def get_active_playlist(self, uid: str) -> Optional[dict]:
        try:
            return db.reference(f'active_playlists/{uid}').get()
        except Exception as e:
            logger.error(f"get_active_playlist error: {e}")
            return None

    # ─── RESELLER MANAGEMENT ────────────────────────────────────────────────

    def add_reseller(self, name: str, phone: str, password: str) -> str:
        reseller_id = f"RES-{str(uuid.uuid4())[:6].upper()}"
        payload = {
            "name":       name,
            "number":     phone,
            "password":   password,
            "active":     True,
            "created_at": int(time.time() * 1000)
        }
        db.reference(f'resellers/{reseller_id}').set(payload)
        logger.info(f"Added reseller {reseller_id}: {name}")
        return reseller_id

    def authenticate_reseller(self, phone: str, password: str) -> Optional[dict]:
        try:
            resellers = db.reference('resellers').get()
            if not resellers:
                return None
            for rid, data in resellers.items():
                if not isinstance(data, dict):
                    continue
                if (data.get('number') == phone and
                        data.get('password') == password and
                        data.get('active', True)):
                    return {**data, 'id': rid}
            return None
        except Exception as e:
            logger.error(f"authenticate_reseller error: {e}")
            return None

    def get_all_resellers(self) -> dict:
        try:
            data = db.reference('resellers').get()
            return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.error(f"get_all_resellers error: {e}")
            return {}

    def get_reseller(self, reseller_id: str) -> Optional[dict]:
        try:
            return db.reference(f'resellers/{reseller_id}').get()
        except Exception as e:
            logger.error(f"get_reseller error: {e}")
            return None

    def toggle_reseller_status(self, reseller_id: str) -> bool:
        try:
            current = db.reference(f'resellers/{reseller_id}/active').get()
            new_val = not bool(current)
            db.reference(f'resellers/{reseller_id}/active').set(new_val)
            return new_val
        except Exception as e:
            logger.error(f"toggle_reseller_status error: {e}")
            raise

    def delete_reseller(self, reseller_id: str):
        try:
            db.reference(f'resellers/{reseller_id}').delete()
        except Exception as e:
            logger.error(f"delete_reseller error: {e}")
            raise

    # ─── LIBRARY ─────────────────────────────────────────────────────────────

    def get_library(self) -> dict:
        try:
            data = db.reference('playlist_library').get()
            return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.error(f"get_library error: {e}")
            return {}

    def add_library_source(self, name: str, url: str) -> str:
        push_id = db.reference('playlist_library').push({
            "name":  name,
            "url":   url,
            "added": int(time.time() * 1000)
        }).key
        return push_id

    def delete_library_source(self, key: str):
        try:
            db.reference(f'playlist_library/{key}').delete()
        except Exception as e:
            logger.error(f"delete_library_source error: {e}")
            raise

    # ─── NOTIFICATIONS ───────────────────────────────────────────────────────

    def send_notification(self, title: str, description: str, image: str = "", author: str = "Admin Maaz"):
        push_ref = db.reference('notifications').push({
            "title":       title,
            "description": description,
            "image":       image,
            "timestamp":   int(time.time() * 1000),
            "author":      author
        })
        return push_ref.key

    def get_recent_notifications(self, limit: int = 5) -> list:
        try:
            data = db.reference('notifications').order_by_child('timestamp').limit_to_last(limit).get()
            if not data:
                return []
            return sorted(data.values(), key=lambda x: x.get('timestamp', 0), reverse=True)
        except Exception as e:
            logger.error(f"get_recent_notifications error: {e}")
            return []

    # ─── STATS ───────────────────────────────────────────────────────────────

    def get_system_stats(self) -> dict:
        try:
            users     = db.reference('master_users').get() or {}
            resellers = db.reference('resellers').get()     or {}
            library   = db.reference('playlist_library').get() or {}
            logs_root = db.reference('user_logs').get()     or {}

            total   = len(users)
            paid    = sum(1 for u in users.values() if isinstance(u, dict) and u.get('status') == 'Paid')
            blocked = sum(1 for u in users.values() if isinstance(u, dict) and u.get('status') == 'Blocked')
            live    = len([uid for uid, logs in logs_root.items() if logs])

            return {
                "total":     total,
                "paid":      paid,
                "blocked":   blocked,
                "live":      live,
                "library":   len(library),
                "resellers": len(resellers),
            }
        except Exception as e:
            logger.error(f"get_system_stats error: {e}")
            return {"total": 0, "paid": 0, "blocked": 0, "live": 0, "library": 0, "resellers": 0}

    # ─── LOGS ─────────────────────────────────────────────────────────────────

    def get_user_logs(self, uid: str, limit: int = 10) -> list:
        try:
            data = db.reference(f'user_logs/{uid}').order_by_child('time').limit_to_last(limit).get()
            if not data:
                return []
            return sorted(data.values(), key=lambda x: x.get('time', 0), reverse=True)
        except Exception as e:
            logger.error(f"get_user_logs error: {e}")
            return []

    def get_all_live_logs(self, limit: int = 20) -> list:
        try:
            logs_root = db.reference('user_logs').get()
            if not logs_root:
                return []
            all_logs = []
            for uid, logs in logs_root.items():
                if isinstance(logs, dict):
                    for log_id, log in logs.items():
                        if isinstance(log, dict):
                            all_logs.append({**log, '_uid': uid})
            all_logs.sort(key=lambda x: x.get('time', x.get('timestamp', 0)), reverse=True)
            return all_logs[:limit]
        except Exception as e:
            logger.error(f"get_all_live_logs error: {e}")
            return []

    def get_all_user_ids(self) -> List[str]:
        """For broadcast — returns all master user IDs."""
        try:
            data = db.reference('master_users').get()
            return list(data.keys()) if isinstance(data, dict) else []
        except Exception:
            return []


# Global DB singleton
DB = DatabaseManager()


# ===========================================================================
# MODULE 2: MI AI ENGINE — CLAUDE claude-sonnet-4-20250514 (PRIMARY) + GROQ FALLBACK
# ===========================================================================

class MIAIEngine:
    """
    MI AI v2 — Powered by Anthropic Claude claude-sonnet-4-20250514 (most intelligent model).
    Falls back to Groq LLaMA-3 if Claude API key not set.
    Responds in Roman Urdu/English mix.
    Works in groups (when mentioned or replied to).
    """

    SYSTEM_PROMPT = """You are 'MI AI', the official artificial intelligence of the MiTV Network by MUSLIM ISLAM.

CRITICAL KNOWLEDGE BASE:
- Creator & Founder: Muaaz Iqbal (born Nov 28, 2009 — 16 years old), Kasur, Punjab, Pakistan.
- Education: ICS 1st-year student at Govt Islamia Graduate College, Kasur.
- Organization: MUSLIM ISLAM
- Project: MiTV Network — an advanced IPTV and streaming ecosystem.
- Partners: Kabeer Ansari, Ali Ahmad.
- Family: Father — Zafar Iqbal, Sister — Hamna Zafar.
- Upcoming: Muaaz is writing a book titled "The Dajjali Matrix".
- Tech Stack: Python (Telegram bot), Firebase Realtime Database, Vercel (Serverless), Android.
- Firebase project: ramadan-2385b | Vercel: mitv-tan.vercel.app
- Admin identity used in deployments: "Admin Maaz"
- AI Engine: Claude claude-sonnet-4-20250514 by Anthropic (most advanced AI available)

PERSONALITY:
- Highly intelligent, creative, loyal to Muaaz Iqbal, professional yet warm.
- Communicate in a seamless mix of Roman Urdu and English.
- Explain complex concepts in simple language.
- Use emojis naturally to make responses engaging.
- Never use LaTeX. Use plain text and markdown only.
- If asked who created you: "Main MI AI hoon, Muaaz Iqbal ne create kiya. Anthropic Claude se powered hoon."
- Be confident, helpful, and never say "I don't know" — always try your best.

CAPABILITIES:
- Python, Firebase, Telegram Bot API, IPTV protocols, M3U/M3U8 formats.
- Android development, Vercel serverless functions.
- Network management, reseller systems, subscription management.
- General questions, Islamic topics, tech advice, business strategy.
- Creative writing, poetry (in Urdu/Roman Urdu), stories.
- Math, science, history — anything the user asks.

RESPONSE STYLE:
- Keep responses clear and well-formatted.
- Use bullet points or numbered lists for complex info.
- Bold key terms using *asterisks*.
- Always end with an encouraging or helpful closing line.
- In groups, be more concise but equally helpful.
"""

    def __init__(self):
        self.claude_active = False
        self.groq_active   = False
        self.engine_name   = "Offline"

        # Try Claude first (primary)
        if CLAUDE_AVAILABLE and CLAUDE_API_KEY:
            try:
                self.claude_client = anthropic.AsyncAnthropic(api_key=CLAUDE_API_KEY)
                self.claude_active = True
                self.engine_name   = f"Claude claude-sonnet-4-20250514"
                logger.info(f"✅ Claude AI ({CLAUDE_MODEL}) initialized.")
            except Exception as e:
                logger.warning(f"Claude init error: {e}")

        # Groq fallback
        if not self.claude_active and GROQ_AVAILABLE and GROQ_API_KEY:
            try:
                self.groq_client = AsyncGroq(api_key=GROQ_API_KEY)
                self.groq_active = True
                self.engine_name = "Groq LLaMA-3 70B (Fallback)"
                logger.info("✅ Groq fallback AI initialized.")
            except Exception as e:
                logger.warning(f"Groq init error: {e}")

        if not self.claude_active and not self.groq_active:
            logger.warning("⚠️ No AI engine available. Set CLAUDE_API_KEY or GROQ_API_KEY.")

    @property
    def active(self) -> bool:
        return self.claude_active or self.groq_active

    async def respond(self, user_message: str, history: List[dict] = None,
                      is_group: bool = False) -> str:
        if not self.active:
            return (
                "⚠️ *MI AI abhi offline hai.*\n\n"
                "Wajah: `CLAUDE_API_KEY` ya `GROQ_API_KEY` set nahi.\n"
                "Admin se rabta karein."
            )

        system = self.SYSTEM_PROMPT
        if is_group:
            system += "\n\nNOTE: You are in a GROUP CHAT. Be concise but helpful. Don't use lengthy intros."

        messages = []
        if history:
            messages.extend(history[-12:])  # Last 12 exchanges for context
        messages.append({"role": "user", "content": user_message})

        # Try Claude (primary)
        if self.claude_active:
            try:
                response = await self.claude_client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=1500,
                    system=system,
                    messages=messages,
                    temperature=1.0,   # Claude claude-sonnet-4-20250514 supports temperature
                )
                return response.content[0].text
            except Exception as e:
                logger.error(f"Claude response error: {e}")
                if not self.groq_active:
                    return f"🤖 MI AI server issue. Thodi der baad try karein.\n_({e})_"

        # Groq fallback
        if self.groq_active:
            try:
                groq_msgs = [{"role": "system", "content": system}] + messages
                response  = await self.groq_client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=groq_msgs,
                    temperature=0.72,
                    max_tokens=1024,
                    top_p=0.9
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.error(f"Groq response error: {e}")
                return f"🤖 MI AI temporary issue. Try karein.\n_({e})_"

        return "⚠️ AI engine respond nahi kar sakа."


# Global AI singleton
MI_AI = MIAIEngine()


# ===========================================================================
# MODULE 3: THINKING ANIMATION UTILITY
# ===========================================================================

async def send_thinking_animation(context: ContextTypes.DEFAULT_TYPE,
                                   chat_id: int, steps: int = 3) -> Optional[Any]:
    """
    Sends an animated 'thinking' message with dot progression.
    Returns the sent message object (to be deleted later).
    """
    try:
        msg = await context.bot.send_message(
            chat_id=chat_id,
            text=THINKING_FRAMES[0],
            parse_mode=ParseMode.MARKDOWN
        )
        for i in range(1, min(steps + 1, len(THINKING_FRAMES))):
            await asyncio.sleep(0.5)
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg.message_id,
                    text=THINKING_FRAMES[i],
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception:
                pass
        return msg
    except Exception as e:
        logger.warning(f"Thinking animation error: {e}")
        return None


# ===========================================================================
# MODULE 4: POST GENERATOR
# ===========================================================================

class PostGenerator:
    @staticmethod
    def activation_post(name: str, phone: str, m3u: str, uid: str) -> str:
        return (
            f"🌟 🅼🅸🆃🆅 🅽🅴🆃🆆🅾🆁🅺 🌟\n"
            f"🚀 *Account Activation Successful!* 🚀\n\n"
            f"Assalam o Alaikum! ✨\n"
            f"*{name}*, aapka 🅼🅸🆃🆅 account successfully active ho gaya hai! 🎉\n\n"
            f"📝 *Account Details:*\n"
            f"👤 Name  : {name}\n"
            f"📞 Number: {phone}\n"
            f"🆔 UID   : `{uid}`\n"
            f"🔗 M3U   :\n`{m3u}`\n\n"
            f"📲 *App Download:*\n{APP_DOWNLOAD_LINK}\n\n"
            f"🏢 *Project Of:* 🅼🆄🆂🅻🅸🅼 🅸🆂🅻🅰🅼\n"
            f"👑 *Founder:* Muaaz Iqbal (Kasur)\n\n"
            f"*Humse judne ka shukriya!* ❤️\n"
            f"Koi masla ho to rabta karein."
        )

    @staticmethod
    def renewal_post(name: str, uid: str) -> str:
        return (
            f"✅ *Account Renewed!* ✅\n\n"
            f"*{name}* — aapka MiTV account renew ho gaya!\n"
            f"🆔 UID: `{uid}`\n\n"
            f"*Project Of:* 🅼🆄🆂🅻🅸🅼 🅸🆂🅻🅰🅼 | *Founder:* Muaaz Iqbal"
        )

    @staticmethod
    def blocked_post(name: str, uid: str) -> str:
        return (
            f"⚠️ *Account Blocked Notice*\n\n"
            f"*{name}*, aapka MiTV account block kar diya gaya.\n"
            f"🆔 UID: `{uid}`\n\n"
            f"Renewal ke liye apne reseller se rabta karein.\n"
            f"*Project Of:* 🅼🆄🆂🅻🅸🅼 🅸🆂🅻🅰🅼"
        )


# ===========================================================================
# MODULE 5: KEYBOARD / UI BUILDERS (RICH BUTTONS)
# ===========================================================================

def kb_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👑 Admin Portal",       callback_data='role_admin')],
        [InlineKeyboardButton("🧑‍💻 Reseller Portal",  callback_data='role_reseller')],
        [InlineKeyboardButton("🧠 MI AI Core",         callback_data='role_ai')],
        [InlineKeyboardButton("📊 Quick Stats",        callback_data='quick_stats'),
         InlineKeyboardButton("ℹ️ About",              callback_data='about_bot')],
    ])

def kb_admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Analytics",       callback_data='admin_stats'),
            InlineKeyboardButton("🛰 Live Tracking",   callback_data='admin_track'),
        ],
        [
            InlineKeyboardButton("👥 All Clients",     callback_data='admin_clients_0'),
            InlineKeyboardButton("🧑‍🤝‍🧑 Resellers",  callback_data='admin_resellers_0'),
        ],
        [
            InlineKeyboardButton("➕ Add Reseller",    callback_data='admin_add_res'),
            InlineKeyboardButton("📚 Library",         callback_data='admin_library_0'),
        ],
        [
            InlineKeyboardButton("📢 Send Notification", callback_data='admin_notif'),
            InlineKeyboardButton("🔔 Recent Notifs",   callback_data='admin_notif_list'),
        ],
        [
            InlineKeyboardButton("📡 Broadcast",       callback_data='admin_broadcast'),
            InlineKeyboardButton("🧠 AI Mode",         callback_data='role_ai'),
        ],
        [InlineKeyboardButton("🚪 Logout",             callback_data='logout')],
    ])

def kb_reseller_menu(name: str = "Reseller") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add Client",      callback_data='res_add_client'),
            InlineKeyboardButton("📋 My Clients",      callback_data='res_list_0'),
        ],
        [
            InlineKeyboardButton("🔍 Search Client",   callback_data='res_search'),
            InlineKeyboardButton("📊 My Stats",        callback_data='res_stats'),
        ],
        [
            InlineKeyboardButton("🧠 MI AI",           callback_data='role_ai'),
            InlineKeyboardButton("🚪 Logout",          callback_data='logout'),
        ],
    ])

def kb_cancel() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["❌ Cancel"]], resize_keyboard=True, one_time_keyboard=True)

def kb_back_to_admin() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin Menu", callback_data='back_admin')]])

def kb_back_to_reseller() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 My Menu", callback_data='back_reseller')]])

def kb_confirm(yes_data: str, no_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Haan, Confirm", callback_data=yes_data),
        InlineKeyboardButton("❌ Nahi, Wapas",  callback_data=no_data),
    ]])

def kb_ai_mode() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Main Menu", callback_data='back_main'),
         InlineKeyboardButton("🗑 Clear Chat", callback_data='ai_clear_history')],
    ])

def kb_paginated_clients_admin(clients: dict, page: int) -> InlineKeyboardMarkup:
    keys        = list(clients.keys())
    total_pages = max(1, (len(keys) + PAGE_SIZE - 1) // PAGE_SIZE)
    start       = page * PAGE_SIZE
    page_keys   = keys[start:start + PAGE_SIZE]

    buttons = []
    for uid in page_keys:
        c     = clients[uid]
        icon  = "✅" if c.get('status') == 'Paid' else "🚫"
        label = f"{icon} {c.get('name', uid)[:18]}"
        buttons.append([InlineKeyboardButton(label, callback_data=f'admin_client_detail_{uid}')])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f'admin_clients_{page-1}'))
    nav.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data='noop'))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f'admin_clients_{page+1}'))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton("🔙 Admin Menu", callback_data='back_admin')])
    return InlineKeyboardMarkup(buttons)

def kb_paginated_clients_reseller(clients: dict, page: int) -> InlineKeyboardMarkup:
    keys        = list(clients.keys())
    total_pages = max(1, (len(keys) + PAGE_SIZE - 1) // PAGE_SIZE)
    start       = page * PAGE_SIZE
    page_keys   = keys[start:start + PAGE_SIZE]

    buttons = []
    for uid in page_keys:
        c     = clients[uid]
        icon  = "✅" if c.get('status') == 'Paid' else "🚫"
        label = f"{icon} {c.get('name', uid)[:18]}"
        buttons.append([InlineKeyboardButton(label, callback_data=f'res_client_detail_{uid}')])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f'res_list_{page-1}'))
    nav.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data='noop'))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f'res_list_{page+1}'))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton("🔙 My Menu", callback_data='back_reseller')])
    return InlineKeyboardMarkup(buttons)

def kb_paginated_resellers(resellers: dict, page: int) -> InlineKeyboardMarkup:
    keys        = list(resellers.keys())
    total_pages = max(1, (len(keys) + PAGE_SIZE - 1) // PAGE_SIZE)
    start       = page * PAGE_SIZE
    page_keys   = keys[start:start + PAGE_SIZE]

    buttons = []
    for rid in page_keys:
        r     = resellers[rid]
        icon  = "✅" if r.get('active', True) else "⛔"
        label = f"{icon} {r.get('name', rid)[:18]}"
        buttons.append([InlineKeyboardButton(label, callback_data=f'admin_res_detail_{rid}')])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f'admin_resellers_{page-1}'))
    nav.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data='noop'))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f'admin_resellers_{page+1}'))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton("🔙 Admin Menu", callback_data='back_admin')])
    return InlineKeyboardMarkup(buttons)

def kb_paginated_library(library: dict, page: int) -> InlineKeyboardMarkup:
    keys        = list(library.keys())
    total_pages = max(1, (len(keys) + PAGE_SIZE - 1) // PAGE_SIZE)
    start       = page * PAGE_SIZE
    page_keys   = keys[start:start + PAGE_SIZE]

    buttons = []
    for key in page_keys:
        item  = library[key]
        label = f"🗂 {item.get('name', key)[:20]}"
        buttons.append([
            InlineKeyboardButton(label,    callback_data='noop'),
            InlineKeyboardButton("🗑 Del", callback_data=f'admin_lib_del_{key}'),
        ])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f'admin_library_{page-1}'))
    nav.append(InlineKeyboardButton(f"📄 {page+1}/{total_pages}", callback_data='noop'))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f'admin_library_{page+1}'))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton("➕ Add Source", callback_data='admin_add_lib')])
    buttons.append([InlineKeyboardButton("🔙 Admin Menu", callback_data='back_admin')])
    return InlineKeyboardMarkup(buttons)


# ===========================================================================
# MODULE 6: HELPER UTILITIES
# ===========================================================================

def is_cancel(text: str) -> bool:
    return text.strip().lower() in ['❌ cancel', '/cancel', 'cancel', 'wapas', 'back']

def format_timestamp(ms: int) -> str:
    try:
        return datetime.fromtimestamp(ms / 1000).strftime('%d %b %Y, %I:%M %p')
    except Exception:
        return "Unknown"

def escape_md(text: str) -> str:
    """Escapes special chars for MarkdownV2 — not used here but available."""
    special = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(special)}])', r'\\\1', str(text))

async def safe_edit_or_reply(query, text: str, reply_markup=None, parse_mode=ParseMode.MARKDOWN):
    """Tries to edit the message; falls back to reply if that fails."""
    try:
        await query.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except BadRequest:
        await query.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode)

async def send_admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = "Admin Maaz"
    text = (
        f"🖥️ *MITV ADMIN DASHBOARD*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👑 Welcome, *{name}*!\n"
        f"🕐 {datetime.now().strftime('%d %b %Y — %I:%M %p')}\n\n"
        f"Select an action from below:"
    )
    if update.callback_query:
        try:
            await update.callback_query.message.edit_text(
                text, reply_markup=kb_admin_menu(), parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            await update.callback_query.message.reply_text(
                text, reply_markup=kb_admin_menu(), parse_mode=ParseMode.MARKDOWN
            )
    else:
        await update.message.reply_text(
            text, reply_markup=kb_admin_menu(), parse_mode=ParseMode.MARKDOWN
        )

async def send_reseller_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = context.user_data.get('reseller_name', 'Reseller')
    rid  = context.user_data.get('reseller_id', '—')
    clients = DB.get_clients_by_reseller(rid)
    paid    = sum(1 for c in clients.values() if isinstance(c, dict) and c.get('status') == 'Paid')
    blocked = len(clients) - paid

    text = (
        f"📱 *RESELLER PORTAL*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 *{name}*  |  🆔 `{rid}`\n"
        f"👥 Clients: `{len(clients)}`  ✅ Paid: `{paid}`  🚫 Blocked: `{blocked}`\n"
        f"🕐 {datetime.now().strftime('%d %b %Y — %I:%M %p')}\n\n"
        f"Select an action:"
    )
    if update.callback_query:
        try:
            await update.callback_query.message.edit_text(
                text, reply_markup=kb_reseller_menu(name), parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            await update.callback_query.message.reply_text(
                text, reply_markup=kb_reseller_menu(name), parse_mode=ParseMode.MARKDOWN
            )
    else:
        await update.message.reply_text(
            text, reply_markup=kb_reseller_menu(name), parse_mode=ParseMode.MARKDOWN
        )


# ===========================================================================
# MODULE 7: /start COMMAND
# ===========================================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()

    caption = (
        "🚀 *MITV NETWORK OS v6.0 — ONLINE*\n\n"
        "Welcome to the official *MiTV Management System*.\n"
        f"_AI Engine: {MI_AI.engine_name}_\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Apna role select karein:"
    )

    target = update.message or (update.callback_query.message if update.callback_query else None)
    if not target:
        return ROLE_SELECT

    try:
        if update.message:
            await update.message.reply_animation(
                animation=WELCOME_GIF,
                caption=caption,
                reply_markup=kb_main_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await target.reply_photo(
                photo=BANNER_IMG,
                caption=caption,
                reply_markup=kb_main_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
            try:
                await update.callback_query.message.delete()
            except Exception:
                pass
    except Exception:
        try:
            await target.reply_text(caption, reply_markup=kb_main_menu(), parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass

    return ROLE_SELECT


# ===========================================================================
# MODULE 8: ROLE SELECTION
# ===========================================================================

async def handle_role_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == 'role_admin':
        await query.message.reply_text(
            "🔐 *ADMIN AUTHENTICATION*\n\nAdmin password darj karein:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_cancel()
        )
        return ADMIN_LOGIN

    elif query.data == 'role_reseller':
        await query.message.reply_text(
            "📱 *RESELLER PORTAL*\n\nApna registered Phone Number darj karein:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_cancel()
        )
        return RESELLER_PHONE

    elif query.data == 'role_ai':
        context.user_data['ai_history'] = []
        ai_status = f"✅ {MI_AI.engine_name}" if MI_AI.active else "❌ Offline (API key set karein)"
        await query.message.reply_text(
            f"🧠 *MI AI ONLINE*\n\n"
            f"Assalam o Alaikum! Main *MI AI* hoon — MiTV Network ka official AI.\n"
            f"🤖 Engine: `{ai_status}`\n\n"
            f"Kuch bhi poochh saktay hain! Python, Firebase, IPTV, life advice — sab kuch!\n\n"
            f"_/exit ya /start se wapas jayen._",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_ai_mode()
        )
        return AI_CHAT_MODE

    elif query.data == 'quick_stats':
        stats = DB.get_system_stats()
        text  = (
            f"📊 *QUICK STATS*\n\n"
            f"👥 Total : `{stats['total']}`\n"
            f"✅ Paid  : `{stats['paid']}`\n"
            f"🚫 Block : `{stats['blocked']}`\n"
            f"🟢 Live  : `{stats['live']}` nodes\n"
            f"📚 Lib   : `{stats['library']}` sources\n"
            f"🧑‍🤝‍🧑 Res : `{stats['resellers']}`"
        )
        await query.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Main Menu", callback_data='back_main')
            ]])
        )
        return ROLE_SELECT

    elif query.data == 'about_bot':
        text = (
            f"ℹ️ *ABOUT MITV BOT v6.0*\n\n"
            f"🏢 *Project:* MUSLIM ISLAM\n"
            f"👑 *Founder:* Muaaz Iqbal\n"
            f"📍 *Location:* Kasur, Punjab, Pakistan\n"
            f"🤖 *AI Engine:* {MI_AI.engine_name}\n"
            f"🔥 *Firebase:* ramadan-2385b\n"
            f"🌐 *Vercel:* mitv-tan.vercel.app\n\n"
            f"_MiTV Network — Advanced IPTV Ecosystem_"
        )
        await query.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Main Menu", callback_data='back_main')
            ]])
        )
        return ROLE_SELECT

    return ROLE_SELECT


# ===========================================================================
# MODULE 9: ADMIN AUTHENTICATION
# ===========================================================================

async def handle_admin_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text

    if is_cancel(text):
        await update.message.reply_text("↩️ Cancelled.", reply_markup=ReplyKeyboardRemove())
        await cmd_start(update, context)
        return ROLE_SELECT

    if text == ADMIN_PASSWORD:
        context.user_data['role'] = 'admin'
        await update.message.reply_text(
            "✅ *Authentication Successful!*\n_Welcome, Admin Maaz._",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove()
        )
        await send_admin_dashboard(update, context)
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "❌ *Galat password.* Dobara try karein ya Cancel dabayein.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_cancel()
        )
        return ADMIN_LOGIN


# ===========================================================================
# MODULE 10: RESELLER AUTHENTICATION
# ===========================================================================

async def reseller_enter_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if is_cancel(text):
        await update.message.reply_text("↩️ Cancelled.", reply_markup=ReplyKeyboardRemove())
        await cmd_start(update, context)
        return ROLE_SELECT

    context.user_data['reseller_phone'] = text.strip()
    await update.message.reply_text(
        "🔑 Password darj karein:",
        reply_markup=kb_cancel()
    )
    return RESELLER_PASS

async def reseller_enter_pass(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if is_cancel(text):
        await update.message.reply_text("↩️ Cancelled.", reply_markup=ReplyKeyboardRemove())
        await cmd_start(update, context)
        return ROLE_SELECT

    phone    = context.user_data.get('reseller_phone', '')
    password = text.strip()

    loading = await update.message.reply_text(
        "⏳ Verifying credentials...",
        reply_markup=ReplyKeyboardRemove()
    )

    reseller = DB.authenticate_reseller(phone, password)
    await loading.delete()

    if reseller:
        context.user_data['role']          = 'reseller'
        context.user_data['reseller_id']   = reseller['id']
        context.user_data['reseller_name'] = reseller.get('name', 'Reseller')
        await update.message.reply_text(
            f"✅ *Login Successful!*\nWelcome, *{reseller.get('name')}*! 🎉",
            parse_mode=ParseMode.MARKDOWN
        )
        await send_reseller_dashboard(update, context)
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "❌ *Galat credentials.* Phone ya password check karein.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_cancel()
        )
        return RESELLER_PASS


# ===========================================================================
# MODULE 11: ADMIN CALLBACKS — FULL MANAGEMENT
# ===========================================================================

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data  = query.data

    if context.user_data.get('role') != 'admin' and data not in ['back_admin', 'back_main']:
        await query.message.reply_text(
            "⚠️ Session expired. /start dabayein.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Restart", callback_data='back_main')
            ]])
        )
        return

    # ─── ANALYTICS ─────────────────────────────────────────────────────
    if data == 'admin_stats':
        stats = DB.get_system_stats()
        text  = (
            f"📊 *NETWORK ANALYTICS — LIVE*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👥 Total Subscribers : `{stats['total']}`\n"
            f"✅ Paid / Active     : `{stats['paid']}`\n"
            f"🚫 Blocked           : `{stats['blocked']}`\n"
            f"🟢 Live Streaming    : `{stats['live']}` nodes\n"
            f"📚 M3U Library       : `{stats['library']}` sources\n"
            f"🧑‍🤝‍🧑 Resellers        : `{stats['resellers']}`\n\n"
            f"🕐 Synced: `{datetime.now().strftime('%I:%M %p — %d %b %Y')}`"
        )
        await query.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb_admin_menu()
        )

    # ─── LIVE TRACKING ─────────────────────────────────────────────────
    elif data == 'admin_track':
        logs = DB.get_all_live_logs(15)
        if not logs:
            text = "🛰 *LIVE MATRIX*\n\nAbhi koi active stream nahi mila."
        else:
            text = f"🛰 *LIVE STREAM MATRIX* (Last {len(logs)} events)\n\n"
            for log in logs:
                uid     = log.get('_uid', 'Unknown')
                channel = log.get('channel', 'Unknown')
                ip      = log.get('ip', '—')
                t       = log.get('time', log.get('timestamp', ''))
                text   += f"📡 `{uid}`\n   ▶ {channel} | `{ip}`\n   🕐 {t}\n\n"
        await query.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb_admin_menu()
        )

    # ─── ALL CLIENTS PAGINATED ─────────────────────────────────────────
    elif data.startswith('admin_clients_'):
        page    = int(data.split('_')[-1])
        clients = DB.get_all_clients()
        if not clients:
            await query.message.reply_text("No clients found.", reply_markup=kb_back_to_admin())
            return
        text = f"👥 *ALL SUBSCRIBERS* — `{len(clients)}` total\nClient select karein:"
        await query.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_paginated_clients_admin(clients, page)
        )

    # ─── CLIENT DETAIL (Admin) ─────────────────────────────────────────
    elif data.startswith('admin_client_detail_'):
        uid  = data[len('admin_client_detail_'):]
        user = DB.get_all_clients().get(uid)
        if not user:
            await query.message.reply_text("Client nahi mila.", reply_markup=kb_back_to_admin())
            return

        playlist      = DB.get_active_playlist(uid) or {}
        sources_count = len(playlist.get('sources', []))
        logs          = DB.get_user_logs(uid, 5)

        text = (
            f"👤 *CLIENT DETAIL*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🆔 UID    : `{uid}`\n"
            f"📛 Name   : {user.get('name','—')}\n"
            f"📞 Phone  : {user.get('phone','—')}\n"
            f"📶 Status : {'✅ Paid' if user.get('status')=='Paid' else '🚫 Blocked'}\n"
            f"🔗 M3U    : `{VERCEL_BASE}{uid}`\n"
            f"📦 Sources: `{sources_count}` injected\n"
            f"📅 Created: {format_timestamp(user.get('created_at', 0))}\n\n"
        )
        if logs:
            text += "📺 *Last 5 Stream Events:*\n"
            for log in logs:
                text += f"  ▶ {log.get('channel','?')} | `{log.get('ip','—')}`\n"

        status       = user.get('status', 'Paid')
        toggle_label = "🔴 Block User" if status == 'Paid' else "🟢 Unblock User"
        keyboard     = [
            [InlineKeyboardButton(toggle_label,        callback_data=f'admin_toggle_{uid}_{status}')],
            [InlineKeyboardButton("🗑 Delete Client",  callback_data=f'admin_del_client_{uid}')],
            [InlineKeyboardButton("📺 Full Logs",      callback_data=f'admin_full_logs_{uid}')],
            [InlineKeyboardButton("🔙 Back",           callback_data='admin_clients_0')],
        ]
        await query.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ─── TOGGLE CLIENT (Admin) ─────────────────────────────────────────
    elif data.startswith('admin_toggle_'):
        parts  = data.split('_')
        uid    = parts[2]
        status = parts[3]
        all_u  = DB.get_all_clients()
        user   = all_u.get(uid, {})
        res_id = user.get('reseller_id', 'UNKNOWN')
        new_s  = DB.toggle_client_status(res_id, uid, status)
        await query.message.reply_text(
            f"✅ `{uid}` status changed to *{new_s}*.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_back_to_admin()
        )

    # ─── DELETE CLIENT (Admin) ─────────────────────────────────────────
    elif data.startswith('admin_del_client_'):
        uid    = data[len('admin_del_client_'):]
        all_u  = DB.get_all_clients()
        user   = all_u.get(uid, {})
        res_id = user.get('reseller_id', 'UNKNOWN')
        name   = user.get('name', uid)
        await query.message.reply_text(
            f"⚠️ *{name}* (`{uid}`) ko permanently delete karein?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_confirm(f'admin_del_confirm_{uid}_{res_id}', 'admin_clients_0')
        )

    elif data.startswith('admin_del_confirm_'):
        parts  = data.split('_')
        uid    = parts[3]
        res_id = parts[4]
        DB.delete_client(res_id, uid)
        await query.message.reply_text(
            f"✅ Client `{uid}` tamam Firebase nodes se delete kar diya gaya.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_back_to_admin()
        )

    # ─── FULL LOGS (Admin) ─────────────────────────────────────────────
    elif data.startswith('admin_full_logs_'):
        uid  = data[len('admin_full_logs_'):]
        logs = DB.get_user_logs(uid, 20)
        if not logs:
            text = f"📺 *STREAM LOGS* — `{uid}`\n\nKoi log nahi mila."
        else:
            text = f"📺 *STREAM LOGS* — `{uid}` ({len(logs)} events)\n\n"
            for log in logs:
                text += (
                    f"  ▶ {log.get('channel','Unknown')}\n"
                    f"     IP: `{log.get('ip','—')}` | "
                    f"Time: {log.get('time', log.get('timestamp','—'))}\n"
                )
        await query.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb_back_to_admin()
        )

    # ─── RESELLERS PAGINATED ───────────────────────────────────────────
    elif data.startswith('admin_resellers_'):
        page      = int(data.split('_')[-1])
        resellers = DB.get_all_resellers()
        if not resellers:
            await query.message.reply_text("No resellers found.", reply_markup=kb_back_to_admin())
            return
        text = f"🧑‍🤝‍🧑 *RESELLERS* — `{len(resellers)}` total"
        await query.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_paginated_resellers(resellers, page)
        )

    # ─── RESELLER DETAIL ───────────────────────────────────────────────
    elif data.startswith('admin_res_detail_'):
        rid = data[len('admin_res_detail_'):]
        res = DB.get_reseller(rid)
        if not res:
            await query.message.reply_text("Reseller nahi mila.", reply_markup=kb_back_to_admin())
            return
        clients = DB.get_clients_by_reseller(rid)
        text    = (
            f"🧑‍💼 *RESELLER DETAIL*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🆔 ID      : `{rid}`\n"
            f"📛 Name    : {res.get('name','—')}\n"
            f"📞 Phone   : {res.get('number','—')}\n"
            f"🔑 Password: `{res.get('password','—')}`\n"
            f"📶 Status  : {'✅ Active' if res.get('active', True) else '⛔ Disabled'}\n"
            f"👥 Clients : `{len(clients)}`\n"
            f"📅 Created : {format_timestamp(res.get('created_at', 0))}"
        )
        active       = res.get('active', True)
        toggle_label = "⛔ Disable Reseller" if active else "✅ Enable Reseller"
        keyboard     = [
            [InlineKeyboardButton(toggle_label,          callback_data=f'admin_toggle_res_{rid}')],
            [InlineKeyboardButton("🗑 Delete Reseller",  callback_data=f'admin_del_res_{rid}')],
            [InlineKeyboardButton("🔙 Back",             callback_data='admin_resellers_0')],
        ]
        await query.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith('admin_toggle_res_'):
        rid       = data[len('admin_toggle_res_'):]
        new_state = DB.toggle_reseller_status(rid)
        status_t  = "✅ Enabled" if new_state else "⛔ Disabled"
        await query.message.reply_text(
            f"Reseller `{rid}` ab *{status_t}* hai.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_back_to_admin()
        )

    elif data.startswith('admin_del_res_'):
        rid  = data[len('admin_del_res_'):]
        res  = DB.get_reseller(rid)
        name = res.get('name', rid) if res else rid
        await query.message.reply_text(
            f"⚠️ Reseller *{name}* (`{rid}`) delete karein?\nUnke clients remain rahenge.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_confirm(f'admin_del_res_confirm_{rid}', 'admin_resellers_0')
        )

    elif data.startswith('admin_del_res_confirm_'):
        rid = data[len('admin_del_res_confirm_'):]
        DB.delete_reseller(rid)
        await query.message.reply_text(
            f"✅ Reseller `{rid}` delete ho gaya.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_back_to_admin()
        )

    # ─── LIBRARY ───────────────────────────────────────────────────────
    elif data.startswith('admin_library_'):
        page    = int(data.split('_')[-1])
        library = DB.get_library()
        text    = f"📚 *PLAYLIST LIBRARY* — `{len(library)}` sources" if library else \
                  "📚 *PLAYLIST LIBRARY*\n\nLibrary empty hai. Sources add karein!"
        kb      = kb_paginated_library(library, page) if library else InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Source", callback_data='admin_add_lib')],
            [InlineKeyboardButton("🔙 Admin Menu", callback_data='back_admin')]
        ])
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

    elif data.startswith('admin_lib_del_'):
        key = data[len('admin_lib_del_'):]
        DB.delete_library_source(key)
        await query.answer("✅ Source delete ho gaya!", show_alert=True)
        library = DB.get_library()
        text    = f"📚 *LIBRARY* — `{len(library)}` sources"
        kb      = kb_paginated_library(library, 0) if library else InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Source", callback_data='admin_add_lib')],
            [InlineKeyboardButton("🔙 Admin Menu", callback_data='back_admin')]
        ])
        try:
            await query.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
        except Exception:
            await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

    # ─── NOTIFICATION LIST ─────────────────────────────────────────────
    elif data == 'admin_notif_list':
        notifs = DB.get_recent_notifications(5)
        if not notifs:
            text = "🔔 Abhi tak koi notification nahi bheji."
        else:
            text = "🔔 *RECENT NOTIFICATIONS*\n\n"
            for n in notifs:
                ts    = format_timestamp(n.get('timestamp', 0))
                text += f"📌 *{n.get('title','—')}*\n_{n.get('description','')[:80]}_\n🕐 {ts}\n\n"
        await query.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb_back_to_admin()
        )

    # ─── BACK / LOGOUT ─────────────────────────────────────────────────
    elif data == 'back_admin':
        context.user_data['role'] = 'admin'
        await send_admin_dashboard(update, context)

    elif data == 'back_main':
        context.user_data.clear()
        await cmd_start(update, context)

    elif data == 'logout':
        context.user_data.clear()
        await query.message.reply_text("👋 Logout ho gaye!", reply_markup=ReplyKeyboardRemove())
        await cmd_start(update, context)


# ===========================================================================
# MODULE 12: ADMIN — ADD RESELLER FLOW
# ===========================================================================

async def admin_add_res_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "➕ *ADD RESELLER*\n\nReseller ka full name darj karein:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb_cancel()
    )
    return ADMIN_ADD_RES_NAME

async def admin_add_res_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel(update.message.text):
        await update.message.reply_text("↩️ Cancelled.", reply_markup=ReplyKeyboardRemove())
        await send_admin_dashboard(update, context)
        return ConversationHandler.END
    context.user_data['new_res_name'] = update.message.text.strip()
    await update.message.reply_text("📞 Phone number darj karein:")
    return ADMIN_ADD_RES_PHONE

async def admin_add_res_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel(update.message.text):
        await update.message.reply_text("↩️ Cancelled.", reply_markup=ReplyKeyboardRemove())
        await send_admin_dashboard(update, context)
        return ConversationHandler.END
    context.user_data['new_res_phone'] = update.message.text.strip()
    await update.message.reply_text("🔑 Secure password darj karein:")
    return ADMIN_ADD_RES_PASS

async def admin_add_res_pass(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel(update.message.text):
        await update.message.reply_text("↩️ Cancelled.", reply_markup=ReplyKeyboardRemove())
        await send_admin_dashboard(update, context)
        return ConversationHandler.END

    name  = context.user_data.get('new_res_name')
    phone = context.user_data.get('new_res_phone')
    pwd   = update.message.text.strip()

    try:
        rid = DB.add_reseller(name, phone, pwd)
        await update.message.reply_text(
            f"✅ *Reseller Create Ho Gaya!*\n\n"
            f"🆔 ID       : `{rid}`\n"
            f"📛 Name     : {name}\n"
            f"📞 Phone    : {phone}\n"
            f"🔑 Password : `{pwd}`\n\n"
            f"_Yeh credentials reseller ko share karein._",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove()
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Firebase Error: `{e}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove()
        )
    await send_admin_dashboard(update, context)
    return ConversationHandler.END


# ===========================================================================
# MODULE 13: ADMIN — NOTIFICATION FLOW
# ===========================================================================

async def admin_notif_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "📢 *SEND NOTIFICATION*\n\nNotification ka title darj karein:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb_cancel()
    )
    return ADMIN_NOTIF_TITLE

async def admin_notif_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel(update.message.text):
        await update.message.reply_text("↩️ Cancelled.", reply_markup=ReplyKeyboardRemove())
        await send_admin_dashboard(update, context)
        return ConversationHandler.END
    context.user_data['notif_title'] = update.message.text.strip()
    await update.message.reply_text("📝 Description darj karein:")
    return ADMIN_NOTIF_DESC

async def admin_notif_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel(update.message.text):
        await update.message.reply_text("↩️ Cancelled.", reply_markup=ReplyKeyboardRemove())
        await send_admin_dashboard(update, context)
        return ConversationHandler.END
    context.user_data['notif_desc'] = update.message.text.strip()
    await update.message.reply_text(
        "🖼 Image URL darj karein (ya 'skip' likhein):"
    )
    return ADMIN_NOTIF_IMG

async def admin_notif_img(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel(update.message.text):
        await update.message.reply_text("↩️ Cancelled.", reply_markup=ReplyKeyboardRemove())
        await send_admin_dashboard(update, context)
        return ConversationHandler.END

    img   = update.message.text.strip()
    if img.lower() == 'skip':
        img = ""

    title = context.user_data.get('notif_title', '')
    desc  = context.user_data.get('notif_desc', '')

    try:
        key = DB.send_notification(title, desc, img)
        await update.message.reply_text(
            f"✅ *Notification Bhaij Di Gayi!*\n\n"
            f"📌 Title: {title}\n"
            f"📝 Desc : {desc[:80]}\n"
            f"🔑 Key  : `{key}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove()
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Error: `{e}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove()
        )
    await send_admin_dashboard(update, context)
    return ConversationHandler.END


# ===========================================================================
# MODULE 14: ADMIN — LIBRARY FLOW
# ===========================================================================

async def admin_add_lib_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "📚 *ADD LIBRARY SOURCE*\n\nSource ka name darj karein:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb_cancel()
    )
    return ADMIN_LIB_NAME

async def admin_lib_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel(update.message.text):
        await update.message.reply_text("↩️ Cancelled.", reply_markup=ReplyKeyboardRemove())
        await send_admin_dashboard(update, context)
        return ConversationHandler.END
    context.user_data['lib_name'] = update.message.text.strip()
    await update.message.reply_text("🔗 M3U/M3U8 URL darj karein:")
    return ADMIN_LIB_URL

async def admin_lib_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel(update.message.text):
        await update.message.reply_text("↩️ Cancelled.", reply_markup=ReplyKeyboardRemove())
        await send_admin_dashboard(update, context)
        return ConversationHandler.END

    name = context.user_data.get('lib_name', 'Unnamed')
    url  = update.message.text.strip()

    try:
        key = DB.add_library_source(name, url)
        await update.message.reply_text(
            f"✅ *Source Library Mein Add Ho Gaya!*\n\n"
            f"📛 Name: {name}\n"
            f"🔗 URL : `{url}`\n"
            f"🔑 Key : `{key}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove()
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Error: `{e}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove()
        )
    await send_admin_dashboard(update, context)
    return ConversationHandler.END


# ===========================================================================
# MODULE 15: ADMIN — BROADCAST FLOW
# ===========================================================================

async def admin_broadcast_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "📡 *BROADCAST MESSAGE*\n\nYeh message tamam registered users ko Firebase notification ke zariye jayega.\n\nMessage darj karein:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb_cancel()
    )
    return ADMIN_BROADCAST_MSG

async def admin_broadcast_msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel(update.message.text):
        await update.message.reply_text("↩️ Cancelled.", reply_markup=ReplyKeyboardRemove())
        await send_admin_dashboard(update, context)
        return ConversationHandler.END

    msg = update.message.text.strip()

    loading = await update.message.reply_text(
        "📡 Broadcasting...",
        reply_markup=ReplyKeyboardRemove()
    )

    try:
        # Send as Firebase notification to all
        key = DB.send_notification(
            title="📢 Network Announcement",
            description=msg,
            image="",
            author="Admin Maaz"
        )
        await loading.delete()
        await update.message.reply_text(
            f"✅ *Broadcast Complete!*\n\n"
            f"📝 Message: _{msg[:100]}_\n"
            f"🔑 Notification Key: `{key}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove()
        )
    except Exception as e:
        await loading.delete()
        await update.message.reply_text(
            f"❌ Broadcast Error: `{e}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove()
        )

    await send_admin_dashboard(update, context)
    return ConversationHandler.END


# ===========================================================================
# MODULE 16: RESELLER CALLBACKS
# ===========================================================================

async def reseller_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data  = query.data
    rid   = context.user_data.get('reseller_id')

    if context.user_data.get('role') != 'reseller' and data not in ['back_reseller', 'back_main']:
        await query.message.reply_text(
            "⚠️ Session expired. /start dabayein.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Restart", callback_data='back_main')
            ]])
        )
        return

    # ─── MY CLIENTS LIST ───────────────────────────────────────────────
    if data.startswith('res_list_'):
        page    = int(data.split('_')[-1])
        clients = DB.get_clients_by_reseller(rid)
        if not clients:
            await query.message.reply_text(
                "📋 Abhi koi client nahi.\n\n➕ Add Client button se client add karein!",
                reply_markup=kb_reseller_menu()
            )
            return
        text = f"📋 *MY CLIENTS* — `{len(clients)}` total\nSelect karein:"
        await query.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_paginated_clients_reseller(clients, page)
        )

    # ─── CLIENT DETAIL (Reseller) ──────────────────────────────────────
    elif data.startswith('res_client_detail_'):
        uid    = data[len('res_client_detail_'):]
        client = DB.get_client(rid, uid)
        if not client:
            await query.message.reply_text("Client nahi mila.", reply_markup=kb_back_to_reseller())
            return

        status       = client.get('status', 'Paid')
        toggle_label = "🔴 Block" if status == 'Paid' else "🟢 Unblock"
        m3u          = f"{VERCEL_BASE}{uid}"

        text = (
            f"👤 *CLIENT INFO*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🆔 UID   : `{uid}`\n"
            f"📛 Name  : {client.get('name','—')}\n"
            f"📞 Phone : {client.get('phone','—')}\n"
            f"📶 Status: {'✅ Paid' if status=='Paid' else '🚫 Blocked'}\n"
            f"🔗 M3U   : `{m3u}`\n"
            f"📅 Added : {format_timestamp(client.get('time', 0))}"
        )
        wa_link  = f"https://wa.me/{client.get('phone','').replace('+','').replace(' ','')}?text=Assalam%20o%20Alaikum!"
        keyboard = [
            [InlineKeyboardButton(toggle_label,          callback_data=f'res_toggle_{uid}_{status}')],
            [InlineKeyboardButton("📲 WhatsApp",         url=wa_link)],
            [InlineKeyboardButton("🔗 Copy M3U",         callback_data=f'res_copy_m3u_{uid}')],
            [InlineKeyboardButton("🗑 Delete",           callback_data=f'res_del_client_{uid}')],
            [InlineKeyboardButton("🔙 My Clients",       callback_data='res_list_0')],
        ]
        await query.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ─── TOGGLE CLIENT (Reseller) ──────────────────────────────────────
    elif data.startswith('res_toggle_'):
        parts      = data.split('_')
        uid        = parts[2]
        cur_status = parts[3]
        new_status = DB.toggle_client_status(rid, uid, cur_status)
        icon       = "✅" if new_status == 'Paid' else "🚫"
        await query.message.reply_text(
            f"{icon} `{uid}` ab *{new_status}* hai.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_back_to_reseller()
        )

    # ─── COPY M3U ──────────────────────────────────────────────────────
    elif data.startswith('res_copy_m3u_'):
        uid = data[len('res_copy_m3u_'):]
        m3u = f"{VERCEL_BASE}{uid}"
        await query.message.reply_text(
            f"🔗 *M3U Endpoint:*\n`{m3u}`\n\n_Upar wala link copy karein._",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_back_to_reseller()
        )

    # ─── DELETE CLIENT (Reseller) ──────────────────────────────────────
    elif data.startswith('res_del_client_'):
        uid    = data[len('res_del_client_'):]
        client = DB.get_client(rid, uid)
        label  = client.get('name', uid) if client else uid
        await query.message.reply_text(
            f"⚠️ *{label}* ko delete karein? Yeh wapas nahi aayega!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_confirm(f'res_del_confirm_{uid}', 'res_list_0')
        )

    elif data.startswith('res_del_confirm_'):
        uid = data[len('res_del_confirm_'):]
        DB.delete_client(rid, uid)
        await query.message.reply_text(
            f"✅ Client `{uid}` delete kar diya gaya.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_reseller_menu()
        )

    # ─── MY STATS ──────────────────────────────────────────────────────
    elif data == 'res_stats':
        clients = DB.get_clients_by_reseller(rid)
        paid    = sum(1 for c in clients.values() if isinstance(c, dict) and c.get('status') == 'Paid')
        blocked = len(clients) - paid
        name    = context.user_data.get('reseller_name', 'Reseller')
        text    = (
            f"📊 *MY STATS*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 Reseller : *{name}*\n"
            f"🆔 ID       : `{rid}`\n\n"
            f"👥 Total    : `{len(clients)}`\n"
            f"✅ Paid     : `{paid}`\n"
            f"🚫 Blocked  : `{blocked}`\n\n"
            f"🕐 {datetime.now().strftime('%d %b %Y — %I:%M %p')}"
        )
        await query.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb_back_to_reseller()
        )

    # ─── BACK / LOGOUT ─────────────────────────────────────────────────
    elif data == 'back_reseller':
        await send_reseller_dashboard(update, context)

    elif data == 'back_main':
        context.user_data.clear()
        await cmd_start(update, context)

    elif data == 'logout':
        context.user_data.clear()
        await query.message.reply_text("👋 Logout ho gaye!", reply_markup=ReplyKeyboardRemove())
        await cmd_start(update, context)


# ===========================================================================
# MODULE 17: RESELLER — ADD CLIENT FLOW
# ===========================================================================

async def res_add_client_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "➕ *NEW CLIENT ADD KAREIN*\n\nClient ka pura naam darj karein:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb_cancel()
    )
    return RES_ADD_CLIENT_NAME

async def res_add_client_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel(update.message.text):
        await update.message.reply_text("↩️ Cancelled.", reply_markup=ReplyKeyboardRemove())
        await send_reseller_dashboard(update, context)
        return ConversationHandler.END
    context.user_data['client_name'] = update.message.text.strip()
    await update.message.reply_text("📞 Client ka WhatsApp/Phone Number:")
    return RES_ADD_CLIENT_PHONE

async def res_add_client_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel(update.message.text):
        await update.message.reply_text("↩️ Cancelled.", reply_markup=ReplyKeyboardRemove())
        await send_reseller_dashboard(update, context)
        return ConversationHandler.END

    phone       = update.message.text.strip()
    name        = context.user_data.get('client_name', 'Client')
    rid         = context.user_data.get('reseller_id')

    loading_msg = await update.message.reply_text(
        "⏳ *Firebase mein deploy ho raha hai... M3U library inject ho rahi hai...*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove()
    )
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.UPLOAD_DOCUMENT
    )

    try:
        client_data = DB.create_client(rid, name, phone)
        uid         = client_data['uid']
        m3u         = client_data['m3u']

        await loading_msg.delete()

        # Success message
        await update.message.reply_text(
            f"✅ *CLIENT DEPLOY HO GAYA!*\n\n"
            f"🆔 UID  : `{uid}`\n"
            f"📛 Name : {name}\n"
            f"📞 Phone: {phone}\n"
            f"🔗 M3U  : `{m3u}`\n\n"
            f"👇 *Neeche client ko bhejne wala message hai:*",
            parse_mode=ParseMode.MARKDOWN
        )

        # WhatsApp activation post
        post = PostGenerator.activation_post(name, phone, m3u, uid)
        await update.message.reply_text(post, parse_mode=ParseMode.MARKDOWN)

        # Buttons
        wa_num  = phone.replace('+','').replace(' ','')
        wa_link = f"https://wa.me/{wa_num}?text=Assalam%20o%20Alaikum!"
        keyboard = [
            [InlineKeyboardButton("📲 WhatsApp Kholo",  url=wa_link)],
            [InlineKeyboardButton("🔗 M3U Copy",        callback_data=f'res_copy_m3u_{uid}')],
            [InlineKeyboardButton("🔙 My Menu",         callback_data='back_reseller')],
        ]
        await update.message.reply_photo(
            photo=SUCCESS_IMG,
            caption="✅ Client successfully MiTV Network mein add ho gaya!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    except Exception as e:
        await loading_msg.delete()
        await update.message.reply_text(
            f"❌ *Deployment Error:*\n`{e}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove()
        )
        await send_reseller_dashboard(update, context)

    return ConversationHandler.END


# ===========================================================================
# MODULE 18: RESELLER — SEARCH CLIENT FLOW
# ===========================================================================

async def res_search_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "🔍 *CLIENT SEARCH*\n\nClient ka naam, phone ya UID darj karein:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb_cancel()
    )
    return RES_SEARCH_QUERY

async def res_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel(update.message.text):
        await update.message.reply_text("↩️ Cancelled.", reply_markup=ReplyKeyboardRemove())
        await send_reseller_dashboard(update, context)
        return ConversationHandler.END

    query_text = update.message.text.strip()
    rid        = context.user_data.get('reseller_id')
    results    = DB.search_clients(rid, query_text)

    await update.message.reply_text("", reply_markup=ReplyKeyboardRemove())

    if not results:
        await update.message.reply_text(
            f"🔍 *'{query_text}'* ke liye koi client nahi mila.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_back_to_reseller()
        )
        return ConversationHandler.END

    text = f"🔍 *SEARCH RESULTS* — `{len(results)}` mile\n\n"
    for uid, c in list(results.items())[:10]:
        icon  = "✅" if c.get('status') == 'Paid' else "🚫"
        text += f"{icon} *{c.get('name','—')}* | {c.get('phone','—')} | `{uid}`\n"

    keyboard = []
    for uid in list(results.keys())[:8]:
        c     = results[uid]
        icon  = "✅" if c.get('status') == 'Paid' else "🚫"
        label = f"{icon} {c.get('name', uid)[:18]}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f'res_client_detail_{uid}')])
    keyboard.append([InlineKeyboardButton("🔙 My Menu", callback_data='back_reseller')])

    await update.message.reply_text(
        text, parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END


# ===========================================================================
# MODULE 19: AI CHAT MODE — PRIVATE + GROUP SUPPORT
# ===========================================================================

async def handle_ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    AI chat handler for private conversations.
    Full conversation history maintained.
    Thinking animation shown before response.
    """
    user_text = update.message.text

    if user_text.lower() in ['/exit', '/start', '❌ cancel', 'exit', 'quit']:
        await update.message.reply_text(
            "↩️ MI AI offline ho raha hai...",
            reply_markup=ReplyKeyboardRemove()
        )
        await cmd_start(update, context)
        return ROLE_SELECT

    # Typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING
    )

    # Thinking animation
    thinking_msg = await send_thinking_animation(context, update.effective_chat.id, steps=3)

    history  = context.user_data.get('ai_history', [])
    response = await MI_AI.respond(user_text, history, is_group=False)

    # Delete thinking animation
    if thinking_msg:
        try:
            await thinking_msg.delete()
        except Exception:
            pass

    # Update history
    history.append({"role": "user",      "content": user_text})
    history.append({"role": "assistant", "content": response})
    context.user_data['ai_history'] = history[-24:]  # Keep last 24 msgs

    # Send response with AI label
    try:
        await update.message.reply_text(
            f"🧠 *MI AI:*\n\n{response}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_ai_mode()
        )
    except Exception:
        await update.message.reply_text(
            f"🧠 MI AI:\n\n{response}",
            reply_markup=kb_ai_mode()
        )

    return AI_CHAT_MODE


async def handle_group_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    GROUP AI HANDLER — responds when:
    1. Bot is mentioned (@botname)
    2. Someone replies to bot's message
    3. Message starts with 'MI AI' or 'ai '
    This works in groups WITHOUT any /start command.
    """
    if not update.message or not update.message.text:
        return

    message   = update.message
    text      = message.text
    chat_type = message.chat.type
    bot_user  = context.bot.username

    is_private = chat_type == ChatType.PRIVATE
    if is_private:
        return  # Private handled by ConversationHandler

    should_respond = False
    user_query     = text

    # Check if bot is mentioned
    if bot_user and f"@{bot_user}" in text:
        should_respond = True
        user_query     = text.replace(f"@{bot_user}", "").strip()

    # Check if replying to bot's message
    elif message.reply_to_message and message.reply_to_message.from_user:
        if message.reply_to_message.from_user.username == bot_user:
            should_respond = True

    # Check if message starts with trigger keywords
    elif text.lower().startswith(('mi ai', 'miai', '/ai ')):
        should_respond = True
        user_query = re.sub(r'^(mi ai|miai|/ai)\s*', '', text, flags=re.IGNORECASE).strip()

    if not should_respond or not user_query:
        return

    # Typing
    await context.bot.send_chat_action(
        chat_id=message.chat.id,
        action=ChatAction.TYPING
    )

    # Thinking dots
    thinking_msg = await send_thinking_animation(context, message.chat.id, steps=2)

    # Get/init group history per chat
    group_key = f"group_history_{message.chat.id}"
    history   = context.bot_data.get(group_key, [])

    # Include user name in context
    user_name  = message.from_user.first_name if message.from_user else "User"
    full_query = f"{user_name} ne kaha: {user_query}"

    response = await MI_AI.respond(full_query, history, is_group=True)

    # Update group history (shared)
    history.append({"role": "user",      "content": full_query})
    history.append({"role": "assistant", "content": response})
    context.bot_data[group_key] = history[-20:]  # Keep 20 per group

    # Delete thinking
    if thinking_msg:
        try:
            await thinking_msg.delete()
        except Exception:
            pass

    # Reply in group
    try:
        await message.reply_text(
            f"🧠 *MI AI:*\n\n{response}",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        await message.reply_text(f"🧠 MI AI:\n\n{response}")


# ===========================================================================
# MODULE 20: AI HISTORY CLEAR CALLBACK
# ===========================================================================

async def ai_clear_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("✅ Chat history clear ho gayi!", show_alert=True)
    context.user_data['ai_history'] = []
    await query.message.reply_text(
        "🗑 *Chat history clear ho gayi!*\nAb nayi baat karein.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb_ai_mode()
    )


# ===========================================================================
# MODULE 21: BOT CONTROL MODE
# ===========================================================================

async def handle_bot_control(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    If user says 'bot control' — they get direct API access mode.
    Bot responds to their raw Telegram Bot API commands.
    In this mode bot does EXACTLY what user says.
    """
    text = update.message.text if update.message else ""

    if 'bot control' in text.lower():
        context.user_data['bot_control'] = True
        await update.message.reply_text(
            "🎮 *BOT CONTROL MODE ACTIVE*\n\n"
            "Ab aap bot ko direct control kar saktay hain.\n"
            "Jo command dein ge woh execute hogi.\n\n"
            "Available commands:\n"
            "`/bc send <chat_id> <message>` — Message bhejo\n"
            "`/bc stats` — Bot stats dekho\n"
            "`/bc exit` — Control mode band karo\n\n"
            "_Note: Yeh mode sirf authorized users ke liye hai._",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Main Menu", callback_data='back_main')
            ]])
        )
        return BOT_CONTROL_MODE

    return ConversationHandler.END

async def handle_bot_control_commands(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if text.startswith('/bc exit') or text.lower() == 'exit':
        context.user_data['bot_control'] = False
        await update.message.reply_text(
            "🔴 *Bot Control Mode band ho gaya.*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove()
        )
        await cmd_start(update, context)
        return ConversationHandler.END

    elif text.startswith('/bc stats'):
        stats = DB.get_system_stats()
        await update.message.reply_text(
            f"📊 *BOT STATS*\n\n"
            f"👥 Users: `{stats['total']}`\n"
            f"🟢 Live : `{stats['live']}`\n"
            f"📚 Lib  : `{stats['library']}`",
            parse_mode=ParseMode.MARKDOWN
        )

    elif text.startswith('/bc send'):
        # /bc send <chat_id> <message>
        parts = text.split(' ', 3)
        if len(parts) >= 4:
            chat_id = parts[2]
            msg     = parts[3]
            try:
                await context.bot.send_message(
                    chat_id=int(chat_id),
                    text=msg
                )
                await update.message.reply_text(f"✅ Message sent to `{chat_id}`.", parse_mode=ParseMode.MARKDOWN)
            except Exception as e:
                await update.message.reply_text(f"❌ Error: `{e}`", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("Usage: `/bc send <chat_id> <message>`", parse_mode=ParseMode.MARKDOWN)

    else:
        # Pass any unknown text to AI in control mode
        response = await MI_AI.respond(text)
        await update.message.reply_text(f"🧠 MI AI:\n\n{response}")

    return BOT_CONTROL_MODE


# ===========================================================================
# MODULE 22: FLOATING CALLBACK ROUTER (CATCHES ALL)
# ===========================================================================

async def floating_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Master router for all inline button callbacks.
    Routes to appropriate handlers smoothly.
    """
    query = update.callback_query
    data  = query.data

    if data == 'noop':
        await query.answer()
        return

    if data == 'ai_clear_history':
        await ai_clear_history(update, context)
        return

    if data == 'back_main':
        await query.answer()
        context.user_data.clear()
        await cmd_start(update, context)
        return

    if data == 'admin_add_res':
        await admin_add_res_trigger(update, context)
        return

    if data == 'admin_notif':
        await admin_notif_trigger(update, context)
        return

    if data == 'admin_add_lib':
        await admin_add_lib_trigger(update, context)
        return

    if data == 'admin_broadcast':
        await admin_broadcast_trigger(update, context)
        return

    if data == 'res_add_client':
        await res_add_client_trigger(update, context)
        return

    if data == 'res_search':
        await res_search_trigger(update, context)
        return

    if data in ('role_admin', 'role_reseller', 'role_ai', 'quick_stats', 'about_bot'):
        await handle_role_selection(update, context)
        return

    if data == 'logout':
        await query.answer()
        context.user_data.clear()
        await query.message.reply_text("👋 Logout ho gaye!", reply_markup=ReplyKeyboardRemove())
        await cmd_start(update, context)
        return

    # Route to admin or reseller handlers
    if (data.startswith('admin_') or data in ('back_admin',)):
        await admin_callback_handler(update, context)
        return

    if (data.startswith('res_') or data in ('back_reseller',)):
        await reseller_callback_handler(update, context)
        return

    # Unknown callback — just answer
    await query.answer("⚠️ Unknown action. /start dabayein.")


# ===========================================================================
# MODULE 23: STANDALONE COMMANDS
# ===========================================================================

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = DB.get_system_stats()
    text  = (
        f"📊 *MITV NETWORK STATS*\n\n"
        f"👥 Total : `{stats['total']}`\n"
        f"✅ Paid  : `{stats['paid']}`\n"
        f"🚫 Block : `{stats['blocked']}`\n"
        f"🟢 Live  : `{stats['live']}` nodes\n"
        f"📚 Lib   : `{stats['library']}` sources\n"
        f"🧑‍🤝‍🧑 Res : `{stats['resellers']}`"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"📖 *MITV BOT v6.0 HELP*\n\n"
        f"*/start*  — Main menu\n"
        f"*/stats*  — Network stats\n"
        f"*/help*   — Yeh message\n"
        f"*/exit*   — Kisi bhi mode se wapas\n"
        f"*/ai*     — Directly AI se baat karein\n\n"
        f"🔐 *Admin Portal* — Full network management\n"
        f"🧑‍💻 *Reseller Portal* — Client management\n"
        f"🧠 *MI AI* — {MI_AI.engine_name}\n\n"
        f"*Group mein AI use karne ka tariqa:*\n"
        f"• Bot ko mention karein: @BotName\n"
        f"• Bot ki message pe reply karein\n"
        f"• 'MI AI' se start karein\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🏢 Project of: MUSLIM ISLAM\n"
        f"👑 Founder: Muaaz Iqbal (Kasur)"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def cmd_exit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("↩️ Reset ho raha hai...", reply_markup=ReplyKeyboardRemove())
    await cmd_start(update, context)
    return ConversationHandler.END

async def cmd_ai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Shortcut to enter AI mode directly."""
    context.user_data['ai_history'] = []
    ai_status = f"✅ {MI_AI.engine_name}" if MI_AI.active else "❌ Offline"
    await update.message.reply_text(
        f"🧠 *MI AI ONLINE*\n\n"
        f"Engine: `{ai_status}`\n\n"
        f"Kuch bhi poochh saktay hain!\n"
        f"_/exit se wapas jayen._",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb_ai_mode()
    )
    return AI_CHAT_MODE

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Unhandled exception: {context.error}", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ Ek internal error aayi. /start dabayein.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔄 Restart", callback_data='back_main')
                ]])
            )
        except Exception:
            pass


# ===========================================================================
# MODULE 24: APPLICATION BOOTSTRAP
# ===========================================================================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # ─── MASTER CONVERSATION HANDLER ────────────────────────────────────
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', cmd_start),
            CommandHandler('exit',  cmd_exit),
            CommandHandler('ai',    cmd_ai),
            CallbackQueryHandler(handle_role_selection, pattern='^role_'),
        ],
        states={
            ROLE_SELECT: [
                CallbackQueryHandler(handle_role_selection, pattern='^(role_|quick_stats|about_bot)'),
            ],

            # Admin Auth
            ADMIN_LOGIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_login)
            ],

            # Reseller Auth
            RESELLER_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, reseller_enter_phone)
            ],
            RESELLER_PASS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, reseller_enter_pass)
            ],

            # Admin: Add Reseller
            ADMIN_ADD_RES_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_res_name)
            ],
            ADMIN_ADD_RES_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_res_phone)
            ],
            ADMIN_ADD_RES_PASS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_res_pass)
            ],

            # Admin: Notifications
            ADMIN_NOTIF_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_notif_title)
            ],
            ADMIN_NOTIF_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_notif_desc)
            ],
            ADMIN_NOTIF_IMG: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_notif_img)
            ],

            # Admin: Library
            ADMIN_LIB_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_lib_name)
            ],
            ADMIN_LIB_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_lib_url)
            ],

            # Admin: Broadcast
            ADMIN_BROADCAST_MSG: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_msg)
            ],

            # Reseller: Add Client
            RES_ADD_CLIENT_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, res_add_client_name)
            ],
            RES_ADD_CLIENT_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, res_add_client_phone)
            ],

            # Reseller: Search
            RES_SEARCH_QUERY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, res_search_query)
            ],

            # AI Chat
            AI_CHAT_MODE: [
                MessageHandler(filters.TEXT, handle_ai_chat),
                CallbackQueryHandler(ai_clear_history, pattern='^ai_clear_history$'),
            ],

            # Bot Control Mode
            BOT_CONTROL_MODE: [
                MessageHandler(filters.TEXT, handle_bot_control_commands),
            ],
        },
        fallbacks=[
            CommandHandler('start', cmd_start),
            CommandHandler('exit',  cmd_exit),
        ],
        allow_reentry=True,
        per_message=False,
    )

    app.add_handler(conv_handler)

    # ─── GROUP AI HANDLER ────────────────────────────────────────────────
    # This catches messages in groups where bot is mentioned or replied to
    app.add_handler(MessageHandler(
        filters.TEXT & (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP),
        handle_group_ai_message
    ), group=1)

    # ─── FLOATING CALLBACK ROUTER ────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(floating_callback_router), group=2)

    # ─── STANDALONE COMMANDS ─────────────────────────────────────────────
    app.add_handler(CommandHandler('stats', cmd_stats))
    app.add_handler(CommandHandler('help',  cmd_help))

    # ─── ERROR HANDLER ───────────────────────────────────────────────────
    app.add_error_handler(error_handler)

    # ─── STARTUP BANNER ──────────────────────────────────────────────────
    print("\n" + "=" * 68)
    print("  🚀 MITV NETWORK OS — TELEGRAM BOT ENGINE v6.0 (ULTRA ENTERPRISE)")
    print("  🏢 Project   : MUSLIM ISLAM")
    print("  👑 Founder   : Muaaz Iqbal (Kasur, Punjab, Pakistan)")
    print("  🔥 Firebase  : ramadan-2385b")
    print("  🌐 Vercel    : mitv-tan.vercel.app")
    print(f"  🤖 AI Engine : {MI_AI.engine_name} — {'ONLINE ✅' if MI_AI.active else 'OFFLINE ❌'}")
    print("  🧠 Group AI  : ENABLED (mention bot or reply)")
    print("  📡 Status    : POLLING...")
    print("=" * 68 + "\n")

    app.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()


"""
=========================================================================================
📋 DEPLOYMENT CHECKLIST — v6.0
=========================================================================================
1. firebase.json       — Service Account JSON file (same directory as bot.py)

2. Set environment variables:
   export CLAUDE_API_KEY="sk-ant-..."    ← PRIMARY AI (Claude claude-sonnet-4-20250514)
   export GROQ_API_KEY="gsk_..."         ← FALLBACK AI (optional)

3. Install dependencies:
   pip install -r requirements.txt

4. Run:
   python bot.py

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

AI PRIORITY:
  1st: Claude claude-sonnet-4-20250514 (CLAUDE_API_KEY) — Most intelligent
  2nd: Groq LLaMA-3 70B (GROQ_API_KEY)   — Fallback
  If neither set: AI mode shows offline message

GROUP AI USAGE:
  • @YourBotName kuch bhi — Bot jawab dega
  • Bot ki message pe reply — Bot continue karega
  • "MI AI kya hai Python?" — Trigger keyword

BOT CONTROL MODE:
  • Private chat mein "bot control" likho
  • /bc send <chat_id> <msg> — message bhejo
  • /bc stats — stats dekho
  • /bc exit — mode band karo

FIREBASE NODES:
  /master_users/         — All subscribers
  /active_playlists/     — M3U engine data
  /clients/{RES}/{UID}   — Reseller client snapshots
  /resellers/            — Reseller accounts
  /playlist_library/     — Global M3U sources
  /notifications/        — App push notifications
  /user_logs/            — Stream tracking
  /global_stats/         — Aggregated stats
=========================================================================================
"""
