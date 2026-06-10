import os
import sys
import asyncio
import subprocess
import requests
import json
from groq import Groq

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
YT_REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")
YT_CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID", "")
YT_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

TOPIC_PROMPT = """Generate a short viral video script (30-45 seconds).
Topic: motivational / life advice
Format:
TITLE: <catchy title>
SCRIPT: <narration text, 80-100 words>
Return ONLY the above format, nothing else."""

def generate_script():
    print("Calling Groq...")
    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": TOPIC_PROMPT}],
        max_tokens=300,
    )
    text = response.choices[0].message.content.strip()
    print("Groq done:", text[:100])
    title = ""
    script = ""
    for line in text.splitlines():
        if line.startswith("TITLE:"):
            title = line.replace("TITLE:", "").strip()
        elif line.startswith("SCRIPT:"):
            script = line.replace("SCRIPT:", "").strip()
    if not title:
        title = "Motivational Video"
    if not script:
        script = text
    return title, script

async def generate_tts(script, out_path="voice.mp3"):
    print("Generating TTS...")
    import edge_tts
    communicate = edge_tts.Communicate(script, voice="en-US-GuyNeural")
    await asyncio.wait_for(communicate.save(out_path), timeout=60)
    print("TTS saved:", out_path)
    return out_path

def run_ffmpeg(args):
    result = subprocess.run(["ffmpeg"] + args, capture_output=True, text=True)
    if result.returncode != 0:
        print("FFMPEG ERROR:", result.stderr[-500:])
    return result.returncode

def create_video(title, audio_path, out_path="video.mp4"):
    print("Creating video...")
    safe_title = title.replace("'", "").replace('"', "").replace(":", "")

    # تلاش اول: با متن روی ویدیو
    drawtext = ("drawtext=fontfile=" + FONT + ":text='" + safe_title +
                "':fontcolor=white:fontsize=60:x=(w-text_w)/2:y=(h-text_h)/2")
    code = run_ffmpeg([
        "-f", "lavfi", "-i", "color=c=black:size=1080x1920:rate=30",
        "-i", audio_path,
        "-shortest", "-vf", drawtext,
        "-c:v", "libx264", "-c:a", "aac", out_path, "-y"
    ])

    # تلاش دوم: بدون متن (اگه drawtext مشکل داشت)
    if code != 0 or not os.path.exists(out_path):
        print("Retrying without text overlay...")
        code = run_ffmpeg([
            "-f", "lavfi", "-i", "color=c=black:size=1080x1920:rate=30",
            "-i", audio_path,
            "-shortest",
            "-c:v", "libx264", "-c:a", "aac", out_path, "-y"
        ])

    if code != 0 or not os.path.exists(out_path):
        print("Video creation FAILED completely.")
        sys.exit(1)

    print("Video created:", out_path, os.path.getsize(out_path), "bytes")
    return out_path

def get_youtube_token():
    resp = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": YT_CLIENT_ID,
        "client_secret": YT_CLIENT_SECRET,
        "refresh_token": YT_REFRESH_TOKEN,
        "grant_type": "refresh_token",
    })
    data = resp.json()
    print("YouTube token response:", str(data)[:200])
    if "access_token" not in data:
        raise ValueError("YouTube auth failed: " + str(data))
    return data["access_token"]

def upload_youtube(title, video_path):
    print("Uploading to YouTube...")
    token = get_youtube_token()
    headers = {"Authorization": "Bearer " + token}
    metadata = json.dumps({
        "snippet": {
            "title": title,
            "description": "Motivational content",
            "categoryId": "22"
        },
        "status": {
            "privacyStatus": "public"
        }
    })
    with open(video_path, "rb") as video_file:
        resp = requests.post(
            "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=multipart&part=snippet,status",
            headers=headers,
            files={
                "metadata": ("metadata", metadata, "application/json; charset=UTF-8"),
                "video": ("video.mp4", video_file, "video/mp4")
            }
        )
    if resp.status_code in [200, 201]:
        print("YouTube uploaded!")
        return resp.json().get("id")
    else:
        print("YouTube error:", resp.status_code, resp.text[:300])
        return None

def send_telegram(title, script, video_path, yt_id=None):
    print("Sending Telegram video...")
    caption = title + "\n\n" + script
    if yt_id:
        caption += "\n\nhttps://youtube.com/watch?v=" + yt_id
    with open(video_path, "rb") as video_file:
        resp = requests.post(
            "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendVideo",
            data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption[:1024]},
            files={"video": video_file},
            timeout=120
        )
    if resp.status_code == 200:
        print("Telegram video sent!")
    else:
        print("Telegram error:", resp.status_code, resp.text[:200])
        sys.exit(1)

async def main():
    print("Starting...")
    title, script = generate_script()
    audio = await generate_tts(script)
    video = create_video(title, audio)
    yt_id = None  # upload_youtube(title, video) — YouTube موقتاً غیرفعال
    send_telegram(title, script, video, yt_id)
    print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
