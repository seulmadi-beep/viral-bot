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
    if not title or
