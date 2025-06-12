# Cline Music Player

A modern web-based music player with lyrics and album art support, built with Python Flask.

## Features

- Upload and play music files (supports MP3, WAV, OGG, M4A, FLAC)
- Automatic lyrics fetching from multiple sources
- Album artwork display
- Clean and modern interface
- Drag and drop file upload support
- Metadata extraction from audio files

## Requirements

- Python 3.8+
- Flask
- mutagen
- requests
- beautifulsoup4
- lyricsgenius
- python-dotenv

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/Web_Music_Player.git
cd cline
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the application:
```bash
python src/app.py
```

The application will be available at `http://localhost:5000`

## Project Structure

```
cline/
├── src/
│   └── app.py              # Main Flask application
├── static/
│   ├── audio/             # Uploaded audio files
│   ├── covers/           # Album artwork
│   ├── css/             # Stylesheets
│   └── lyrics/          # Cached lyrics
├── templates/
│   └── index.html       # Main application template
├── requirements.txt     # Python dependencies
├── .gitignore          # Git ignore rules
└── README.md           # This file
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
