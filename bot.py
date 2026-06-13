"""
╔══════════════════════════════════════════════════════════╗
║        Chandu's Real-Time Java Job Alert Bot             ║
║  Filters: Entry/Fresher/0-Exp/Associate Only             ║
║  Roles: Software Engineer, Developer, Java Developer    ║
║  Database: SQLite3 (Concurrent & Crash-Resilient)       ║
╚══════════════════════════════════════════════════════════╝
"""

import requests
import json
import time
import schedule
import threading
import os
import sqlite3
import hashlib
from datetime import datetime
from bs4 import BeautifulSoup


from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# # ─── CONFIG ───────────────────────────────────────────────
# BOT_TOKEN = "8653797468:AAF49XcsruJbhellHExNdrVJjkWwcMzJqq4"
# ADMIN_ID  = "2092031953"
# DB_FILE   = "bot_data.db"

# ─── CONFIG ───────────────────────────────────────────────
# Safely pulls the token from the system environment variables
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8653797468:AAF49XcsruJbhellHExNdrVJjkWwcMzJqq4")
CHAT_ID   = "2092031953"
DB_FILE   = "bot_data.db"

# ─── STRICT FILTERING CRITERIA ────────────────────────────
ALLOWED_KEYWORDS = ["software engineer", "software developer", "java developer", "java full stack", "backend engineer"]
ALLOWED_EXPERIENCE = ["fresher", "entry level", "0 year", "0-1 year", "0-2 years", "associate", "graduate trainee"]
BLOCKED_KEYWORDS = ["senior", "sr.", "lead", "principal", "manager", "architect", "5+", "3+ years"]

# ─── DATABASE INITIALIZATION ──────────────────────────────
def init_db():
    """Sets up relational tables for thread-safe execution."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Table for tracking subscribers
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscribers (
            chat_id TEXT PRIMARY KEY
        )
    """)
    # Table for tracking sent job hashes to prevent duplicate alerts
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sent_jobs (
            job_hash TEXT PRIMARY KEY,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_subscribers():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT chat_id FROM subscribers")
    subs = [row[0] for row in cursor.fetchall()]
    conn.close()
    if ADMIN_ID not in subs:
        subs.append(ADMIN_ID)
    return subs

def add_subscriber(chat_id: str):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO subscribers (chat_id) VALUES (?)", (chat_id,))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def is_job_new(link: str) -> bool:
    """Uses SHA-256 hash checking to confirm if a link is completely unique."""
    job_hash = hashlib.sha256(link.encode('utf-8')).hexdigest()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM sent_jobs WHERE job_hash = ?", (job_hash,))
    exists = cursor.fetchone()
    
    if not exists:
        cursor.execute("INSERT INTO sent_jobs (job_hash, timestamp) VALUES (?, ?)", 
                       (job_hash, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

# ─── TELEGRAM COMMUNICATIONS ──────────────────────────────
def send_telegram(chat_id: str, message: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML", "disable_web_page_preview": True}
    try:
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code != 200:
            print(f"[Telegram Error] {r.text}")
    except Exception as e:
        print(f"[Telegram Exception] {e}")

def broadcast_job(job):
    """Sends a newly detected job directly to everyone in real-time."""
    subs = get_subscribers()
    message = (
        f"🚨 <b>NEW MATCHING JOB SPOTTED</b>\n"
        f"💼 <b>Role:</b> {job['title']}\n"
        f"🏢 <b>Company:</b> {job['company']}\n"
        f"📍 <b>Location:</b> {job['location']}\n"
        f"🌐 <b>Source:</b> {job['source']}\n"
        f"🔗 <a href='{job['link']}'>Apply Immediately Here</a>\n"
    )
    for chat_id in subs:
        send_telegram(chat_id, message)
        time.sleep(0.3)

# ─── REAL-TIME PROCESSING FILTERS ──────────────────────────
def qualification_check(title: str) -> bool:
    """Verifies that the job matches only your specific requested engineering roles."""
    title_lower = title.lower()
    
    # Block any senior or experienced management positions
    if any(blocked in title_lower for blocked in BLOCKED_KEYWORDS):
        return False
        
    # Must match target fresher engineering domains
    if any(allowed in title_lower for allowed in ALLOWED_KEYWORDS):
        return True
    return False

# ─── LIVE AGGREGATION PIPELINE ────────────────────────────
def check_feeds_for_new_jobs():
    """Scrapes external endpoints and enforces entry-level structural filters."""
    print(f"[*] [{datetime.now().strftime('%H:%M:%S')}] Checking live feeds for fresh entries...")
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    # 1. Scrape Internshala Java Feed
    try:
        url = "https://internshala.com/fresher-jobs/java-jobs/"
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.find_all("div", class_="individual_internship")
        
        for card in cards:
            try:
                title_el = card.find("h3", class_="title")
                company_el = card.find("a", class_="company_name")
                link_el = card.find("a", class_="view_detail_button")
                
                if title_el and link_el:
                    title = title_el.get_text(strip=True)
                    company = company_el.get_text(strip=True) if company_el else "Tech Company"
                    link = "https://internshala.com" + link_el["href"]
                    
                    if qualification_check(title) and is_job_new(link):
                        job = {"title": title, "company": company, "location": "India/Remote", "link": link, "source": "Internshala"}
                        broadcast_job(job)
            except Exception:
                continue
    except Exception as e:
        print(f"[Pipeline Error - Internshala] {e}")

    # 2. Scrape Careerjet Aggregator Feed
    try:
        url = "https://www.careerjet.in/java-fresher-jobs.html"
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        articles = soup.find_all("article", class_="job")
        
        for art in articles:
            try:
                title_el = art.find("a", class_="job_title")
                company_el = art.find("p", class_="company")
                loc_el = art.find("ul", class_="location")
                
                if title_el:
                    title = title_el.get_text(strip=True)
                    company = company_el.get_text(strip=True) if company_el else "Verified Employer"
                    location = loc_el.get_text(strip=True) if loc_el else "India"
                    link = "https://www.careerjet.in" + title_el["href"]
                    
                    if qualification_check(title) and is_job_new(link):
                        job = {"title": title, "company": company, "location": location, "link": link, "source": "Careerjet"}
                        broadcast_job(job)
            except Exception:
                continue
    except Exception as e:
        print(f"[Pipeline Error - Careerjet] {e}")

# ─── COMMANDS ENGINE ──────────────────────────────────────
def check_for_commands():
    last_update_id = None
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
            params = {"timeout": 30, "offset": last_update_id}
            r = requests.get(url, params=params, timeout=35)
            data = r.json()

            if data.get("ok") and data.get("result"):
                for update in data["result"]:
                    last_update_id = update["update_id"] + 1
                    message = update.get("message", {})
                    text = message.get("text", "").strip().lower()
                    chat_id = str(message.get("chat", {}).get("id", ""))

                    if not chat_id:
                        continue

                    if text in ["/start", "/hello"]:
                        is_new = add_subscriber(chat_id)
                        welcome = (
                            "👋 <b>Welcome to Chandu's 24/7 Java Job Tracker!</b>\n\n"
                            "This engine is fully automated. It tracks postings 24/7 and will ping you "
                            "the *second* a new Software Engineer, Developer, or Java Fresher role drops.\n\n"
                            "🎯 <b>Status:</b> Active Subscriber"
                        )
                        send_telegram(chat_id, welcome)
                        if is_new and chat_id != ADMIN_ID:
                            send_telegram(ADMIN_ID, f"🔔 <b>New Subscriber Alert:</b> User {chat_id} joined your channel.")
                            
                    elif text in ["/jobs", "/check"]:
                        send_telegram(chat_id, "⏳ Running instant diagnostic scan across external data streams...")
                        check_feeds_for_new_jobs()
                        send_telegram(chat_id, "✅ Scan complete. Any newly identified matching roles have been dispatched.")
        except Exception as e:
            print(f"[Command Error] {e}")
        time.sleep(2)

# ─── EXECUTION HANDOFF ────────────────────────────────────
def run_scheduler():
    # Continually executes tracking lookups hourly, 24 hours a day
    schedule.every(1).hours.do(check_feeds_for_new_jobs)
    print("[✓] 24/7 Hourly Monitoring Worker Thread Pool Attached.")
    while True:
        schedule.run_pending()
        time.sleep(10)

    if __name__ == "__main__":
        print("!!! THE BOT CODE HAS STARTED RUNNING !!!") # Add this line
    # ... rest of your code
  
    print("=" * 60)
    print("  Initializing 24/7 Enterprise Job Stream Filtering Pipeline")
    print("=" * 60)
    
    # 1. Initialize the SQLite database
    init_db()

    # 2. Start command listener FIRST so it doesn't miss anyone clicking /start
    cmd_thread = threading.Thread(target=check_for_commands, daemon=True)
    cmd_thread.start()
    print("[✓] Context API polling worker active.")

    # 3. Start the Web Server for Render
    threading.Thread(target=run_web_server, daemon=True).start()
    print("[✓] Flask health check server running.")

    # 4. EXPLICIT STARTUP BROADCAST (Forces the bot to send a message right now)
    startup_message = (
        "✅ <b>Chandu's Job Alert Engine is officially ONLINE!</b>\n\n"
        "☁️ Hosted 24/7 on Render Cloud.\n"
        "🔍 Monitoring entry-level Software Engineer & Java Developer roles.\n"
        "⏰ Next automated scan will run in 1 hour."
    )
    print("[*] Sending startup broadcast to active subscribers...")
    broadcast_message_text = """🚀 <b>Java Job Alert Bot</b> is now running 24/7 in the cloud!\n\nType /jobs to fetch current matching openings instantly."""
    
    # Send a quick direct message to you (Admin) to verify connectivity
    send_telegram(ADMIN_ID, startup_message)
    
    # Send to all registered subscribers
    for sub_id in get_subscribers():
        send_telegram(sub_id, broadcast_message_text)

    # 5. Run the background scheduler loop
    run_scheduler()