import os
import sys
import asyncio
import requests
from groq import Groq

GROQ_API_KEY     = os.environ["GROQ_API_KEY"]"]
TELEGRAM_TOKEN = "8816458276:AAGnabqN9S3BAwS5HoCWlfJ8dvz0wGf38MA"




TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

TOPIC_PROMPT = """Generate a short viral video script (30-45 seconds).
Topic: motivational / life advice
Format:
TITLE: <catchy title>
SCRIPT: <narration text, 80-100 words>
Return ONLY the above format, nothing else."""

def generate_script():
    print("⏳ Calling Groq...")
    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",

        messages=[{"role": "user", "content": TOPIC_PROMPT}],
        max_tokens=300,
    )
    text = response.choices[0].message.content.strip()
    print("✅ Groq done:\n", text[:200])

    title, script = "", ""
    for line in text.splitlines():
        if line.startswith("TITLE:"):
            title = line.replace("TITLE:", "").strip()
        elif line.startswith("SCRIPT:"):
            script = line.replace("SCRIPT:", "").strip()

    if not title or not script:
        raise ValueError(f"Bad Groq format:\n{text}")
    return title, script

async def generate_tts(script: str, out_path: str = "voice.mp3"):
    print("⏳ Generating TTS...")
    import edge_tts
    communicate = edge_tts.Communicate(script, voice="en-US-GuyNeural")
    # 60 second timeout — اگه hang کرد، crash میشه نه hang
    await asyncio.wait_for(communicate.save(out_path), timeout=60)
    print(f"✅ TTS saved: {out_path}")
    return out_path

def send_telegram_text(title: str, script: str):
    """فقط text میفرسته — بدون فایل، سریع‌تره"""
    print("⏳ Sending Telegram...")
    msg = f"🎬 *{title}*\n\n{script}"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown",
    }, timeout=15)
    if resp.status_code == 200:
        print("✅ Telegram sent!")
    else:
        print(f"❌ Telegram error: {resp.status_code} — {resp.text}")
        sys.exit(1)

async def main():
    print("🚀 Starting...")
    title, script = generate_script()
    
    # TTS رو try کن، اگه fail شد ادامه بده
    try:
        await generate_tts(script)
    except Exception as e:
        print(f"⚠️ TTS failed (skipping): {e}")
    
    # Telegram رو همیشه بفرست
    send_telegram_text(title, script)
    print("✅ Done!")

if __name__ == "__main__":
    asyncio.run(main())
