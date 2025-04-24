from flask import Flask, request, jsonify, send_from_directory, render_template
import os
import requests
from werkzeug.utils import secure_filename
from mutagen import File
from mutagen.flac import FLAC
from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3
import lyricsgenius  # You'll need to pip install lyricsgenius
from bs4 import BeautifulSoup
import logging
import re

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__, 
    static_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static')),
    template_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates')))

UPLOAD_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'audio'))
LYRICS_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'lyrics'))
COVER_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static', 'covers'))

ALLOWED_EXTENSIONS = {'mp3', 'wav', 'ogg', 'm4a', 'flac'}  # Added FLAC support

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(LYRICS_FOLDER, exist_ok=True)
os.makedirs(COVER_FOLDER, exist_ok=True)

# Initialize Genius API (sign up at genius.com/api-clients)
genius = lyricsgenius.Genius("ggY8t6TZXmqA2ecdbYy6f7D3t3jgX1Zhsjzjn6BwIa-btdyWMIrFryut4eJUqI8r")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_audio_file(file_path):
    try:
        logger.debug(f"Processing audio file: {file_path}")
        if file_path.lower().endswith('.mp3'):
            audio = MP3(file_path, ID3=EasyID3)
            artist = audio.get('artist', ['Unknown'])[0]
            title = audio.get('title', [os.path.splitext(os.path.basename(file_path))[0]])[0]
            album = audio.get('album', ['Unknown'])[0]
        elif file_path.lower().endswith('.flac'):
            audio = FLAC(file_path)
            artist = audio.tags.get('ARTIST', ['Unknown'])[0]
            title = audio.tags.get('TITLE', [os.path.splitext(os.path.basename(file_path))[0]])[0]
            album = audio.tags.get('ALBUM', ['Unknown'])[0]
        else:
            audio = File(file_path)
            if hasattr(audio, 'tags'):
                artist = audio.tags.get('artist', ['Unknown'])[0]
                title = audio.tags.get('title', [os.path.splitext(os.path.basename(file_path))[0]])[0]
                album = audio.tags.get('album', ['Unknown'])[0]
            else:
                # Fallback to filename as title
                title = os.path.splitext(os.path.basename(file_path))[0]
                artist = "Unknown"
                album = "Unknown"
        
        logger.debug(f"Extracted metadata - Artist: {artist}, Title: {title}, Album: {album}")
        return artist, title, album
    except Exception as e:
        logger.error(f"Error processing {file_path}: {e}")
        # Fallback to filename as title
        title = os.path.splitext(os.path.basename(file_path))[0]
        return "Unknown", title, "Unknown"

import re

def fetch_lyrics_from_internet(artist, title):
    try:
        logger.debug(f"Fetching lyrics for {artist} - {title}")
        # Clean up the title
        cleaned_title = re.sub(r'^\d+\s*[-_]*\s*', '', title)  # Remove leading numbers and separators
        cleaned_title = cleaned_title.replace('_', ' ').strip()
        
        # Try multiple lyrics sources
        
        # 1. Try Genius API first with proper authentication
        # try:
        #     song = genius.search_song(cleaned_title, artist)
        #     if song and song.lyrics:
        #         logger.debug("Lyrics found from Genius!")
        #         lyrics = song.lyrics
        #         # Clean up the lyrics
        #         lyrics = re.sub(r'\d*Embed$', '', lyrics)  # Remove 'Embed' from the end
        #         lyrics = re.sub(r'\[.*?\]', '', lyrics)    # Remove [Verse], [Chorus] etc.
        #         lyrics = re.sub(r'You might also like', '', lyrics)
        #         # Remove extra blank lines while preserving paragraph structure
        #         lyrics = re.sub(r'\n\s*\n\s*\n+', '\n\n', lyrics)  # Replace 3+ newlines with 2
        #         lyrics = re.sub(r'^\s+|\s+$', '', lyrics, flags=re.MULTILINE)  # Remove leading/trailing spaces
        #         return lyrics.strip()
        # except Exception as e:
        #     logger.error(f"Genius API error: {e}")

        # 2. Try Lyrics.ovh API
        try:
            url = f"https://api.lyrics.ovh/v1/{artist}/{cleaned_title}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'lyrics' in data:
                    lyrics = data['lyrics']
                    # Standardize newlines
                    lyrics = lyrics.replace('\r\n', '\n').replace('\r', '\n')
                    # Clean up the lyrics
                    lyrics = re.sub(r'\n\s*\n\s*\n+', '\n\n', lyrics)  # Replace 3+ newlines with 2
                    lyrics = re.sub(r'^\s+|\s+$', '', lyrics, flags=re.MULTILINE)  # Remove leading/trailing spaces
                    return lyrics.strip()
        except Exception as e:
            logger.error(f"Lyrics.ovh API error: {e}")

        # 3. Try AZLyrics as last resort
        try:
            artist_url = re.sub(r'[^a-zA-Z0-9]', '', artist.lower())
            title_url = re.sub(r'[^a-zA-Z0-9]', '', cleaned_title.lower())
            url = f'https://www.azlyrics.com/lyrics/{artist_url}/{title_url}.html'
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                lyrics_div = None
                for div in soup.find_all("div", class_=False, id=False):
                    if div.find_previous(text=lambda text: isinstance(text, str) and 'Usage of azlyrics.com content' in text):
                        lyrics_div = div
                        break
                
                if lyrics_div:
                    lyrics_content = []
                    for content in lyrics_div.contents:
                        if isinstance(content, str):
                            lyrics_content.append(content.strip())
                        elif content.name == 'br':
                            lyrics_content.append('\n')
                    lyrics = "".join(lyrics_content)
                    # Standardize newlines
                    lyrics = lyrics.replace('\r\n', '\n').replace('\r', '\n')
                    # Clean up the lyrics - remove empty lines and extra whitespace
                    lyrics = "\n".join([line for line in lyrics.split('\n') if line.strip()])
                    lyrics = re.sub(r'\n\n+', '\n\n', lyrics) # Ensure no more than double newlines
                    return lyrics.strip()
        except Exception as e:
            logger.error(f"AZLyrics error: {e}")
        
        logger.debug("No lyrics found from any source")
        return None
    except Exception as e:
        logger.error(f"Error fetching lyrics: {e}")
        return None

def fetch_cover_from_internet(artist, title, album=None):
    try:
        logger.debug(f"Fetching cover for {artist} - {album or title}")
        
        # Last.fm API key (you should register for your own)
        lastfm_key = '7d21dec07e5e3082d44a848e4787fca5'
        
        if album and album != "Unknown":
            # Search by album first
            url = f"http://ws.audioscrobbler.com/2.0/?method=album.getinfo&api_key={lastfm_key}&artist={artist}&album={album}&format=json"
            response = requests.get(url)
            data = response.json()
            
            if 'album' in data and 'image' in data['album']:
                for img in data['album']['image']:
                    if img['size'] == 'extralarge' and img['#text']:
                        return img['#text']
        
        # Fallback to track search
        url = f"http://ws.audioscrobbler.com/2.0/?method=track.getInfo&api_key={lastfm_key}&artist={artist}&track={title}&format=json"
        response = requests.get(url)
        data = response.json()
        
        if 'track' in data and 'album' in data['track'] and 'image' in data['track']['album']:
            for img in data['track']['album']['image']:
                if img['size'] == 'extralarge' and img['#text']:
                    return img['#text']
        
        return None
    except Exception as e:
        logger.error(f"Error fetching cover: {e}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    if 'files' not in request.files:
        return jsonify({'error': 'No files in request'}), 400

    uploaded_files = []
    files = request.files.getlist('files')
    
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(file_path)
            
            # Process audio file for metadata
            artist, title, album = process_audio_file(file_path)
            if artist and title:
                # Fetch and save lyrics
                lyrics = fetch_lyrics_from_internet(artist, title)
                if lyrics:
                    lyrics_path = os.path.join(LYRICS_FOLDER, f"{filename}.txt")
                    with open(lyrics_path, 'w', encoding='utf-8') as f:
                        f.write(lyrics)
                
                # Fetch and save cover
                cover_url = fetch_cover_from_internet(artist, title, album)
                if cover_url:
                    cover_response = requests.get(cover_url)
                    if cover_response.ok:
                        cover_path = os.path.join(COVER_FOLDER, f"{filename}.jpg")
                        with open(cover_path, 'wb') as f:
                            f.write(cover_response.content)
            
            uploaded_files.append(filename)

    return jsonify({
        'message': 'Files uploaded successfully',
        'files': uploaded_files
    }), 200

@app.route('/api/files', methods=['GET'])
def get_files():
    files = []
    for filename in os.listdir(UPLOAD_FOLDER):
        if allowed_file(filename):
            files.append({
                'name': filename,
                'url': f'/static/audio/{filename}'
            })
    return jsonify(files)

@app.route('/api/remove_file/<filename>', methods=['DELETE'])
def remove_file(filename):
    filename = secure_filename(filename)
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        return '', 204
    return jsonify({'error': 'File not found'}), 404

@app.route('/api/clean_playlist', methods=['POST'])
def clean_playlist():
    try:
        # Clean audio files
        basenames = []
        for filename in os.listdir(UPLOAD_FOLDER):
            if os.path.isfile(os.path.join(UPLOAD_FOLDER, filename)):
                try:
                    base_name = os.path.splitext(filename)[0]
                    basenames.append(base_name)
                    os.remove(os.path.join(UPLOAD_FOLDER, filename))
                    logger.debug(f"Removed audio file: {filename}")
                except Exception as e:
                    logger.error(f"Error removing audio file {filename}: {e}")

        # Clean lyrics files and directory
        for filename in os.listdir(LYRICS_FOLDER):
            file_path = os.path.join(LYRICS_FOLDER, filename)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    logger.debug(f"Removed lyrics file: {filename}")
            except Exception as e:
                logger.error(f"Error removing lyrics file {filename}: {e}")

        # Clean cover files
        for basename in basenames:
            for ext in ['jpg', 'jpeg', 'png']:
                cover_file = os.path.join(COVER_FOLDER, f'{basename}.{ext}')
                if os.path.exists(cover_file):
                    try:
                        os.remove(cover_file)
                        logger.debug(f"Removed cover file: {basename}.{ext}")
                    except Exception as e:
                        logger.error(f"Error removing cover file {basename}.{ext}: {e}")

        return jsonify({'message': 'Playlist cleaned successfully', 'status': 'success'}), 200
    except Exception as e:
        logger.error(f"Error cleaning playlist: {e}")
        return jsonify({'message': 'Error cleaning playlist', 'status': 'error'}), 500

@app.route('/api/lyrics/<filename>', methods=['GET'])
def get_lyrics(filename):
    base_name = os.path.splitext(secure_filename(filename))[0]
    
    try:
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.exists(file_path):
            artist, title, _ = process_audio_file(file_path)
            
            lyrics_file = os.path.join(LYRICS_FOLDER, f'{base_name}.txt')
            try:
                if os.path.exists(lyrics_file):
                    with open(lyrics_file, 'r', encoding='utf-8') as f:
                        lyrics = f.read().replace('\n', '<br>')
                    # Don't add artist/title if they're already in the lyrics
                    if not lyrics.startswith(f"Artist: {artist}<br>Title: {title}"):
                        lyrics = f"Artist: {artist}<br>Title: {title}<br><br>" + lyrics
                    return jsonify({'lyrics': lyrics, 'status': 'success'})
            except Exception as e:
                logger.error(f"Error handling lyrics: {e}")
        
        # If lyrics file doesn't exist, try to fetch them
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.exists(file_path):
            artist, title, _ = process_audio_file(file_path)
            lyrics = fetch_lyrics_from_internet(artist, title)
            if lyrics:
                lyrics = f"Artist: {artist}<br>Title: {title}<br><br>" + lyrics.replace('\n', '<br>')
                with open(lyrics_file, 'w', encoding='utf-8') as f:
                    f.write(lyrics.replace('<br>', '\n')) # Write original newlines to file
                return jsonify({'lyrics': lyrics, 'status': 'success'})
    except Exception as e:
        logger.error(f"Error handling lyrics: {e}")
        
    return jsonify({'lyrics': None, 'status': 'not_found'}), 200

@app.route('/api/cover/<filename>', methods=['GET'])
def get_cover(filename):
    base_name = os.path.splitext(secure_filename(filename))[0]
    for ext in ['jpg', 'jpeg', 'png']:
        cover_path = os.path.join(COVER_FOLDER, f'{base_name}.{ext}')
        if os.path.exists(cover_path):
            # Return absolute URL for cover
            return jsonify({
                'cover_url': f'/static/covers/{base_name}.{ext}',
                'status': 'success'
            })
    return jsonify({'cover_url': None, 'status': 'not_found'}), 200

if __name__ == '__main__':
    app.run(debug=True)
