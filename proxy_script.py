import os
import subprocess
import time
import threading
import pyrebase
import requests

# --- FIREBASE CONFIGURATION ---
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

# --- PROXY CONFIGURATION ---
PORT = 8443
# Fake TLS Secret (ee... + hex)
SECRET = os.getenv("TG_SECRET", "ee7f94110123456789abcdef0123456789")

def update_server_status(status, ip):
    """Firebase par server ka live status update karta hai"""
    data = {
        "status": status,
        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "server_ip": ip,
        "port": PORT
    }
    try:
        db.child("ProxyServerStatus").set(data)
        print("✅ Firebase Sync: Status Updated")
    except Exception as e:
        print(f"❌ Firebase Error: {e}")

def get_public_ip():
    try:
        return requests.get('https://api.ipify.org').text
    except:
        return "Unknown IP"

def start_proxy_server():
    """Ultra Fast MTG Proxy (Go version) download aur run karne ka logic"""
    print("🚀 Setting up Fast MTG Proxy...")
    if not os.path.exists("mtg-2.1.7-linux-amd64"):
        subprocess.run("wget -q https://github.com/9seconds/mtg/releases/download/v2.1.7/mtg-2.1.7-linux-amd64.tar.gz", shell=True)
        subprocess.run("tar -xzf mtg-2.1.7-linux-amd64.tar.gz", shell=True)

    cmd = f"./mtg-2.1.7-linux-amd64/mtg run {SECRET} -b 0.0.0.0:{PORT}"
    
    print(f"⚡ Proxy started on port {PORT}")
    public_ip = get_public_ip()
    update_server_status("ONLINE", public_ip)
    
    # Ye link aap Firebase se utha kar share kar sakte hain
    tg_link = f"tg://proxy?server={public_ip}&port={PORT}&secret={SECRET}"
    db.child("ProxyServerStatus").update({"connect_link": tg_link})
    print(f"🔗 Connect Link: {tg_link}")

    try:
        process = subprocess.Popen(cmd, shell=True)
        # 5.5 Hours tak chalega then graceful restart for GitHub Limits
        time.sleep(19800) 
        process.terminate()
        update_server_status("OFFLINE (Restarting...)", public_ip)
    except Exception as e:
        print(f"❌ Server Crash: {e}")
        update_server_status("ERROR", public_ip)

def monitor_activity():
    """Background thread jo har 5 minute mein check karega"""
    while True:
        time.sleep(300) # 5 mins
        try:
            # Note: Deep user tracking (messages) is encrypted by Telegram.
            # We log server health and active ping timestamp.
            db.child("ProxyLogs").push({
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "event": "Ping Alive",
                "system": "GitHub Actions Runner"
            })
        except:
            pass

if __name__ == "__main__":
    # Background monitoring start
    threading.Thread(target=monitor_activity, daemon=True).start()
    
    while True:
        start_proxy_server()
        print("🔄 Restarting Proxy Loop...")
        time.sleep(5)
