import os
import subprocess
import time
import threading
import pyrebase
import requests

# ==========================================
# 1. CONFIGURATION (DuckDNS & Proxy)
# ==========================================
DUCKDNS_DOMAIN = "miaiproxy" 
DUCKDNS_TOKEN = "Ce812ef5-13e1-4bbe-bc89-9bd6910c3d24"

PORT = 443 # Fast speed aur anti-block ke liye
# Fake TLS Secret (High Security + Fast)
SECRET = "ee0000000000000000000000000000000077777772e676f6f676c652e636f6d"

# Firebase Config
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
    """Naye IP ko aapke domain miaiproxy.duckdns.org par map karta hai"""
    try:
        url = f"https://www.duckdns.org/update?domains={DUCKDNS_DOMAIN}&token={DUCKDNS_TOKEN}&ip={ip}"
        r = requests.get(url, timeout=10)
        if "OK" in r.text:
            print(f"🚀 DuckDNS Updated: {DUCKDNS_DOMAIN}.duckdns.org -> {ip}")
        else:
            print("⚠️ DuckDNS Update Failed")
    except:
        print("❌ DuckDNS Connection Error")

def update_firebase(status, ip):
    """Firebase par permanent link save karta hai"""
    perm_link = f"tg://proxy?server={DUCKDNS_DOMAIN}.duckdns.org&port={PORT}&secret={SECRET}"
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

    # config.py generation for extreme speed
    config_data = f"""
PORT = {PORT}
USERS = {{
    "admin": "{SECRET}"
}}
TLS_DOMAIN = "www.google.com"
AD_TAG = "" 
"""
    with open("mtprotoproxy/config.py", "w") as f:
        f.write(config_data)

    print(f"⚡ Proxy is LIVE on Port {PORT}")
    print(f"🔗 Permanent Link: tg://proxy?server={DUCKDNS_DOMAIN}.duckdns.org&port={PORT}&secret={SECRET}")

    # Start the engine
    subprocess.run("cd mtprotoproxy && python3 mtprotoproxy.py", shell=True)

if __name__ == "__main__":
    while True:
        try:
            start_proxy()
        except Exception as e:
            print(f"Restarting... Error: {e}")
            time.sleep(10)
