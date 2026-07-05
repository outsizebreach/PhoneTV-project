from flask import Flask, render_template, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from mutagen import File as MutagenFile
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.mp4 import MP4
import os
import io
from PIL import Image
import base64

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")


# مسیر پوشه موسیقی شما
MUSIC_FOLDER = r'C:\music'





# پسوندهای مجاز فایل صوتی
ALLOWED_EXTENSIONS = {'.mp3', '.wav', '.ogg', '.flac', '.m4a', '.wma'}

# وضعیت فعلی پخش
current_state = {
    'song': None,
    'song_file': None,
    'playing': False,
    'cover_art': None
}

def remove_extension(filename):
    """حذف پسوند فایل"""
    return os.path.splitext(filename)[0]

def extract_cover_art(file_path):
    """استخراج کاور از فایل صوتی و تبدیل به base64"""
    try:
        audio = MutagenFile(file_path)
        
        if audio is None:
            return None
            
        if isinstance(audio, MP3):
            for tag in audio.tags.values():
                if tag.FrameID == 'APIC':
                    image_data = tag.data
                    image = Image.open(io.BytesIO(image_data))
                    buffered = io.BytesIO()
                    image.save(buffered, format="JPEG")
                    return base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        elif hasattr(audio, 'pictures') and audio.pictures:
            image_data = audio.pictures[0].data
            image = Image.open(io.BytesIO(image_data))
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG")
            return base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        elif isinstance(audio, MP4):
            if 'covr' in audio.tags:
                cover_data = audio.tags['covr'][0]
                image = Image.open(io.BytesIO(cover_data))
                buffered = io.BytesIO()
                image.save(buffered, format="JPEG")
                return base64.b64encode(buffered.getvalue()).decode('utf-8')
                
    except Exception as e:
        print(f"خطا در استخراج کاور: {e}")
    
    return None

def get_song_list():
    """لیست فایل‌های موسیقی داخل پوشه (بدون زیرپوشه)"""
    songs = []
    if os.path.exists(MUSIC_FOLDER):
        for f in os.listdir(MUSIC_FOLDER):
            ext = os.path.splitext(f)[1].lower()
            if ext in ALLOWED_EXTENSIONS:
                songs.append(f)
    return sorted(songs)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/control')
def control():
    return render_template('control.html')

@app.route('/player')
def player():
    return render_template('player.html')

@app.route('/api/songs')
def api_songs():
    """ارسال لیست آهنگ‌ها بدون پسوند"""
    songs = get_song_list()
    songs_without_ext = [remove_extension(s) for s in songs]
    return jsonify(songs_without_ext)

@app.route('/music/<path:filename>')
def serve_music(filename):
    """ارسال فایل صوتی به کلاینت"""
    # اگر filename پسوند نداره، پیداش کن
    if not os.path.splitext(filename)[1]:
        for ext in ALLOWED_EXTENSIONS:
            full_path = os.path.join(MUSIC_FOLDER, filename + ext)
            if os.path.exists(full_path):
                filename = filename + ext
                break
    return send_from_directory(MUSIC_FOLDER, filename)

@socketio.on('connect')
def handle_connect():
    """به محض اتصال هر کلاینت، وضعیت فعلی را ارسال کن"""
    emit('state', current_state)

@socketio.on('play_song')
def handle_play_song(data):
    song_name = data.get('song')  # این اسم بدون پسوند میاد
    if song_name:
        # پیدا کردن فایل کامل با پسوند
        songs = get_song_list()
        full_song = None
        for s in songs:
            if remove_extension(s) == song_name:
                full_song = s
                break
        
        if full_song:
            current_state['song'] = song_name  # بدون پسوند
            current_state['song_file'] = full_song  # با پسوند
            current_state['playing'] = True
            
            file_path = os.path.join(MUSIC_FOLDER, full_song)
            cover_art = extract_cover_art(file_path)
            current_state['cover_art'] = cover_art
            
            socketio.emit('state', current_state)

@socketio.on('play')
def handle_play():
    if current_state['song']:
        current_state['playing'] = True
        socketio.emit('state', current_state)

@socketio.on('pause')
def handle_pause():
    if current_state['song']:
        current_state['playing'] = False
        socketio.emit('state', current_state)

@socketio.on('volume_change')
def handle_volume_change(data):
    socketio.emit('volume_change', data)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)