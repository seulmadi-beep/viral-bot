import os
import sys
import asyncio
import requests
from groq import Groq

GROQ_API_KEY     = os.environ["GROQ_API_KEY"]
TELEGRAM_TOKEN   = "8816458276:AAGnabqN9S3BAwS5HoCWlfJ8dvz0wGf38MA"
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
YT_REFRESH_TOKEN = os.environ["YOUTUBE_REFRESH_TOKEN"]
YT_CLIENT_ID     = os.environ["YOUTUBE_CLIENT_ID"]
YT_CLIENT_SECRET = os.environ["YOUTUBE_CLIENT_SECRET"]

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
    await asyncio.wait_for(communicate.save(out_path), timeout=60)
    print(f"✅ TTS saved: {out_path}")
    return out_path

def create_video(title: str, audio_path: str, out_path: str = "video.mp4"):
    print("⏳ Creating video...")
    os.system(f'ffmpeg -f lavfi -i color=c=black:size=1080x1920:rate=30 -i {audio_path} -shortest -vf "drawtext=text=\'{title}\':fontcolor=white:fontsize=60:x=(w-text_w)/2:y=(h-text_h)/2" -c:v libx264 -c:a aac {out_path} -y')
    print(f"✅ Video created: {out_path}")
    return out_path

def get_youtube_token():
    resp = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": YT_CLIENT_ID,
        "client_secret": YT_CLIENT_SECRET,
        "refresh_token": YT_REFRESH_TOKEN,
        "grant_type": "refresh_token",
    })
    return resp.json()["access_token"]

def upload_youtube(title: str, video_path: str):
    print("⏳ Uploading to YouTube...")
    token = get_youtube_token()
    headers = {"Authorization": f"Bearer {token}"}
    metadata = {
        "snippet": {"title": title, "description": "Motivational content", "categoryId": "22"},
        "status": {"privacyStatus": "public"}
    }
    resp = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=multipart&part=snippet,status",
        headers=headers,
        files={
            "metadata": (None, str(metadata), "application/json"),
            "video": open(video_path, "rb")
        }
    )
    if resp.status_code == 200:
        print("✅ YouTube uploaded!")
        return resp.json().get("id")
    else:
        print(f"❌ YouTube error: {resp.status_code} — {resp.text[:200]}")
        return None

def send_telegram(title: str, script: str, yt_id: str = None):
    print("⏳ Sending Telegram...")
    msg = f"🎬 *{title}*\n\n{script}"
    if yt_id:
        msg += f"\n\n▶️ https://youtube.com/watch?v={yt_id}"
    resp = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown",
    }, timeout=15)
    if resp.status_code == 200:
        print("✅ Telegram sent!")
    else:
        print(f"❌ Telegram error: {resp.status_code}")
        sys.exit(1)

async def main():
    print("🚀 Starting...")
    title, script = generate_script()
    audio = await generate_tts(script)
    video = create_video(title, audio)
    yt_id = upload_youtube(title, video)
    send_telegram(title, script, yt_id)
    print("✅ Done!")

if __name__ == "__main__":
    asyncio.run(main())
