from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token
import os
import anthropic
import yt_dlp
import requests
import random

app = Flask(__name__)
CORS(app)

app.config['JWT_SECRET_KEY'] = os.environ.get('SECRET_KEY', 'wave-secret-key')
jwt = JWTManager(app)

client = anthropic.Anthropic(
    api_key=os.environ.get('ANTHROPIC_API_KEY')
)

otp_store = {}

@app.route('/')
def health():
    return jsonify({'status': 'WAVE server running', 'version': '1.0'})

@app.route('/auth/send-otp', methods=['POST'])
def send_otp():
    email = request.json.get('email')
    otp = str(random.randint(100000, 999999))
    otp_store[email] = otp
    print(f"OTP for {email}: {otp}")
    return jsonify({'message': 'OTP sent'})

@app.route('/auth/verify-otp', methods=['POST'])
def verify_otp():
    email = request.json.get('email')
    otp = request.json.get('otp')
    if otp_store.get(email) == otp:
        del otp_store[email]
        token = create_access_token(identity=email)
        return jsonify({'token': token, 'email': email})
    return jsonify({'error': 'Invalid OTP'}), 401

@app.route('/aria/chat', methods=['POST'])
def aria_chat():
    message = request.json.get('message')
    history = request.json.get('history', [])
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        system="""You are ARIA, the AI assistant inside WAVE app.
You help users find music, videos, and download content.
You give recommendations, answer questions, and assist
with anything the user needs. Be friendly and concise.""",
        messages=history + [
            {"role": "user", "content": message}
        ]
    )
    return jsonify({'reply': response.content[0].text})

@app.route('/download/info', methods=['POST'])

def get_tiktok_info(url):
    try:
        r = requests.get(f"https://tikwm.com/api/?url={url}", timeout=10)
        data = r.json()
        if data.get('code') == 0:
            d = data['data']
            return {
                'title': d.get('title', 'TikTok Video'),
                'thumbnail': d.get('cover'),
                'duration': str(d.get('duration', '')),
                'uploader': d.get('author', {}).get('nickname', ''),
                'site': 'TikTok',
                'formats': [],
                'source': 'tikwm',
                'direct_url': d.get('play')
            }
    except Exception as e:
        print(f"[TikWM] {e}")
    return None

def get_info():
    url = request.json.get('url')
    try:
        ydl_opts = {'quiet': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({
                'title': info.get('title'),
                'thumbnail': info.get('thumbnail'),
                'duration': info.get('duration'),
                'uploader': info.get('uploader'),
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/download/start', methods=['POST'])
def start_download():
    url = request.json.get('url')
    quality = request.json.get('quality', '720')
    fmt = request.json.get('format', 'mp4')
    try:
        ydl_opts = {
            'format': f'bestvideo[height<={quality}]+bestaudio/best',
            'merge_output_format': fmt,
            'outtmpl': '/tmp/%(title)s.%(ext)s',
            'quiet': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return jsonify({
                'success': True,
                'title': info.get('title'),
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/lyrics', methods=['POST'])
def get_lyrics():
    artist = request.json.get('artist', '')
    title = request.json.get('title', '')
    duration = request.json.get('duration', 180)
    try:
        r = requests.get(
            'https://lrclib.net/api/get',
            params={'artist_name': artist, 'track_name': title}
        )
        if r.ok and r.json().get('syncedLyrics'):
            return jsonify({
                'source': 'lrclib',
                'synced': True,
                'lyrics': r.json().get('syncedLyrics')
            })
        if r.ok and r.json().get('plainLyrics'):
            return jsonify({
                'source': 'lrclib',
                'synced': False,
                'lyrics': r.json().get('plainLyrics')
            })
    except:
        pass
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": f"""Write lyrics for this song in LRC timestamp format.
Artist: {artist}
Title: {title}
Duration: {duration} seconds
Return ONLY LRC format like:
[00:12.00] Line here
[00:15.50] Next line
Spread evenly across {duration} seconds."""
        }]
    )
    return jsonify({
        'source': 'ai',
        'synced': True,
        'lyrics': response.content[0].text
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
