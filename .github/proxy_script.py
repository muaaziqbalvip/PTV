import os
import time
import subprocess

# --- CONFIGURATION ---
# Agar GitHub Secrets use kar rahe ho toh wahan se lega, warna niche manually likh do
PORT = 443
SECRET = os.getenv("TG_SECRET", "ee00000000000000000000000000000000") 
TAG = "7f000000000000000000000000000001" # Promotion Tag (Niche batata hoon kaise milega)

def start_proxy():
    print(f"🚀 Proxy starting on port {PORT}...")
    # Hum MTProxy-python use kar rahe hain
    try:
        # GitHub Actions par script ko 5 ghante 30 min tak chalane ka logic
        # Taake GitHub session expire hone se pehle gracefully band ho jaye
        cmd = f"python3 mtprotoproxy.py -p {PORT} -s {SECRET} -t {TAG}"
        process = subprocess.Popen(cmd, shell=True)
        
        print("✅ Proxy is LIVE!")
        time.sleep(19800) # 5.5 Hours tak chalega
        process.terminate()
        print("🔄 Restarting for stability...")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    # Library download karne ka command (Pehli baar ke liye)
    subprocess.run("git clone https://github.com/alexbers/mtprotoproxy.git", shell=True)
    os.chdir("mtprotoproxy")
    start_proxy()
