"""
=========================================================================================
🌟 MITV NETWORK - OFFICIAL TELEGRAM AI BOT & MANAGEMENT SYSTEM 🌟
=========================================================================================
Project Of   : MUSLIM ISLAM
Founder & CEO: Muaaz Iqbal
Location     : Kasur, Punjab, Pakistan
Version      : 5.0 (Full Enterprise Edition with Groq LLaMA-3 AI)
Firebase DB  : ramadan-2385b
Vercel API   : https://mitv-tan.vercel.app/api/m3u?user=MITV-XXXXX

DATABASE STRUCTURE (Firebase Realtime DB):
  /master_users/{uid}
      name, phone, status, reseller_id, created_at, updated_at

  /active_playlists/{uid}
      sources[], warningVideo, assigned_by, lastUpdate

  /clients/{reseller_id}/{uid}
      uid, name, phone, m3u, status, time

  /resellers/{reseller_id}
      name, number, password, active, created_at

  /playlist_library/{push_id}
      name, url, added

  /notifications/{push_id}
      title, description, image, timestamp, author

  /user_logs/{uid}/{log_id}
      channel, ip, time, device

  /global_stats/{uid}
      total, active, dead, last_scan

MODULES:
  1. Firebase Database Manager     - Full CRUD + M3U injection engine
  2. MI AI Core (Groq LLaMA-3)     - Autonomous AI assistant
  3. Telegram UI/UX Manager        - Pagination, rich media, animations
  4. Post Generator                - WhatsApp activation templates
  5. Real-time Analytics           - Network-wide live statistics
  6. Notification System           - Push to app via Firebase
  7. Admin: Reseller Management    - Add, list, delete, toggle resellers
  8. Admin: Library Management     - Add/remove global M3U sources
  9. Reseller: Client Management   - Full lifecycle management
 10. Deep Trace & Logs             - Live stream tracking per user
=========================================================================================
"""

import logging
import os
import time
import uuid
import json
import asyncio
import re
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
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ===========================================================================
# FIREBASE IMPORTS
# ===========================================================================
import firebase_admin
from firebase_admin import credentials, db

# ===========================================================================
# GROQ AI IMPORT
# ===========================================================================
try:
    from groq import AsyncGroq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

# ===========================================================================
# SYSTEM CONFIGURATION & CONSTANTS
# ===========================================================================

BOT_TOKEN       = "8700778314:AAECDc3KN8BzDD_-4_Clkv0zGxhgC1WRw5g"
ADMIN_PASSWORD  = "123456"

# Firebase
FIREBASE_DB_URL   = "https://ramadan-2385b-default-rtdb.firebaseio.com"
FIREBASE_CRED_PATH = "firebase.json"

# Groq
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = "llama3-70b-8192"

# Vercel Endpoint Pattern
VERCEL_BASE = "https://mitv-tan.vercel.app/api/m3u?user="

# App Download
APP_DOWNLOAD_LINK = "https://mitvnet.vercel.app/mitvnet.apk"

# Media (Unsplash stable links, no expiry)
SUCCESS_IMG = "https://images.unsplash.com/photo-1586281380349-632531db7ed4?q=80&w=800&auto=format&fit=crop"
ERROR_IMG   = "https://images.unsplash.com/photo-1525785967371-87ba44b3e6cf?q=80&w=800&auto=format&fit=crop"
BANNER_IMG  = "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?q=80&w=800&auto=format&fit=crop"

# WARNING: Welcome GIF - using a stable Telegram-hosted URL fallback
WELCOME_GIF = "https://media1.giphy.com/media/3o7TKMt1VVNkHV2PaE/giphy.gif"

# Pagination
PAGE_SIZE = 5

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

    # Admin: Edit Reseller
    ADMIN_EDIT_RES_SELECT,
    ADMIN_EDIT_RES_FIELD,
    ADMIN_EDIT_RES_VALUE,

    # Reseller: Add Client
    RES_ADD_CLIENT_NAME,
    RES_ADD_CLIENT_PHONE,

    # Reseller: Edit Client
    RES_EDIT_CLIENT_SELECT,
    RES_EDIT_FIELD,
    RES_EDIT_VALUE,

    # AI Chat
    AI_CHAT_MODE,

    # Engine: Manual Deploy
    ENGINE_SELECT_USER,
    ENGINE_ENTER_SOURCES,
    ENGINE_CONFIRM,

) = range(24)

# ===========================================================================
# LOGGING SETUP
# ===========================================================================
logging.basicConfig(
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("MITV_BOT")


# ===========================================================================
# MODULE 1: FIREBASE DATABASE MANAGER
# ===========================================================================

class DatabaseManager:
    """
    Centralized Firebase Realtime Database handler.
    All reads/writes go through this class to ensure consistency.

    DB Structure used:
      master_users/     - Source of truth for all subscribers
      active_playlists/ - Engine data per user (M3U sources + warning video)
      clients/          - Reseller-grouped client snapshots
      resellers/        - Reseller accounts
      playlist_library/ - Global default M3U sources
      notifications/    - App push notifications
      user_logs/        - Stream activity logs (from Vercel api/m3u.js)
      global_stats/     - Aggregated stats per user node
    """

    def __init__(self):
        self._init_firebase()

    def _init_firebase(self):
        """Safely initializes Firebase Admin SDK (idempotent)."""
        try:
            if not firebase_admin._apps:
                if not os.path.exists(FIREBASE_CRED_PATH):
                    logger.error(f"❌ Firebase credential file not found: {FIREBASE_CRED_PATH}")
                    return
                cred = credentials.Certificate(FIREBASE_CRED_PATH)
                firebase_admin.initialize_app(cred, {'databaseURL': FIREBASE_DB_URL})
                logger.info("✅ Firebase initialized successfully.")
        except Exception as e:
            logger.error(f"❌ Firebase init error: {e}")

    # -----------------------------------------------------------------------
    # CLIENT MANAGEMENT
    # -----------------------------------------------------------------------

    def create_client(self, reseller_id: str, name: str, phone: str) -> dict:
        """
        Creates a new subscriber:
        1. Generates UID (MITV-XXXXX)
        2. Saves to master_users/
        3. Fetches playlist_library/ and injects into active_playlists/
        4. Saves snapshot to clients/{reseller_id}/
        Returns the full client dict with m3u link.
        """
        uid = f"MITV-{str(uuid.uuid4())[:5].upper()}"
        timestamp = int(time.time() * 1000)

        # Step 1: Save to master_users
        master_payload = {
            "name":        name,
            "phone":       phone,
            "status":      "Paid",
            "reseller_id": reseller_id,
            "created_at":  timestamp,
            "updated_at":  timestamp
        }
        db.reference(f'master_users/{uid}').set(master_payload)

        # Step 2: Fetch global library for auto-injection
        lib_ref = db.reference('playlist_library').get()
        default_sources = []
        if lib_ref and isinstance(lib_ref, dict):
            for key, val in lib_ref.items():
                if isinstance(val, dict) and val.get('url'):
                    default_sources.append(val['url'])

        # Fallback source
        if not default_sources:
            default_sources = ["https://mitvnet.vercel.app/default.m3u"]

        # Step 3: Inject into active_playlists (the core engine node)
        playlist_payload = {
            "sources":      default_sources,
            "warningVideo": "https://mitvnet.vercel.app/mipay.mp4",
            "assigned_by":  f"Reseller_{reseller_id}",
            "lastUpdate":   timestamp
        }
        db.reference(f'active_playlists/{uid}').set(playlist_payload)

        # Step 4: Generate Vercel endpoint
        m3u_link = f"{VERCEL_BASE}{uid}"

        # Step 5: Save to reseller's client list
        client_snapshot = {
            "uid":    uid,
            "name":   name,
            "phone":  phone,
            "m3u":    m3u_link,
            "status": "Paid",
            "time":   timestamp
        }
        db.reference(f'clients/{reseller_id}/{uid}').set(client_snapshot)

        logger.info(f"✅ Created client {uid} under reseller {reseller_id}")
        return client_snapshot

    def get_client(self, reseller_id: str, uid: str) -> Optional[dict]:
        """Retrieves a single client by UID under a reseller."""
        try:
            data = db.reference(f'clients/{reseller_id}/{uid}').get()
            return data
        except Exception as e:
            logger.error(f"get_client error: {e}")
            return None

    def get_clients_by_reseller(self, reseller_id: str) -> dict:
        """Returns all clients for a given reseller."""
        try:
            data = db.reference(f'clients/{reseller_id}').get()
            return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.error(f"get_clients_by_reseller error: {e}")
            return {}

    def get_all_clients(self) -> dict:
        """Admin-only: returns ALL clients from master_users."""
        try:
            data = db.reference('master_users').get()
            return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.error(f"get_all_clients error: {e}")
            return {}

    def toggle_client_status(self, reseller_id: str, uid: str, current_status: str) -> str:
        """
        Toggles client status between Paid <-> Blocked.
        Updates both master_users/ and clients/{reseller_id}/ nodes.
        """
        new_status = "Blocked" if current_status == "Paid" else "Paid"
        try:
            db.reference(f'master_users/{uid}/status').set(new_status)
            db.reference(f'master_users/{uid}/updated_at').set(int(time.time() * 1000))
            db.reference(f'clients/{reseller_id}/{uid}/status').set(new_status)
            logger.info(f"Toggled {uid} status: {current_status} -> {new_status}")
            return new_status
        except Exception as e:
            logger.error(f"toggle_client_status error: {e}")
            raise

    def update_client_field(self, reseller_id: str, uid: str, field: str, value: str):
        """Updates a specific field on both master_users and clients nodes."""
        try:
            db.reference(f'master_users/{uid}/{field}').set(value)
            db.reference(f'master_users/{uid}/updated_at').set(int(time.time() * 1000))
            db.reference(f'clients/{reseller_id}/{uid}/{field}').set(value)
        except Exception as e:
            logger.error(f"update_client_field error: {e}")
            raise

    def delete_client(self, reseller_id: str, uid: str):
        """
        Fully purges a client from:
          - master_users/
          - active_playlists/
          - clients/{reseller_id}/
          - global_stats/
        """
        try:
            updates = {
                f'master_users/{uid}':         None,
                f'active_playlists/{uid}':     None,
                f'clients/{reseller_id}/{uid}': None,
                f'global_stats/{uid}':         None,
            }
            db.reference().update(updates)
            logger.info(f"Deleted client {uid} from all nodes.")
        except Exception as e:
            logger.error(f"delete_client error: {e}")
            raise

    # -----------------------------------------------------------------------
    # ENGINE: ACTIVE PLAYLISTS (M3U MASKING)
    # -----------------------------------------------------------------------

    def deploy_playlist(self, uid: str, sources: List[str], warning_video: str = "",
                        assigned_by: str = "Admin Maaz") -> str:
        """
        Core engine: writes sources to active_playlists/{uid}.
        Returns the Vercel endpoint URL.
        """
        if not warning_video:
            warning_video = "https://mitvnet.vercel.app/mipay.mp4"

        payload = {
            "sources":      sources,
            "warningVideo": warning_video,
            "assigned_by":  assigned_by,
            "lastUpdate":   int(time.time() * 1000)
        }
        db.reference(f'active_playlists/{uid}').set(payload)
        endpoint = f"{VERCEL_BASE}{uid}"
        logger.info(f"Engine deployed for {uid}: {len(sources)} sources.")
        return endpoint

    def get_active_playlist(self, uid: str) -> Optional[dict]:
        """Fetches the current active playlist config for a user."""
        try:
            return db.reference(f'active_playlists/{uid}').get()
        except Exception as e:
            logger.error(f"get_active_playlist error: {e}")
            return None

    # -----------------------------------------------------------------------
    # RESELLER MANAGEMENT
    # -----------------------------------------------------------------------

    def add_reseller(self, name: str, phone: str, password: str) -> str:
        """Registers a new reseller. Returns the generated reseller ID."""
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
        """
        Checks phone + password against resellers/ node.
        Returns reseller dict with 'id' field if valid, else None.
        """
        try:
            resellers = db.reference('resellers').get()
            if not resellers:
                return None
            for rid, data in resellers.items():
                if (isinstance(data, dict)
                        and data.get('number') == phone
                        and data.get('password') == password
                        and data.get('active', True)):
                    data['id'] = rid
                    return data
        except Exception as e:
            logger.error(f"authenticate_reseller error: {e}")
        return None

    def get_all_resellers(self) -> dict:
        """Returns all resellers from DB."""
        try:
            data = db.reference('resellers').get()
            return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.error(f"get_all_resellers error: {e}")
            return {}

    def get_reseller(self, reseller_id: str) -> Optional[dict]:
        """Fetches a single reseller by ID."""
        try:
            return db.reference(f'resellers/{reseller_id}').get()
        except Exception as e:
            logger.error(f"get_reseller error: {e}")
            return None

    def toggle_reseller_status(self, reseller_id: str) -> bool:
        """Toggles reseller active status. Returns new state."""
        try:
            current = db.reference(f'resellers/{reseller_id}/active').get()
            new_state = not bool(current)
            db.reference(f'resellers/{reseller_id}/active').set(new_state)
            return new_state
        except Exception as e:
            logger.error(f"toggle_reseller_status error: {e}")
            raise

    def delete_reseller(self, reseller_id: str):
        """Removes a reseller record (does NOT delete their clients)."""
        try:
            db.reference(f'resellers/{reseller_id}').delete()
        except Exception as e:
            logger.error(f"delete_reseller error: {e}")
            raise

    # -----------------------------------------------------------------------
    # PLAYLIST LIBRARY MANAGEMENT
    # -----------------------------------------------------------------------

    def add_library_source(self, name: str, url: str) -> str:
        """Adds a new M3U source to global library. Returns push key."""
        payload = {"name": name, "url": url, "added": int(time.time() * 1000)}
        ref = db.reference('playlist_library').push(payload)
        return ref.key

    def get_library(self) -> dict:
        """Returns all global library sources."""
        try:
            data = db.reference('playlist_library').get()
            return data if isinstance(data, dict) else {}
        except Exception as e:
            logger.error(f"get_library error: {e}")
            return {}

    def delete_library_source(self, key: str):
        """Removes a source from the global library by its push key."""
        db.reference(f'playlist_library/{key}').delete()

    # -----------------------------------------------------------------------
    # NOTIFICATIONS
    # -----------------------------------------------------------------------

    def push_notification(self, title: str, description: str, image: str = "") -> bool:
        """Pushes a notification to /notifications/ for the mobile app to consume."""
        try:
            payload = {
                "title":       title,
                "description": description,
                "image":       image,
                "timestamp":   int(time.time() * 1000),
                "author":      "Admin Maaz"
            }
            db.reference('notifications').push(payload)
            logger.info(f"Pushed notification: {title}")
            return True
        except Exception as e:
            logger.error(f"push_notification error: {e}")
            return False

    def get_recent_notifications(self, limit: int = 5) -> list:
        """Returns the most recent N notifications."""
        try:
            data = db.reference('notifications').get()
            if not data:
                return []
            items = list(data.values())
            items.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            return items[:limit]
        except Exception as e:
            logger.error(f"get_recent_notifications error: {e}")
            return []

    # -----------------------------------------------------------------------
    # ANALYTICS & LOGS
    # -----------------------------------------------------------------------

    def get_system_stats(self) -> dict:
        """
        Aggregates live statistics:
          - Total subscribers
          - Paid / Blocked breakdown
          - Live users (active within last 5 min based on user_logs)
          - Library count
          - Reseller count
        """
        stats = {"total": 0, "paid": 0, "blocked": 0, "live": 0,
                 "library": 0, "resellers": 0}
        try:
            users = db.reference('master_users').get() or {}
            stats['total'] = len(users)
            for u in users.values():
                if isinstance(u, dict):
                    if u.get('status') == 'Paid':
                        stats['paid'] += 1
                    elif u.get('status') == 'Blocked':
                        stats['blocked'] += 1

            # Live count via user_logs
            logs = db.reference('user_logs').get() or {}
            now_ms = time.time() * 1000
            for uid, user_logs in logs.items():
                if not isinstance(user_logs, dict):
                    continue
                for log_id, log_data in user_logs.items():
                    if not isinstance(log_data, dict):
                        continue
                    log_time = log_data.get('time', log_data.get('timestamp', 0))
                    if isinstance(log_time, (int, float)) and (now_ms - log_time) < 300000:
                        stats['live'] += 1
                        break

            lib = db.reference('playlist_library').get() or {}
            stats['library'] = len(lib) if isinstance(lib, dict) else 0

            resellers = db.reference('resellers').get() or {}
            stats['resellers'] = len(resellers) if isinstance(resellers, dict) else 0

        except Exception as e:
            logger.error(f"get_system_stats error: {e}")

        return stats

    def get_user_logs(self, uid: str, limit: int = 20) -> list:
        """Returns recent stream logs for a specific user."""
        try:
            data = db.reference(f'user_logs/{uid}').get()
            if not data or not isinstance(data, dict):
                return []
            logs = list(data.values())
            logs.sort(key=lambda x: x.get('time', x.get('timestamp', 0)), reverse=True)
            return logs[:limit]
        except Exception as e:
            logger.error(f"get_user_logs error: {e}")
            return []

    def get_all_live_logs(self, limit: int = 15) -> list:
        """Returns the most recent stream events across all users."""
        try:
            all_logs_node = db.reference('user_logs').get()
            if not all_logs_node or not isinstance(all_logs_node, dict):
                return []

            all_logs = []
            for uid, user_logs in all_logs_node.items():
                if not isinstance(user_logs, dict):
                    continue
                for log_id, log_data in user_logs.items():
                    if isinstance(log_data, dict):
                        log_data['_uid'] = uid
                        all_logs.append(log_data)

            all_logs.sort(
                key=lambda x: x.get('time', x.get('timestamp', 0)),
                reverse=True
            )
            return all_logs[:limit]
        except Exception as e:
            logger.error(f"get_all_live_logs error: {e}")
            return []


# Global DB instance
DB = DatabaseManager()


# ===========================================================================
# MODULE 2: MI AI CORE (Groq LLaMA-3)
# ===========================================================================

class MIAIEngine:
    """
    MI AI - Powered by Groq's LPU + LLaMA-3 70B.
    Acts as autonomous technical and business assistant for MiTV Network.
    Communicates in Roman Urdu / English mix.
    """

    SYSTEM_PROMPT = """
You are 'MI AI', the official artificial intelligence of the MiTV Network by MUSLIM ISLAM.

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

PERSONALITY:
- Highly intelligent, loyal to Muaaz Iqbal, professional yet warm.
- Communicate in a seamless mix of Roman Urdu and English.
- Explain complex concepts in Urdu first, then provide the English term.
- Never use LaTeX. Use plain markdown only.
- If asked who created you: "Main MI AI hoon, Muaaz Iqbal ne create kiya."

CAPABILITIES:
- Python, Firebase, Telegram Bot API, IPTV protocols, M3U/M3U8 formats.
- Android development, Vercel serverless functions.
- Network management, reseller systems, subscription management.
- General questions, Islamic topics, tech advice, business strategy.
"""

    def __init__(self):
        self.active = False
        if GROQ_AVAILABLE and GROQ_API_KEY:
            try:
                self.client = AsyncGroq(api_key=GROQ_API_KEY)
                self.active = True
                logger.info("✅ Groq MI AI initialized.")
            except Exception as e:
                logger.warning(f"Groq init warning: {e}")
        else:
            logger.warning("⚠️ Groq not available — AI mode disabled.")

    async def respond(self, user_message: str, history: List[dict] = None) -> str:
        """Generates a response using Groq LLaMA-3."""
        if not self.active:
            return ("⚠️ *MI AI offline* hai.\n\n"
                    "Reason: GROQ_API_KEY environment variable set nahi hai.\n"
                    "Admin se contact karein ya `GROQ_API_KEY` set karein.")

        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
        if history:
            messages.extend(history[-10:])  # Keep last 10 exchanges
        messages.append({"role": "user", "content": user_message})

        try:
            response = await self.client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                temperature=0.72,
                max_tokens=1024,
                top_p=0.9
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Groq response error: {e}")
            return f"🤖 MI AI temporary server load hai. Thodi der baad try karein.\n_(Error: {e})_"


MI_AI = MIAIEngine()


# ===========================================================================
# MODULE 3: POST GENERATOR (WhatsApp Templates)
# ===========================================================================

class PostGenerator:
    """Generates stylized activation messages for WhatsApp sharing."""

    @staticmethod
    def activation_post(name: str, phone: str, m3u: str, uid: str) -> str:
        return (
            f"🌟 🅼🅸🆃🆅 🅽🅴🆃🆆🅾🆁🅺 🌟\n"
            f"🚀 𝐀𝐜𝐜𝐨𝐮𝐧𝐭 𝐀𝐜𝐭𝐢𝐯𝐚𝐭𝐢𝐨𝐧 𝐒𝐮𝐜𝐜𝐞𝐬𝐬𝐟𝐮𝐥! 🚀\n\n"
            f"Assalam o Alaikum! ✨\n"
            f"*{name}*, humein batate hue khushi ho rahi hai ke aapka 🅼🅸🆃🆅 account "
            f"successfully active kar diya gaya hai. 🎉\n\n"
            f"📝 𝐘𝐨𝐮𝐫 𝐀𝐜𝐜𝐨𝐮𝐧𝐭 𝐃𝐞𝐭𝐚𝐢𝐥𝐬:\n"
            f"👤 𝐍𝐚𝐦𝐞: {name}\n"
            f"📞 𝐍𝐮𝐦𝐛𝐞𝐫: {phone}\n"
            f"🆔 𝐔𝐈𝐃: `{uid}`\n"
            f"🔗 𝐌𝟑𝐔 𝐋𝐢𝐧𝐤:\n`{m3u}`\n\n"
            f"📥 𝐀𝐩𝐩 𝐈𝐧𝐬𝐭𝐚𝐥𝐥𝐚𝐭𝐢𝐨𝐧:\n"
            f"📲 {APP_DOWNLOAD_LINK}\n\n"
            f"🏢 𝐏𝐫𝐨𝐣𝐞𝐜𝐭 𝐎𝐟: 🅼🆄🆂🅻🅸🅼 🅸🆂🅻🅰🅼\n"
            f"👑 𝐅𝐨𝐮𝐧𝐝𝐞𝐫: 𝐌𝐮𝐚𝐚𝐳 𝐈𝐪𝐛𝐚𝐥 (𝐊𝐚𝐬𝐮𝐫)\n\n"
            f"𝗛𝗨𝗠𝗘 𝗝𝗢𝗜𝗡 𝗞𝗔𝗥𝗡𝗘 𝗞𝗔 𝗦𝗛𝗨𝗞𝗥𝗜𝗬𝗔! ❤️\n"
            f"Koi masla ho to hum se rabta karein."
        )

    @staticmethod
    def renewal_post(name: str, uid: str) -> str:
        return (
            f"✅ 𝐀𝐜𝐜𝐨𝐮𝐧𝐭 𝐑𝐞𝐧𝐞𝐰𝐞𝐝! ✅\n\n"
            f"*{name}* — aapka MiTV account renew ho gaya hai!\n"
            f"🆔 UID: `{uid}`\n\n"
            f"𝐏𝐫𝐨𝐣𝐞𝐜𝐭 𝐎𝐟: 🅼🆄🆂🅻🅸🅼 🅸🆂🅻🅰🅼 | 𝐅𝐨𝐮𝐧𝐝𝐞𝐫: 𝐌𝐮𝐚𝐚𝐳 𝐈𝐪𝐛𝐚𝐥"
        )


# ===========================================================================
# MODULE 4: KEYBOARD / UI BUILDERS
# ===========================================================================

def kb_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👑 Admin Portal",    callback_data='role_admin')],
        [InlineKeyboardButton("🧑‍💻 Reseller Portal", callback_data='role_reseller')],
        [InlineKeyboardButton("🧠 MI AI Core",      callback_data='role_ai')],
    ])

def kb_admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Analytics",       callback_data='admin_stats'),
            InlineKeyboardButton("🛰️ Live Tracking",   callback_data='admin_track'),
        ],
        [
            InlineKeyboardButton("👥 All Clients",     callback_data='admin_clients_0'),
            InlineKeyboardButton("🧑‍🤝‍🧑 Resellers",    callback_data='admin_resellers_0'),
        ],
        [
            InlineKeyboardButton("➕ Add Reseller",    callback_data='admin_add_res'),
            InlineKeyboardButton("📚 Library",         callback_data='admin_library_0'),
        ],
        [
            InlineKeyboardButton("📢 Notification",    callback_data='admin_notif'),
            InlineKeyboardButton("🔔 Recent Notifs",   callback_data='admin_notif_list'),
        ],
        [InlineKeyboardButton("🚪 Logout",             callback_data='logout')],
    ])

def kb_reseller_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Client",          callback_data='res_add_client')],
        [InlineKeyboardButton("📋 My Clients",          callback_data='res_list_0')],
        [InlineKeyboardButton("📊 My Stats",            callback_data='res_stats')],
        [InlineKeyboardButton("🚪 Logout",              callback_data='logout')],
    ])

def kb_cancel() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["❌ Cancel"]], resize_keyboard=True, one_time_keyboard=True)

def kb_back_to_admin() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Admin Menu", callback_data='back_admin')]])

def kb_back_to_reseller() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 My Menu", callback_data='back_reseller')]])

def kb_confirm(yes_data: str, no_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirm", callback_data=yes_data),
            InlineKeyboardButton("❌ Cancel",  callback_data=no_data),
        ]
    ])

def kb_paginated_clients_admin(clients: dict, page: int) -> InlineKeyboardMarkup:
    """Builds a paginated inline keyboard for admin client list."""
    keys = list(clients.keys())
    total_pages = max(1, (len(keys) + PAGE_SIZE - 1) // PAGE_SIZE)
    start = page * PAGE_SIZE
    page_keys = keys[start:start + PAGE_SIZE]

    buttons = []
    for uid in page_keys:
        c = clients[uid]
        icon = "✅" if c.get('status') == 'Paid' else "🚫"
        label = f"{icon} {c.get('name', uid)[:18]}"
        buttons.append([InlineKeyboardButton(label, callback_data=f'admin_client_detail_{uid}')])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f'admin_clients_{page-1}'))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data='noop'))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f'admin_clients_{page+1}'))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton("🔙 Admin Menu", callback_data='back_admin')])
    return InlineKeyboardMarkup(buttons)

def kb_paginated_clients_reseller(clients: dict, page: int, reseller_id: str) -> InlineKeyboardMarkup:
    keys = list(clients.keys())
    total_pages = max(1, (len(keys) + PAGE_SIZE - 1) // PAGE_SIZE)
    start = page * PAGE_SIZE
    page_keys = keys[start:start + PAGE_SIZE]

    buttons = []
    for uid in page_keys:
        c = clients[uid]
        icon = "✅" if c.get('status') == 'Paid' else "🚫"
        label = f"{icon} {c.get('name', uid)[:18]}"
        buttons.append([InlineKeyboardButton(label, callback_data=f'res_client_detail_{uid}')])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f'res_list_{page-1}'))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data='noop'))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f'res_list_{page+1}'))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton("🔙 My Menu", callback_data='back_reseller')])
    return InlineKeyboardMarkup(buttons)

def kb_paginated_resellers(resellers: dict, page: int) -> InlineKeyboardMarkup:
    keys = list(resellers.keys())
    total_pages = max(1, (len(keys) + PAGE_SIZE - 1) // PAGE_SIZE)
    start = page * PAGE_SIZE
    page_keys = keys[start:start + PAGE_SIZE]

    buttons = []
    for rid in page_keys:
        r = resellers[rid]
        icon = "✅" if r.get('active', True) else "⛔"
        label = f"{icon} {r.get('name', rid)[:18]}"
        buttons.append([InlineKeyboardButton(label, callback_data=f'admin_res_detail_{rid}')])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f'admin_resellers_{page-1}'))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data='noop'))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f'admin_resellers_{page+1}'))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton("🔙 Admin Menu", callback_data='back_admin')])
    return InlineKeyboardMarkup(buttons)

def kb_paginated_library(library: dict, page: int) -> InlineKeyboardMarkup:
    keys = list(library.keys())
    total_pages = max(1, (len(keys) + PAGE_SIZE - 1) // PAGE_SIZE)
    start = page * PAGE_SIZE
    page_keys = keys[start:start + PAGE_SIZE]

    buttons = []
    for key in page_keys:
        item = library[key]
        label = f"🗂 {item.get('name', key)[:20]}"
        buttons.append([
            InlineKeyboardButton(label,       callback_data='noop'),
            InlineKeyboardButton("🗑 Del",    callback_data=f'admin_lib_del_{key}'),
        ])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f'admin_library_{page-1}'))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data='noop'))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f'admin_library_{page+1}'))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton("➕ Add Source",    callback_data='admin_add_lib')])
    buttons.append([InlineKeyboardButton("🔙 Admin Menu",    callback_data='back_admin')])
    return InlineKeyboardMarkup(buttons)


# ===========================================================================
# MODULE 5: HELPER UTILITIES
# ===========================================================================

def is_cancel(text: str) -> bool:
    return text.strip().lower() in ['❌ cancel', '/cancel', 'cancel']

async def send_admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends/edits message to show admin dashboard."""
    text = "🖥️ *MITV ADMIN DASHBOARD*\nSelect an action:"
    if update.callback_query:
        try:
            await update.callback_query.message.edit_text(
                text, reply_markup=kb_admin_menu(), parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            await update.callback_query.message.reply_photo(
                photo=BANNER_IMG, caption=text,
                reply_markup=kb_admin_menu(), parse_mode=ParseMode.MARKDOWN
            )
    else:
        await update.message.reply_photo(
            photo=BANNER_IMG, caption=text,
            reply_markup=kb_admin_menu(), parse_mode=ParseMode.MARKDOWN
        )

async def send_reseller_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends/edits message to show reseller dashboard."""
    name = context.user_data.get('reseller_name', 'Reseller')
    text = f"📱 *RESELLER PORTAL*\nWelcome, {name}!\nSelect an action:"
    if update.callback_query:
        try:
            await update.callback_query.message.edit_text(
                text, reply_markup=kb_reseller_menu(), parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            await update.callback_query.message.reply_text(
                text, reply_markup=kb_reseller_menu(), parse_mode=ParseMode.MARKDOWN
            )
    else:
        await update.message.reply_text(
            text, reply_markup=kb_reseller_menu(), parse_mode=ParseMode.MARKDOWN
        )

def format_timestamp(ms: int) -> str:
    """Converts millisecond timestamp to readable string."""
    try:
        return datetime.fromtimestamp(ms / 1000).strftime('%d %b %Y, %I:%M %p')
    except Exception:
        return "Unknown"


# ===========================================================================
# MODULE 6: COMMAND HANDLERS
# ===========================================================================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point. Clears state and shows the role selection screen."""
    context.user_data.clear()

    caption = (
        "🚀 *MITV NETWORK OS — BOOT COMPLETE*\n\n"
        "Welcome to the official *MiTV Management System*.\n"
        "_Powered by MUSLIM ISLAM & MI AI Core_\n\n"
        "Please select your authorization role:"
    )

    if update.message:
        try:
            await update.message.reply_animation(
                animation=WELCOME_GIF,
                caption=caption,
                reply_markup=kb_main_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            # Fallback if GIF fails
            await update.message.reply_photo(
                photo=BANNER_IMG,
                caption=caption,
                reply_markup=kb_main_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
    elif update.callback_query:
        await update.callback_query.message.reply_photo(
            photo=BANNER_IMG,
            caption=caption,
            reply_markup=kb_main_menu(),
            parse_mode=ParseMode.MARKDOWN
        )
        try:
            await update.callback_query.message.delete()
        except Exception:
            pass

    return ROLE_SELECT


async def handle_role_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Routes user based on selected role."""
    query = update.callback_query
    await query.answer()

    if query.data == 'role_admin':
        await query.message.reply_text(
            "🔐 *ADMIN AUTHENTICATION*\n\nEnter the Super Admin Password:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_cancel()
        )
        return ADMIN_LOGIN

    elif query.data == 'role_reseller':
        await query.message.reply_text(
            "📱 *RESELLER PORTAL*\n\nEnter your registered Phone Number:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_cancel()
        )
        return RESELLER_PHONE

    elif query.data == 'role_ai':
        context.user_data['ai_history'] = []
        await query.message.reply_text(
            "🧠 *MI AI ONLINE*\n\n"
            "Assalam o Alaikum! Main *MI AI* hoon — MiTV Network ka official AI assistant.\n"
            "Kuch bhi poochh saktay hain! Python, Firebase, IPTV, business — sab.\n\n"
            "_/exit ya /start se wapas jayen._",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove()
        )
        return AI_CHAT_MODE

    return ROLE_SELECT


# ===========================================================================
# MODULE 7: ADMIN AUTHENTICATION
# ===========================================================================

async def handle_admin_login(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text

    if is_cancel(text):
        await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
        await cmd_start(update, context)
        return ROLE_SELECT

    if text == ADMIN_PASSWORD:
        context.user_data['role'] = 'admin'
        await update.message.reply_text("✅ Authenticated!", reply_markup=ReplyKeyboardRemove())
        await send_admin_dashboard(update, context)
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "❌ *Wrong password.* Try again or press Cancel.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_cancel()
        )
        return ADMIN_LOGIN


# ===========================================================================
# MODULE 8: ADMIN DASHBOARD CALLBACKS
# ===========================================================================

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Master handler for all admin dashboard interactions."""
    query = update.callback_query
    await query.answer()
    data = query.data

    # Ensure admin role
    if context.user_data.get('role') != 'admin' and data not in ['back_admin']:
        await query.message.reply_text("⚠️ Session expired. Please /start again.")
        return

    # --- ANALYTICS ---
    if data == 'admin_stats':
        stats = DB.get_system_stats()
        text = (
            "📊 *NETWORK ANALYTICS — LIVE*\n\n"
            f"👥 Total Subscribers : `{stats['total']}`\n"
            f"✅ Paid / Active      : `{stats['paid']}`\n"
            f"🚫 Blocked            : `{stats['blocked']}`\n"
            f"🟢 Live Streaming Now : `{stats['live']}` nodes\n"
            f"📚 M3U Library        : `{stats['library']}` sources\n"
            f"🧑‍🤝‍🧑 Resellers         : `{stats['resellers']}`\n\n"
            f"🕐 Synced: `{datetime.now().strftime('%I:%M %p')}`"
        )
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb_admin_menu())

    # --- LIVE TRACKING ---
    elif data == 'admin_track':
        logs = DB.get_all_live_logs(15)
        if not logs:
            text = "🛰️ *LIVE MATRIX*\n\nNo active streams detected."
        else:
            text = "🛰️ *LIVE STREAM MATRIX* (Last 15 events)\n\n"
            for log in logs:
                uid      = log.get('_uid', 'Unknown')
                channel  = log.get('channel', 'Unknown')
                ip       = log.get('ip', '—')
                log_time = log.get('time', log.get('timestamp', ''))
                text += f"📡 `{uid}`\n   ▶ {channel} | `{ip}`\n   🕐 {log_time}\n\n"
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb_admin_menu())

    # --- ALL CLIENTS PAGINATED ---
    elif data.startswith('admin_clients_'):
        page = int(data.split('_')[-1])
        clients = DB.get_all_clients()
        if not clients:
            await query.message.reply_text("No clients found.", reply_markup=kb_back_to_admin())
            return
        text = f"👥 *ALL SUBSCRIBERS* ({len(clients)} total)\nSelect to manage:"
        await query.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_paginated_clients_admin(clients, page)
        )

    # --- CLIENT DETAIL (Admin) ---
    elif data.startswith('admin_client_detail_'):
        uid = data[len('admin_client_detail_'):]
        user = DB.get_all_clients().get(uid)
        if not user:
            await query.message.reply_text("Client not found.", reply_markup=kb_back_to_admin())
            return

        playlist = DB.get_active_playlist(uid) or {}
        sources_count = len(playlist.get('sources', []))
        logs = DB.get_user_logs(uid, 5)

        text = (
            f"👤 *CLIENT DETAIL*\n\n"
            f"🆔 UID    : `{uid}`\n"
            f"📛 Name   : {user.get('name','—')}\n"
            f"📞 Phone  : {user.get('phone','—')}\n"
            f"📶 Status : {'✅ Paid' if user.get('status')=='Paid' else '🚫 Blocked'}\n"
            f"🔗 M3U    : `{VERCEL_BASE}{uid}`\n"
            f"📦 Sources: `{sources_count}` injected\n"
            f"📅 Created: {format_timestamp(user.get('created_at',0))}\n\n"
        )

        if logs:
            text += "📺 *Last 5 Stream Events:*\n"
            for log in logs:
                text += f"  ▶ {log.get('channel','?')} | `{log.get('ip','—')}`\n"

        status = user.get('status', 'Paid')
        toggle_label = "🔴 Block User" if status == 'Paid' else "🟢 Unblock User"
        keyboard = [
            [InlineKeyboardButton(toggle_label, callback_data=f'admin_toggle_{uid}_{status}')],
            [InlineKeyboardButton("🗑 Delete Client", callback_data=f'admin_del_client_{uid}')],
            [InlineKeyboardButton("📺 Full Logs",     callback_data=f'admin_full_logs_{uid}')],
            [InlineKeyboardButton("🔙 Back",          callback_data='admin_clients_0')],
        ]
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                       reply_markup=InlineKeyboardMarkup(keyboard))

    # --- TOGGLE CLIENT (Admin) ---
    elif data.startswith('admin_toggle_'):
        parts = data.split('_')
        uid    = parts[2]
        status = parts[3]
        # We need reseller_id — look it up from master_users
        all_users = DB.get_all_clients()
        user = all_users.get(uid, {})
        res_id = user.get('reseller_id', 'UNKNOWN')
        new_status = DB.toggle_client_status(res_id, uid, status)
        await query.message.reply_text(
            f"✅ `{uid}` status changed to *{new_status}*.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_back_to_admin()
        )

    # --- DELETE CLIENT (Admin) ---
    elif data.startswith('admin_del_client_'):
        uid = data[len('admin_del_client_'):]
        all_users = DB.get_all_clients()
        user = all_users.get(uid, {})
        res_id = user.get('reseller_id', 'UNKNOWN')
        name = user.get('name', uid)
        await query.message.reply_text(
            f"⚠️ Delete *{name}* (`{uid}`) permanently?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_confirm(f'admin_del_confirm_{uid}_{res_id}', 'admin_clients_0')
        )

    elif data.startswith('admin_del_confirm_'):
        parts = data.split('_')
        uid    = parts[3]
        res_id = parts[4]
        DB.delete_client(res_id, uid)
        await query.message.reply_text(
            f"✅ Client `{uid}` fully purged from all Firebase nodes.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_back_to_admin()
        )

    # --- FULL LOGS (Admin) ---
    elif data.startswith('admin_full_logs_'):
        uid = data[len('admin_full_logs_'):]
        logs = DB.get_user_logs(uid, 20)
        if not logs:
            text = f"📺 *STREAM LOGS* — `{uid}`\n\nNo logs found."
        else:
            text = f"📺 *STREAM LOGS* — `{uid}` ({len(logs)} events)\n\n"
            for log in logs:
                text += (f"  ▶ {log.get('channel','Unknown')}\n"
                         f"     IP: `{log.get('ip','—')}` | "
                         f"Time: {log.get('time', log.get('timestamp','—'))}\n")
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                       reply_markup=kb_back_to_admin())

    # --- RESELLERS PAGINATED ---
    elif data.startswith('admin_resellers_'):
        page = int(data.split('_')[-1])
        resellers = DB.get_all_resellers()
        if not resellers:
            await query.message.reply_text("No resellers found.", reply_markup=kb_back_to_admin())
            return
        text = f"🧑‍🤝‍🧑 *RESELLERS* ({len(resellers)} total)"
        await query.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_paginated_resellers(resellers, page)
        )

    # --- RESELLER DETAIL ---
    elif data.startswith('admin_res_detail_'):
        rid = data[len('admin_res_detail_'):]
        res = DB.get_reseller(rid)
        if not res:
            await query.message.reply_text("Reseller not found.", reply_markup=kb_back_to_admin())
            return
        # Count clients
        clients = DB.get_clients_by_reseller(rid)
        text = (
            f"🧑‍💼 *RESELLER DETAIL*\n\n"
            f"🆔 ID      : `{rid}`\n"
            f"📛 Name    : {res.get('name','—')}\n"
            f"📞 Phone   : {res.get('number','—')}\n"
            f"🔑 Password: `{res.get('password','—')}`\n"
            f"📶 Status  : {'✅ Active' if res.get('active', True) else '⛔ Disabled'}\n"
            f"👥 Clients : `{len(clients)}`\n"
            f"📅 Created : {format_timestamp(res.get('created_at', 0))}"
        )
        active = res.get('active', True)
        toggle_label = "⛔ Disable Reseller" if active else "✅ Enable Reseller"
        keyboard = [
            [InlineKeyboardButton(toggle_label,       callback_data=f'admin_toggle_res_{rid}')],
            [InlineKeyboardButton("🗑 Delete Reseller", callback_data=f'admin_del_res_{rid}')],
            [InlineKeyboardButton("🔙 Back",           callback_data='admin_resellers_0')],
        ]
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                       reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith('admin_toggle_res_'):
        rid = data[len('admin_toggle_res_'):]
        new_state = DB.toggle_reseller_status(rid)
        status_text = "✅ Enabled" if new_state else "⛔ Disabled"
        await query.message.reply_text(
            f"Reseller `{rid}` is now *{status_text}*.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_back_to_admin()
        )

    elif data.startswith('admin_del_res_'):
        rid = data[len('admin_del_res_'):]
        res = DB.get_reseller(rid)
        name = res.get('name', rid) if res else rid
        await query.message.reply_text(
            f"⚠️ Delete reseller *{name}* (`{rid}`)?\nNote: Their clients will remain.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_confirm(f'admin_del_res_confirm_{rid}', 'admin_resellers_0')
        )

    elif data.startswith('admin_del_res_confirm_'):
        rid = data[len('admin_del_res_confirm_'):]
        DB.delete_reseller(rid)
        await query.message.reply_text(
            f"✅ Reseller `{rid}` deleted.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_back_to_admin()
        )

    # --- LIBRARY MANAGEMENT ---
    elif data.startswith('admin_library_'):
        page = int(data.split('_')[-1])
        library = DB.get_library()
        if not library:
            text = "📚 *PLAYLIST LIBRARY*\n\nLibrary is empty. Add some sources!"
        else:
            text = f"📚 *PLAYLIST LIBRARY* ({len(library)} sources)"
        await query.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_paginated_library(library, page) if library else
            InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add Source", callback_data='admin_add_lib')],
                [InlineKeyboardButton("🔙 Admin Menu", callback_data='back_admin')]
            ])
        )

    elif data.startswith('admin_lib_del_'):
        key = data[len('admin_lib_del_'):]
        DB.delete_library_source(key)
        await query.answer("✅ Source deleted!", show_alert=True)
        library = DB.get_library()
        text = f"📚 *LIBRARY* ({len(library)} sources)"
        await query.message.edit_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_paginated_library(library, 0) if library else
            InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add Source", callback_data='admin_add_lib')],
                [InlineKeyboardButton("🔙 Admin Menu", callback_data='back_admin')]
            ])
        )

    # --- NOTIFICATION LIST ---
    elif data == 'admin_notif_list':
        notifs = DB.get_recent_notifications(5)
        if not notifs:
            text = "🔔 No notifications sent yet."
        else:
            text = "🔔 *RECENT NOTIFICATIONS*\n\n"
            for n in notifs:
                ts = format_timestamp(n.get('timestamp', 0))
                text += f"📌 *{n.get('title','—')}*\n{n.get('description','')[:80]}...\n🕐 {ts}\n\n"
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb_back_to_admin())

    # --- BACK TO ADMIN ---
    elif data == 'back_admin':
        context.user_data['role'] = 'admin'
        await send_admin_dashboard(update, context)

    # --- LOGOUT ---
    elif data == 'logout':
        context.user_data.clear()
        await query.message.reply_text("👋 Logged out.", reply_markup=ReplyKeyboardRemove())
        await cmd_start(update, context)


# ===========================================================================
# MODULE 9: ADMIN — ADD RESELLER FLOW
# ===========================================================================

async def admin_add_res_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "➕ *ADD RESELLER*\n\nEnter the full name:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb_cancel()
    )
    return ADMIN_ADD_RES_NAME

async def admin_add_res_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel(update.message.text):
        await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
        await send_admin_dashboard(update, context)
        return ConversationHandler.END
    context.user_data['new_res_name'] = update.message.text.strip()
    await update.message.reply_text("Enter Phone Number:")
    return ADMIN_ADD_RES_PHONE

async def admin_add_res_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel(update.message.text):
        await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
        await send_admin_dashboard(update, context)
        return ConversationHandler.END
    context.user_data['new_res_phone'] = update.message.text.strip()
    await update.message.reply_text("Enter a secure Password:")
    return ADMIN_ADD_RES_PASS

async def admin_add_res_pass(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel(update.message.text):
        await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
        await send_admin_dashboard(update, context)
        return ConversationHandler.END

    name  = context.user_data.get('new_res_name')
    phone = context.user_data.get('new_res_phone')
    pwd   = update.message.text.strip()

    try:
        rid = DB.add_reseller(name, phone, pwd)
        await update.message.reply_text(
            f"✅ *Reseller Created!*\n\n"
            f"🆔 ID       : `{rid}`\n"
            f"📛 Name     : {name}\n"
            f"📞 Phone    : {phone}\n"
            f"🔑 Password : `{pwd}`\n\n"
            f"_Share these credentials with the reseller._",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove()
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Firebase Error: {e}", reply_markup=ReplyKeyboardRemove())

    await send_admin_dashboard(update, context)
    return ConversationHandler.END


# ===========================================================================
# MODULE 10: ADMIN — NOTIFICATION FLOW
# ===========================================================================

async def admin_notif_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "📢 *PUSH NOTIFICATION*\n\nEnter the notification title:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb_cancel()
    )
    return ADMIN_NOTIF_TITLE

async def admin_notif_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel(update.message.text):
        await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
        await send_admin_dashboard(update, context)
        return ConversationHandler.END
    context.user_data['notif_title'] = update.message.text.strip()
    await update.message.reply_text("Enter the description/body text:")
    return ADMIN_NOTIF_DESC

async def admin_notif_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel(update.message.text):
        await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
        await send_admin_dashboard(update, context)
        return ConversationHandler.END
    context.user_data['notif_desc'] = update.message.text.strip()
    await update.message.reply_text(
        "Enter an image URL (optional) or type `skip`:",
        parse_mode=ParseMode.MARKDOWN
    )
    return ADMIN_NOTIF_IMG

async def admin_notif_img(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel(update.message.text):
        await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
        await send_admin_dashboard(update, context)
        return ConversationHandler.END

    img_text = update.message.text.strip()
    img_url  = "" if img_text.lower() == 'skip' else img_text

    title = context.user_data.get('notif_title', '')
    desc  = context.user_data.get('notif_desc', '')

    success = DB.push_notification(title, desc, img_url)
    if success:
        await update.message.reply_text(
            f"✅ *Notification Sent!*\n\n"
            f"📌 Title: {title}\n"
            f"📝 Body : {desc[:80]}\n"
            f"🖼 Image: {img_url or 'None'}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        await update.message.reply_text("❌ Failed to push notification.", reply_markup=ReplyKeyboardRemove())

    await send_admin_dashboard(update, context)
    return ConversationHandler.END


# ===========================================================================
# MODULE 11: ADMIN — ADD LIBRARY SOURCE FLOW
# ===========================================================================

async def admin_add_lib_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "📚 *ADD LIBRARY SOURCE*\n\nEnter a name/label for this source:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb_cancel()
    )
    return ADMIN_LIB_NAME

async def admin_lib_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel(update.message.text):
        await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
        await send_admin_dashboard(update, context)
        return ConversationHandler.END
    context.user_data['lib_name'] = update.message.text.strip()
    await update.message.reply_text("Enter the M3U/M3U8 URL:")
    return ADMIN_LIB_URL

async def admin_lib_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel(update.message.text):
        await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
        await send_admin_dashboard(update, context)
        return ConversationHandler.END

    url = update.message.text.strip()
    if not url.startswith('http'):
        await update.message.reply_text("❌ URL must start with http or https. Try again:")
        return ADMIN_LIB_URL

    name = context.user_data.get('lib_name', 'Unnamed')
    try:
        key = DB.add_library_source(name, url)
        await update.message.reply_text(
            f"✅ *Source Added to Library!*\n\n"
            f"📛 Name : {name}\n"
            f"🔗 URL  : `{url}`\n"
            f"🔑 Key  : `{key}`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove()
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", reply_markup=ReplyKeyboardRemove())

    await send_admin_dashboard(update, context)
    return ConversationHandler.END


# ===========================================================================
# MODULE 12: RESELLER AUTHENTICATION
# ===========================================================================

async def reseller_enter_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel(update.message.text):
        await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
        await cmd_start(update, context)
        return ROLE_SELECT
    context.user_data['res_phone'] = update.message.text.strip()
    await update.message.reply_text("🔐 Enter your Password:")
    return RESELLER_PASS

async def reseller_enter_pass(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel(update.message.text):
        await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
        await cmd_start(update, context)
        return ROLE_SELECT

    phone = context.user_data.get('res_phone', '')
    pwd   = update.message.text.strip()
    res   = DB.authenticate_reseller(phone, pwd)

    if res:
        context.user_data['role']          = 'reseller'
        context.user_data['reseller_id']   = res['id']
        context.user_data['reseller_name'] = res.get('name', 'Reseller')
        await update.message.reply_text(
            f"✅ *Login Successful!*\n\nWelcome, *{res.get('name')}*!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardRemove()
        )
        await send_reseller_dashboard(update, context)
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "❌ *Invalid credentials.* Try again or press Cancel.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_cancel()
        )
        return RESELLER_PHONE


# ===========================================================================
# MODULE 13: RESELLER DASHBOARD CALLBACKS
# ===========================================================================

async def reseller_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Master handler for all reseller dashboard interactions."""
    query = update.callback_query
    await query.answer()
    data  = query.data
    rid   = context.user_data.get('reseller_id')

    if not rid and data not in ['back_reseller', 'logout']:
        await query.message.reply_text("⚠️ Session expired. Please /start again.")
        return

    # --- STATS ---
    if data == 'res_stats':
        clients = DB.get_clients_by_reseller(rid)
        total   = len(clients)
        paid    = sum(1 for c in clients.values() if c.get('status') == 'Paid')
        blocked = total - paid
        name    = context.user_data.get('reseller_name', rid)
        text = (
            f"📊 *YOUR NETWORK STATS*\n\n"
            f"👤 Reseller    : {name}\n"
            f"🆔 ID          : `{rid}`\n\n"
            f"👥 Total Clients: `{total}`\n"
            f"✅ Paid         : `{paid}`\n"
            f"🚫 Blocked      : `{blocked}`"
        )
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                       reply_markup=kb_reseller_menu())

    # --- CLIENT LIST PAGINATED ---
    elif data.startswith('res_list_'):
        page    = int(data.split('_')[-1])
        clients = DB.get_clients_by_reseller(rid)
        if not clients:
            await query.message.reply_text("You have no clients yet.", reply_markup=kb_reseller_menu())
            return
        text = f"📋 *YOUR CLIENTS* ({len(clients)} total)"
        await query.message.reply_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_paginated_clients_reseller(clients, page, rid)
        )

    # --- CLIENT DETAIL ---
    elif data.startswith('res_client_detail_'):
        uid     = data[len('res_client_detail_'):]
        clients = DB.get_clients_by_reseller(rid)
        client  = clients.get(uid)
        if not client:
            await query.message.reply_text("Client not found.", reply_markup=kb_reseller_menu())
            return

        playlist      = DB.get_active_playlist(uid) or {}
        sources_count = len(playlist.get('sources', []))
        m3u_link      = f"{VERCEL_BASE}{uid}"

        text = (
            f"👤 *CLIENT DETAIL*\n\n"
            f"🆔 UID    : `{uid}`\n"
            f"📛 Name   : {client.get('name','—')}\n"
            f"📞 Phone  : {client.get('phone','—')}\n"
            f"📶 Status : {'✅ Paid' if client.get('status')=='Paid' else '🚫 Blocked'}\n"
            f"🔗 M3U    : `{m3u_link}`\n"
            f"📦 Sources: `{sources_count}` injected\n"
            f"📅 Added  : {format_timestamp(client.get('time', 0))}"
        )
        status        = client.get('status', 'Paid')
        toggle_label  = "🔴 Block" if status == 'Paid' else "🟢 Unblock"
        wa_link       = f"https://wa.me/{client.get('phone', '')}?text=Assalam%20o%20Alaikum!"

        keyboard = [
            [InlineKeyboardButton(toggle_label,         callback_data=f'res_toggle_{uid}_{status}')],
            [InlineKeyboardButton("🔗 Copy M3U",        callback_data=f'res_copy_m3u_{uid}')],
            [InlineKeyboardButton("📲 WhatsApp Client", url=wa_link)],
            [InlineKeyboardButton("🗑 Delete",          callback_data=f'res_del_client_{uid}')],
            [InlineKeyboardButton("🔙 Back",            callback_data='res_list_0')],
        ]
        await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN,
                                       reply_markup=InlineKeyboardMarkup(keyboard))

    # --- TOGGLE STATUS (Reseller) ---
    elif data.startswith('res_toggle_'):
        parts  = data.split('_')
        uid    = parts[2]
        status = parts[3]
        new_status = DB.toggle_client_status(rid, uid, status)
        await query.answer(f"Status: {new_status}", show_alert=True)
        # Refresh the detail view
        clients = DB.get_clients_by_reseller(rid)
        client  = clients.get(uid, {})
        m3u_link = f"{VERCEL_BASE}{uid}"
        text = (
            f"👤 *CLIENT DETAIL*\n\n"
            f"🆔 UID : `{uid}`\n"
            f"📛 Name: {client.get('name','—')}\n"
            f"📶 Status: {'✅ Paid' if new_status=='Paid' else '🚫 Blocked'}\n"
            f"🔗 M3U : `{m3u_link}`"
        )
        toggle_label = "🔴 Block" if new_status == 'Paid' else "🟢 Unblock"
        wa_link = f"https://wa.me/{client.get('phone', '')}?text=Assalam%20o%20Alaikum!"
        keyboard = [
            [InlineKeyboardButton(toggle_label,        callback_data=f'res_toggle_{uid}_{new_status}')],
            [InlineKeyboardButton("📲 WhatsApp",       url=wa_link)],
            [InlineKeyboardButton("🗑 Delete",         callback_data=f'res_del_client_{uid}')],
            [InlineKeyboardButton("🔙 Back",           callback_data='res_list_0')],
        ]
        await query.message.edit_text(text, parse_mode=ParseMode.MARKDOWN,
                                      reply_markup=InlineKeyboardMarkup(keyboard))

    # --- COPY M3U ---
    elif data.startswith('res_copy_m3u_'):
        uid = data[len('res_copy_m3u_'):]
        m3u = f"{VERCEL_BASE}{uid}"
        await query.message.reply_text(
            f"🔗 *M3U Endpoint:*\n`{m3u}`\n\n_Copy the link above._",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_back_to_reseller()
        )

    # --- DELETE CLIENT (Reseller) ---
    elif data.startswith('res_del_client_'):
        uid  = data[len('res_del_client_'):]
        name = DB.get_client(rid, uid)
        label = name.get('name', uid) if name else uid
        await query.message.reply_text(
            f"⚠️ Delete *{label}*?\nThis cannot be undone.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_confirm(f'res_del_confirm_{uid}', 'res_list_0')
        )

    elif data.startswith('res_del_confirm_'):
        uid = data[len('res_del_confirm_'):]
        DB.delete_client(rid, uid)
        await query.message.reply_text(
            f"✅ Client `{uid}` deleted.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb_reseller_menu()
        )

    # --- BACK TO RESELLER ---
    elif data == 'back_reseller':
        await send_reseller_dashboard(update, context)

    # --- LOGOUT ---
    elif data == 'logout':
        context.user_data.clear()
        await query.message.reply_text("👋 Logged out.", reply_markup=ReplyKeyboardRemove())
        await cmd_start(update, context)


# ===========================================================================
# MODULE 14: RESELLER — ADD CLIENT FLOW
# ===========================================================================

async def res_add_client_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "➕ *ADD NEW CLIENT*\n\nEnter client's full name:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb_cancel()
    )
    return RES_ADD_CLIENT_NAME

async def res_add_client_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel(update.message.text):
        await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
        await send_reseller_dashboard(update, context)
        return ConversationHandler.END
    context.user_data['client_name'] = update.message.text.strip()
    await update.message.reply_text("Enter client's WhatsApp/Phone Number:")
    return RES_ADD_CLIENT_PHONE

async def res_add_client_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_cancel(update.message.text):
        await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
        await send_reseller_dashboard(update, context)
        return ConversationHandler.END

    phone = update.message.text.strip()
    name  = context.user_data.get('client_name', 'Client')
    rid   = context.user_data.get('reseller_id')

    loading_msg = await update.message.reply_text(
        "⏳ *Deploying to Firebase & injecting M3U library...*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove()
    )
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='upload_document')

    try:
        client_data = DB.create_client(rid, name, phone)
        uid         = client_data['uid']
        m3u         = client_data['m3u']

        await loading_msg.delete()

        # Success message
        await update.message.reply_text(
            f"✅ *CLIENT DEPLOYED SUCCESSFULLY!*\n\n"
            f"🆔 UID  : `{uid}`\n"
            f"📛 Name : {name}\n"
            f"📞 Phone: {phone}\n"
            f"🔗 M3U  : `{m3u}`\n\n"
            f"👇 *COPY MESSAGE BELOW TO SEND CLIENT:*",
            parse_mode=ParseMode.MARKDOWN
        )

        # WhatsApp post
        post = PostGenerator.activation_post(name, phone, m3u, uid)
        await update.message.reply_text(post, parse_mode=ParseMode.MARKDOWN)

        # Action buttons
        wa_link = f"https://wa.me/{phone}?text=Assalam%20o%20Alaikum!"
        keyboard = [
            [InlineKeyboardButton("📲 Open WhatsApp", url=wa_link)],
            [InlineKeyboardButton("🔙 My Menu",        callback_data='back_reseller')],
        ]
        await update.message.reply_photo(
            photo=SUCCESS_IMG,
            caption="Client successfully added to MiTV Network.",
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
# MODULE 15: AI CHAT MODE
# ===========================================================================

async def handle_ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles freeform AI conversation with Groq LLaMA-3."""
    user_text = update.message.text

    if user_text.lower() in ['/exit', '/start', '❌ cancel']:
        await update.message.reply_text("MI AI offline. Returning to main menu...",
                                        reply_markup=ReplyKeyboardRemove())
        await cmd_start(update, context)
        return ROLE_SELECT

    # Typing indicator
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

    history  = context.user_data.get('ai_history', [])
    response = await MI_AI.respond(user_text, history)

    # Update history
    history.append({"role": "user",      "content": user_text})
    history.append({"role": "assistant", "content": response})
    context.user_data['ai_history'] = history[-20:]  # Keep last 20 messages

    try:
        await update.message.reply_text(
            f"🧠 *MI AI:*\n\n{response}",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        # Markdown parse fail fallback
        await update.message.reply_text(f"🧠 MI AI:\n\n{response}")

    return AI_CHAT_MODE


# ===========================================================================
# MODULE 16: FLOATING CALLBACK ROUTER
# ===========================================================================

async def floating_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles callbacks that fire outside of strict ConversationHandler states.
    Routes to the appropriate trigger function.
    """
    query = update.callback_query
    data  = query.data

    if data == 'admin_add_res':
        await admin_add_res_trigger(update, context)
        return ADMIN_ADD_RES_NAME

    elif data == 'admin_notif':
        await admin_notif_trigger(update, context)
        return ADMIN_NOTIF_TITLE

    elif data == 'admin_add_lib':
        await admin_add_lib_trigger(update, context)
        return ADMIN_LIB_NAME

    elif data == 'res_add_client':
        await res_add_client_trigger(update, context)
        return RES_ADD_CLIENT_NAME

    elif data == 'noop':
        await query.answer()

    # Route all other admin/reseller callbacks
    elif data.startswith('admin_') or data == 'back_admin':
        await admin_callback_handler(update, context)

    elif data.startswith('res_') or data == 'back_reseller':
        await reseller_callback_handler(update, context)

    elif data == 'logout':
        context.user_data.clear()
        await query.answer()
        await query.message.reply_text("👋 Logged out.", reply_markup=ReplyKeyboardRemove())
        await cmd_start(update, context)

    elif data.startswith('role_'):
        await handle_role_selection(update, context)


# ===========================================================================
# MODULE 17: STANDALONE COMMANDS
# ===========================================================================

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/stats command — quick network overview."""
    stats = DB.get_system_stats()
    text = (
        "📊 *MITV NETWORK STATS*\n\n"
        f"👥 Total : `{stats['total']}`\n"
        f"✅ Paid  : `{stats['paid']}`\n"
        f"🚫 Block : `{stats['blocked']}`\n"
        f"🟢 Live  : `{stats['live']}`\n"
        f"📚 Lib   : `{stats['library']}` sources\n"
        f"🧑‍🤝‍🧑 Res   : `{stats['resellers']}`"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/help command."""
    text = (
        "📖 *MITV BOT HELP*\n\n"
        "*/start*  — Main menu\n"
        "*/stats*  — Network stats\n"
        "*/help*   — This message\n"
        "*/exit*   — Exit AI mode\n\n"
        "🔐 *Admin Portal* — Full network management\n"
        "🧑‍💻 *Reseller Portal* — Client management\n"
        "🧠 *MI AI* — AI assistant powered by Groq LLaMA-3\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🏢 Project of: MUSLIM ISLAM\n"
        "👑 Founder: Muaaz Iqbal (Kasur)"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def cmd_exit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Resets conversation from any state."""
    context.user_data.clear()
    await update.message.reply_text("↩️ Resetting...", reply_markup=ReplyKeyboardRemove())
    await cmd_start(update, context)
    return ConversationHandler.END

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Global error logger."""
    logger.error(f"Unhandled exception: {context.error}", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ An internal error occurred. Please try /start again."
            )
        except Exception:
            pass


# ===========================================================================
# MODULE 18: APPLICATION BOOTSTRAP
# ===========================================================================

def main():
    """Builds and starts the bot application."""
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # -----------------------------------------------------------------------
    # MASTER CONVERSATION HANDLER
    # All multi-step forms are wired here as nested states.
    # -----------------------------------------------------------------------
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', cmd_start),
            CommandHandler('exit',  cmd_exit),
            CallbackQueryHandler(handle_role_selection, pattern='^role_'),
        ],
        states={
            ROLE_SELECT: [
                CallbackQueryHandler(handle_role_selection, pattern='^role_'),
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

            # Reseller: Add Client
            RES_ADD_CLIENT_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, res_add_client_name)
            ],
            RES_ADD_CLIENT_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, res_add_client_phone)
            ],

            # AI Chat (any text)
            AI_CHAT_MODE: [
                MessageHandler(filters.TEXT, handle_ai_chat)
            ],
        },
        fallbacks=[
            CommandHandler('start', cmd_start),
            CommandHandler('exit',  cmd_exit),
        ],
        allow_reentry=True,
        per_message=False,
    )

    # Attach master conversation handler
    app.add_handler(conv_handler)

    # -----------------------------------------------------------------------
    # FLOATING CALLBACK HANDLERS (for inline buttons outside strict states)
    # -----------------------------------------------------------------------
    app.add_handler(CallbackQueryHandler(floating_callback_router))

    # -----------------------------------------------------------------------
    # STANDALONE COMMANDS
    # -----------------------------------------------------------------------
    app.add_handler(CommandHandler('stats', cmd_stats))
    app.add_handler(CommandHandler('help',  cmd_help))

    # -----------------------------------------------------------------------
    # GLOBAL ERROR HANDLER
    # -----------------------------------------------------------------------
    app.add_error_handler(error_handler)

    # -----------------------------------------------------------------------
    # STARTUP BANNER
    # -----------------------------------------------------------------------
    print("\n" + "=" * 65)
    print("  🚀 MITV NETWORK OS — TELEGRAM BOT ENGINE v5.0")
    print("  🏢 Project   : MUSLIM ISLAM")
    print("  👑 Founder   : Muaaz Iqbal (Kasur, Punjab, Pakistan)")
    print("  🔥 Firebase  : ramadan-2385b")
    print("  🌐 Vercel    : mitv-tan.vercel.app")
    print(f"  🤖 Groq AI   : {'ONLINE' if MI_AI.active else 'OFFLINE (Set GROQ_API_KEY)'}")
    print("  📡 Bot Status: POLLING...")
    print("=" * 65 + "\n")

    app.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()


"""
=========================================================================================
📋 DEPLOYMENT CHECKLIST
=========================================================================================
1. firebase.json         — Place Service Account JSON in same directory as bot.py
2. GROQ_API_KEY          — Set as environment variable: export GROQ_API_KEY="gsk_..."
3. pip install -r requirements.txt
4. python bot.py

FIREBASE DB NODES USED:
  /master_users/{MITV-XXXXX}    — All subscribers
  /active_playlists/{MITV-XXXXX} — M3U engine data per user
  /clients/{RES-XXXXX}/{MITV-XXXXX} — Reseller-grouped snapshots
  /resellers/{RES-XXXXX}        — Reseller accounts
  /playlist_library/{push_id}   — Global M3U defaults
  /notifications/{push_id}      — App push notifications
  /user_logs/{MITV-XXXXX}/{log} — Stream tracking (written by Vercel api/m3u.js)
  /global_stats/{MITV-XXXXX}    — Aggregated stats

VERCEL ENDPOINT:
  https://mitv-tan.vercel.app/api/m3u?user=MITV-XXXXX
=========================================================================================
"""
