import os, asyncio, json, time, random, subprocess, logging, requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
log = logging.getLogger("ViralBot")

GROQ_API_KEY     = os.getenv("GROQ_API_KEY")
TELEGRAM_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
YT_CLIENT_ID     = os.getenv("YOUTUBE_CLIENT_ID")
YT_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")
OUTPUT_DIR       = Path("./videos")
OUTPUT_DIR.mkdir(exist_ok=True)

BG_COLORS = [
    ("#0f0c29", "#302b63"),
    ("#000428", "#004e92"),
    ("#1a1a2e", "#16213e"),
]

def get_trending_topics():
    topics = []
    try:
        import xml.etree.ElementTree as ET
        r = requests.get("https://www.youtube.com/feeds/videos.xml?chart=mostPopular&hl=en&regionCode=US", timeout=10)
        if r.status_code == 200:
            root = ET.fromstring(r.content)
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            for entry in root.findall('atom:entry', ns)[:5]:
                title = entry.find('atom:title', ns)
                if title is not None:
                    topics.append(title.text)
    except: pass
    if not topics:
        topics = ["life hacks that will blow your mind","psychology tricks nobody tells you","facts about money you need to know"]
    return topics[:8]

def generate_script(trending_topics):
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)
    topics_str = "\n".join(f"- {t}" for t in trending_topics[:5])
    prompt = f"""You are a viral video script expert. Analyze these trending topics and create ONE viral short video script.

TRENDING NOW:
{topics_str}

Return ONLY valid JSON:
{{
  "title": "Hook title under 60 chars",
  "hook": "First 3 seconds shocking statement",
  "script": "Full narration 120-150 words",
  "on_screen_text": ["Line 1", "Line 2", "Line 3", "Line 4", "Line 5"],
  "hashtags": ["#viral", "#fyp", "#trending", "#facts", "#mindblowing"],
  "description": "YouTube description 100 words",
  "duration_seconds": 55
}}"""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000, temperature=0.8,
    )
    raw = response.choices[0].message.content.strip().replace("```json","").replace("```","").strip()
    return json.loads(raw)

async def generate_voice(text, output_path, voice="en-US-ChristopherNeural"):
    import edge_tts
    tts = edge_tts.Communicate(text, voice, rate="+10%")
    await tts.save(output_path)

def create_video(script_data, audio_path, output_path):
    from PIL import Image, ImageDraw
    ts = int(time.time())
    temp_dir = OUTPUT_DIR / f"temp_{ts}"
    temp_dir.mkdir(exist_ok=True)
    duration = script_data.get("duration_seconds", 55)
    lines = script_data.get("on_screen_text", ["Watch till the end"])
    bg1, bg2 = random.choice(BG_COLORS)
    bg_path = str(temp_dir / "bg.png")
    img = Image.new("RGB", (1080, 1920))
    draw = ImageDraw.Draw(img)
    def h2r(h):
        h=h.lstrip('#'); return tuple(int(h[i:i+2],16) for i in (0,2,4))
    r1,g1,b1=h2r(bg1); r2,g2,b2=h2r(bg2)
    for y in range(1920):
        rat=y/1920
        draw.line([(0,y),(1080,y)],fill=(int(r1+(r2-r1)*rat),int(g1+(g2-g1)*rat),int(b1+(b2-b1)*rat)))
    img.save(bg_path)
    bg_video = str(temp_dir / "bg.mp4")
    subprocess.run(["ffmpeg","-y","-loop","1","-i",bg_path,"-t",str(duration),"-vf","scale=1080:1920","-c:v","libx264","-pix_fmt","yuv420p","-r","30","-preset","ultrafast",bg_video],capture_output=True)
    fd = duration/max(len(lines),1)
    filters=[]
    for i,line in enumerate(lines):
        s=i*fd; e=min((i+1)*fd,duration)
        safe=line.replace("'","").replace(":","\\:")
        filters.append(f"drawtext=text='{safe}':fontsize=72:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2:enable='between(t,{s:.1f},{e:.1f})'")
    vf=",".join(filters) if filters else "null"
    subprocess.run(["ffmpeg","-y","-i",bg_video,"-i",audio_path,"-vf",vf,"-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac","-b:a","192k","-shortest","-map","0:v","-map","1:a",output_path],capture_output=True)
    import shutil; shutil.rmtree(temp_dir,ignore_errors=True)
    return output_path

def send_to_telegram(script_data, video_path):
    callback_id = f"video_{int(time.time())}"
    caption = f"🎬 *ویدیو جدید*\n\n📌 *عنوان:*\n`{script_data['title']}`\n\n🎤 _{script_data['hook']}_\n\n🏷 {' '.join(script_data['hashtags'][:5])}\n\n🆔 `{callback_id}`"
    keyboard = {"inline_keyboard":[[{"text":"✅ تأیید","callback_data":f"approve_{callback_id}"},{"text":"❌ رد","callback_data":f"reject_{callback_id}"}]]}
    with open(video_path,"rb") as vf:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo",
            data={"chat_id":TELEGRAM_CHAT_ID,"caption":caption,"parse_mode":"Markdown","reply_markup":json.dumps(keyboard)},
            files={"video":vf},timeout=120)
    return callback_id

def wait_for_approval(callback_id, timeout_hours=12):
    deadline = time.time()+(timeout_hours*3600)
    offset = None
    while time.time()<deadline:
        try:
            params={"timeout":30}
            if offset: params["offset"]=offset
            r=requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",params=params,timeout=40)
            for update in r.json().get("result",[]):
                offset=update["update_id"]+1
                cb=update.get("callback_query")
                if cb and callback_id in cb.get("data",""):
                    action="approve" if "approve" in cb["data"] else "reject"
                    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery",
                        json={"callback_query_id":cb["id"],"text":"✅ دریافت شد!" if action=="approve" else "❌ رد شد"})
                    return action=="approve"
        except: time.sleep(5)
    return False

def send_msg(text):
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id":TELEGRAM_CHAT_ID,"text":text,"parse_mode":"Markdown"})

def upload_youtube(script_data, video_path):
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        import pickle
        SCOPES=["https://www.googleapis.com/auth/youtube.upload"]
        creds=None
        if os.path.exists("yt_creds.pickle"):
            with open("yt_creds.pickle","rb") as f: creds=pickle.load(f)
        if not creds or not creds.valid:
            flow=InstalledAppFlow.from_client_config({"installed":{"client_id":YT_CLIENT_ID,"client_secret":YT_CLIENT_SECRET,"redirect_uris":["urn:ietf:wg:oauth:2.0:oob"],"auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token"}},SCOPES)
            creds=flow.run_local_server(port=0)
            with open("yt_creds.pickle","wb") as f: pickle.dump(creds,f)
        yt=build("youtube","v3",credentials=creds)
        req=yt.videos().insert(part="snippet,status",
            body={"snippet":{"title":script_data["title"],"description":script_data["description"],"tags":[h.replace("#","") for h in script_data["hashtags"]],"categoryId":"27"},"status":{"privacyStatus":"public","selfDeclaredMadeForKids":False}},
            media_body=MediaFileUpload(video_path,chunksize=-1,resumable=True))
        resp=None
        while resp is None: _,resp=req.next_chunk()
        return f"https://youtu.be/{resp['id']}"
    except Exception as e:
        log.error(f"YouTube error: {e}"); return None

async def run_once():
    ts=int(time.time())
    trends=get_trending_topics()
    script=generate_script(trends)
    audio=str(OUTPUT_DIR/f"audio_{ts}.mp3")
    await generate_voice(script["script"],audio)
    video=str(OUTPUT_DIR/f"video_{ts}.mp4")
    create_video(script,audio,video)
    cb=send_to_telegram(script,video)
    approved=wait_for_approval(cb)
    if approved:
        url=upload_youtube(script,video)
        send_msg(f"🎉 *پابلیش شد!*\n▶️ {url or 'آپلود شد'}")
    else:
        os.remove(video)
        send_msg("❌ رد شد.")
    try: os.remove(audio)
    except: pass

async def main():
    send_msg("🤖 *Viral Bot شروع کرد!*")
    while True:
        try: await run_once()
        except KeyboardInterrupt: break
        except Exception as e: send_msg(f"⚠️ خطا: `{str(e)[:100]}`")
        await asyncio.sleep(12*3600)
if __name__=="__main__":
    import sys
    if "--once" in sys.argv:
        asyncio.run(run_once())
    else:
        asyncio.run(main())
