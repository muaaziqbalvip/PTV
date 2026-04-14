import os
import subprocess
import time
import threading
import pyrebase
import requests
import secrets # Strong random secret ke liye

# ==========================================
# 1. CONFIGURATION
# ==========================================
DUCKDNS_DOMAIN = "miaiproxy" 
DUCKDNS_TOKEN = "Ce812ef5-13e1-4bbe-bc89-9bd6910c3d24"

PORT = 443 
# Hum ek 32-char ka strong random secret generate karenge
# Agar aap apna fix rakhna chahte hain toh 32 characters ka hex code dein
RAW_SECRET = secrets.token_hex(16) 
# Fake TLS ke liye 'ee' + RAW_SECRET + google.com ka hex
TLS_SECRET = f"ee{RAW_SECRET}7777772e676f6f676c652e636f6d"

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
# 2. UPDATERS
# ==========================================
def update_duckdns(ip):
    try:
        url = f"https://www.duckdns.org/update?domains={DUCKDNS_DOMAIN}&token={DUCKDNS_TOKEN}&ip={ip}"
        requests.get(url, timeout=10)
        print(f"🚀 DuckDNS Updated: {DUCKDNS_DOMAIN}.duckdns.org")
    except:
        print("❌ DuckDNS Error")

def update_firebase(status, ip):
    # Link mein hum Fake TLS wala lamba secret use karenge
    perm_link = f"tg://proxy?server={DUCKDNS_DOMAIN}.duckdns.org&port={PORT}&secret={TLS_SECRET}"
    db.child("ProxyServerStatus").update({
        "status": status,
        "server_ip": ip,
        "connect_link": perm_link,
        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
    })

# ==========================================
# 3. PROXY ENGINE
# ==========================================
def start_proxy():
    if not os.path.exists("mtprotoproxy"):
        subprocess.run("git clone https://github.com/alexbers/mtprotoproxy.git", shell=True)

    current_ip = requests.get('https://api.ipify.org').text
    update_duckdns(current_ip)
    update_firebase("ONLINE", current_ip)

    # CONFIG FIX: Server ko sirf 32 chars wala RAW_SECRET chahiye
    config_data = f"""
PORT = {PORT}
USERS = {{
    "admin": "{RAW_SECRET}"
}}
TLS_DOMAIN = "www.google.com"
"""
    with open("mtprotoproxy/config.py", "w") as f:
        f.write(config_data)

    print(f"⚡ Proxy LIVE on Port {PORT} with Strong Secret")
    
    # THE FIX: 'sudo' use kar rahe hain port 443 ki permission ke liye
    subprocess.run("cd mtprotoproxy && sudo python3 mtprotoproxy.py", shell=True)

if __name__ == "__main__":
    while True:
        try:
            start_proxy()
        except Exception as e:
            print(f"Restarting... {e}")
            time.sleep(10)
