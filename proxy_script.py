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

# Agar GitHub Secrets fail ho jaye, toh ye default fake-TLS secret use hoga
# Hamesha "ee" se shuru karein for high speed & anti-blocking
DEFAULT_SECRET = "ee1234567890abcdef1234567890abcdef"
SECRET = os.getenv("TG_SECRET", DEFAULT_SECRET)

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================
def get_public_ip():
    """Server ka real public IP nikalta hai"""
    try:
        return requests.get('https://api.ipify.org', timeout=10).text.strip()
    except:
        return "127.0.0.1"

def update_firebase_status(status, ip):
    """Firebase Realtime DB par Live Status aur Link Update karta hai"""
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
    """Background mein history track karta hai (Har 5 minute)"""
    while True:
        try:
            db.child("ProxyLogs").push({
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "event": "Server is Running (Active)",
                "system": "GitHub Actions Runner"
            })
        except:
            pass
        time.sleep(300) # 5 Minutes wait

# ==========================================
# 4. MAIN PROXY RUNNER
# ==========================================
def run_proxy():
    print("🚀 Setting up Fast Python MTProtoProxy...")
    
    # Download proxy library (Sirf pehli baar)
    if not os.path.exists("mtprotoproxy"):
        subprocess.run("git clone https://github.com/alexbers/mtprotoproxy.git", shell=True)

    public_ip = get_public_ip()
    update_firebase_status("ONLINE", public_ip)
    
    print(f"⚡ Proxy started on Port {PORT}")
    print(f"🔗 Connect Link: tg://proxy?server={public_ip}&port={PORT}&secret={SECRET}")

    # Run command inside the mtprotoproxy folder
    # Ye python wali proxy sabse fast hai kyunki isme uvloop use hota hai
    cmd = f"cd mtprotoproxy && python3 mtprotoproxy.py -p {PORT} -s {SECRET}"
    
    try:
        process = subprocess.Popen(cmd, shell=True)
        
        # 5 Ghante 30 Minute tak lagatar chalega (GitHub limit cross hone se pehle auto-restart)
        time.sleep(19800) 
        
        process.terminate()
        update_firebase_status("RESTARTING...", public_ip)
    except Exception as e:
        print(f"❌ Proxy Crash Error: {e}")
        update_firebase_status("ERROR / OFFLINE", public_ip)

# ==========================================
# 5. EXECUTION
# ==========================================
if __name__ == "__main__":
    # 1. Background mein Firebase Tracker Start karo
    threading.Thread(target=log_activity_to_firebase, daemon=True).start()
    
    # 2. Main Proxy ko Hamesha Zinda (Alive) rakhne ka Loop
    while True:
        run_proxy()
        print("🔄 Restarting Proxy Loop to maintain High Speed...")
        time.sleep(5)
