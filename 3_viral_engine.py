import os
import sys
import asyncio
import subprocess
import requests
import json
import random
from groq import Groq

GROQ_API_KEY = os.environ["GROQ_API_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
PEXELS_API_KEY = os.environ["PEXELS_API_KEY"]
YT_REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")
YT_CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID", "")
YT_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")

NUM_CLIPS = 5

THEMES = [
    "discipline and daily habits",
    "overcoming fear and self-doubt",
    "failure as a teacher",
    "waking up early and owning your morning",
    "money mindset and building wealth",
    "consistency beats talent",
    "cutting toxic people and environments",
    "patience and playing the long game",
    "comparison is the thief of joy",
    "taking risks while you are young",
    "loneliness on the path to success",
    "turning pain into power",
    "stop waiting for motivation",
    "your future self is watching you",
    "small steps compound into big results",
]

def build_prompt():
    theme = random.choice(THEMES)
    print("Theme:", theme)
    return """Generate a short viral video script (60-75 seconds).
Topic: motivational — specifically about: """ + theme + """
Rules:
- The SCRIPT must START with a shocking or curiosity-driven hook sentence (max 8 words).
- Then 150-180 words of powerful motivational narration.
- Avoid generic cliches. Be specific and punchy.
- KEYWORDS: exactly 5 simple English nouns for cinematic stock footage matching the theme, comma separated.
Format:
TITLE: <catchy title, max 6 words>
KEYWORDS: <word1, word2, word3, word4, word5>
SCRIPT: <hook + narration in one paragraph>
Return ONLY the above format, nothing else."""

def generate_script():
    print("Calling Groq...")
    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": build_prompt()}],
        max_tokens=700,
        temperature=1.1,
    )
    text = response.choices[0].message.content.strip()
    print("Groq done:", text[:100])
    title, keywords, script = "", "", ""
    for line in text.splitlines():
        if line.startswith("TITLE:"):
            title = line.replace("TITLE:", "").strip()
        elif line.startswith("KEYWORDS:"):
            keywords = line.replace("KEYWORDS:", "").strip()
        elif line.startswith("SCRIPT:"):
            script = line.replace("SCRIPT:", "").strip()
    if not title:
        title = "Motivational Video"
    if not keywords:
        keywords = "nature, ocean, sunrise, mountains, city"
    if not script:
        script = text
    return title, keywords, script

async def generate_tts(script, out_path="voice.mp3"):
    print("Generating TTS with word timings...")
    import edge_tts
    communicate = edge_tts.Communicate(script, voice="en-US-GuyNeural", rate="+5%")
    words = []
    with open(out_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                words.append({
                    "text": chunk["text"],
                    "start": chunk["offset"] / 10_000_000,
                    "end": (chunk["offset"] + chunk["duration"]) / 10_000_000,
                })
    print("TTS saved:", out_path, "| words:", len(words))
    return out_path, words

def get_audio_duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())

def run_ffmpeg(args):
    result = subprocess.run(["ffmpeg"] + args, capture_output=True, text=True)
    if result.returncode != 0:
        print("FFMPEG ERROR:", result.stderr[-500:])
    return result.returncode

def download_pexels_clips(keywords, count=NUM_CLIPS):
    print("Searching Pexels:", keywords)
    clips = []
    kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
    for i, kw in enumerate(kw_list[:count]):
        try:
            resp = requests.get(
                "https://api.pexels.com/videos/search",
                headers={"Authorization": PEXELS_API_KEY},
                params={"query": kw, "orientation": "portrait", "per_page": 10},
                timeout=30
            )
            videos = resp.json().get("videos", [])
            if not videos:
                print("No results for:", kw)
                continue
            video = random.choice(videos)
            files = video.get("video_files", [])
            files = sorted(files, key=lambda f: f.get("height") or 0, reverse=True)
            link = None
            for f in files:
                if (f.get("height") or 0) >= 1080:
                    link = f["link"]
            if not link and files:
                link = files[0]["link"]
            if not link:
                continue
            path = "clip" + str(i) + ".mp4"
            print("Downloading:", kw)
            with requests.get(link, stream=True, timeout=120) as r:
                with open(path, "wb") as out:
                    for chunk in r.iter_content(chunk_size=1024 * 256):
                        out.write(chunk)
            clips.append(path)
        except Exception as e:
            print("Pexels error for", kw, ":", str(e)[:200])
    print("Clips downloaded:", len(clips))
    return clips

def ass_time(t):
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return "{}:{:02d}:{:05.2f}".format(h, m, s)

def build_subtitles(words, out_path="subs.ass"):
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Word,DejaVu Sans,115,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,10,2,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for w in words:
        end = max(w["end"], w["start"] + 0.12)
        lines.append("Dialogue: 0,{},{},Word,,0,0,0,,{}".format(
            ass_time(w["start"]), ass_time(end), w["text"].upper()))
    with open(out_path, "w") as f:
        f.write("\n".join(lines))
    print("Subtitles built:", len(words), "words")
    return out_path

def build_video(clips, audio_path, subs_path, out_path="video.mp4"):
    print("Building video...")
    duration = get_audio_duration(audio_path)
    print("Audio duration:", duration)

    if not clips:
        print("No clips! Using black background fallback.")
        code = run_ffmpeg([
            "-f", "lavfi", "-i",
            "color=c=black:size=1080x1920:rate=30:d=" + str(duration),
            "-i", audio_path,
            "-vf", "ass=" + subs_path,
            "-shortest", "-c:v", "libx264", "-preset", "fast",
            "-c:a", "aac", out_path, "-y"
        ])
        if code != 0 or not os.path.exists(out_path):
            sys.exit(1)
        return out_path

    seg_dur = duration / len(clips) + 0.5
    seg_files = []
    for i, clip in enumerate(clips):
        seg = "seg" + str(i) + ".mp4"
        code = run_ffmpeg([
            "-stream_loop", "-1", "-i", clip, "-t", str(seg_dur),
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30",
            "-an", "-c:v", "libx264", "-preset", "fast", seg, "-y"
        ])
        if code == 0 and os.path.exists(seg):
            seg_files.append(seg)
    if not seg_files:
        print("All segments failed!")
        sys.exit(1)

    with open("list.txt", "w") as f:
        for seg in seg_files:
            f.write("file '" + seg + "'\n")

    code = run_ffmpeg([
        "-f", "concat", "-safe", "0", "-i", "list.txt",
        "-i", audio_path,
        "-vf", "ass=" + subs_path,
        "-map", "0:v", "-map", "1:a",
        "-shortest", "-c:v", "libx264", "-preset", "fast",
        "-c:a", "aac", out_path, "-y"
    ])
    if code != 0 or not os.path.exists(out_path):
        print("Final video FAILED.")
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
            timeout=180
        )
    if resp.status_code == 200:
        print("Telegram video sent!")
    else:
        print("Telegram error:", resp.status_code, resp.text[:200])
        sys.exit(1)

async def main():
    print("Starting...")
    title, keywords, script = generate_script()
    audio, words = await generate_tts(script)
    clips = download_pexels_clips(keywords)
    subs = build_subtitles(words)
    video = build_video(clips, audio, subs)
    yt_id = None  # upload_youtube(title, video) — YouTube موقتاً غیرفعال
    send_telegram(title, script, video, yt_id)
    print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
