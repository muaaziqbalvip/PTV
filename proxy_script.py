import os
import subprocess
import time
import threading
import pyrebase
import requests

# ==========================================
# 1. FIREBASE CONFIGURATION
# ==========================================
firebase_config = {
    "apiKey": "AIzaSyBbnU8DkthpYQMHOLLyj6M0cc05qXfjMcw",
    "authDomain": "ramadan-2385b.firebaseapp.com",
    "databaseURL": "https://ramadan-2385b-default-rtdb.firebaseio.com",
    "projectId": "ramadan-2385b",
    "storageBucket": "ramadan-2385b.firebasestorage.app",
    "messagingSenderId": "882828936310",
    "appId": "1:882828936310:web:7f97b921031fe130fe4b57"
}

firebase = pyrebase.initialize_app(firebase_config)
db = firebase.database()

# ==========================================
# 2. PROXY CONFIGURATION
# ==========================================
PORT = 8443
DEFAULT_SECRET = "ee1234567890abcdef1234567890abcdef"
SECRET = os.getenv("TG_SECRET", DEFAULT_SECRET)

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================
def get_public_ip():
    try:
        return requests.get('https://api.ipify.org', timeout=10).text.strip()
    except:
        return "127.0.0.1"

def update_firebase_status(status, ip):
    link = f"tg://proxy?server={ip}&port={PORT}&secret={SECRET}"
    try:
        db.child("ProxyServerStatus").set({
            "status": status,
            "server_ip": ip,
            "port": PORT,
            "connect_link": link,
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
        })
        print(f"✅ Firebase Status Updated: {status}")
    except Exception as e:
        print(f"❌ Firebase DB Error: {e}")

def log_activity_to_firebase():
    while True:
        try:
            db.child("ProxyLogs").push({
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "event": "Server is Running (Active)",
                "system": "GitHub Actions Runner"
            })
        except:
            pass
        time.sleep(300)

# ==========================================
# 4. MAIN PROXY RUNNER (FIXED)
# ==========================================
def run_proxy():
    print("🚀 Setting up Fast Python MTProtoProxy...")
    
    # 1. Download proxy library
    if not os.path.exists("mtprotoproxy"):
        subprocess.run("git clone https://github.com/alexbers/mtprotoproxy.git", shell=True)

    public_ip = get_public_ip()
    update_firebase_status("ONLINE", public_ip)
    
    print(f"⚡ Proxy started on Port {PORT}")
    print(f"🔗 Connect Link: tg://proxy?server={public_ip}&port={PORT}&secret={SECRET}")

    # 2. --- THE FIX: Create config.py dynamically ---
    config_content = f"""
PORT = {PORT}
USERS = {{
    "admin": "{SECRET}"
}}
"""
    with open("mtprotoproxy/config.py", "w") as f:
        f.write(config_content)

    # 3. Run WITHOUT flags (It will automatically read config.py)
    cmd = "cd mtprotoproxy && python3 mtprotoproxy.py"
    
    try:
        process = subprocess.Popen(cmd, shell=True)
        time.sleep(19800) # 5.5 Hours
        process.terminate()
        update_firebase_status("RESTARTING...", public_ip)
    except Exception as e:
        print(f"❌ Proxy Crash Error: {e}")
        update_firebase_status("ERROR / OFFLINE", public_ip)

# ==========================================
# 5. EXECUTION
# ==========================================
if __name__ == "__main__":
    threading.Thread(target=log_activity_to_firebase, daemon=True).start()
    
    while True:
        run_proxy()
        print("🔄 Restarting Proxy Loop to maintain High Speed...")
        time.sleep(5)
