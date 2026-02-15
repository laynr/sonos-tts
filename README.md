# Sonos Text-to-Speech Tool

A Python CLI tool that plays text-to-speech messages on Sonos devices using Google TTS.

## Features

- Auto-discovers Sonos devices on your network
- Interactive device selection
- High-quality Google Text-to-Speech
- Preserves and restores playback state
- Supports multiple languages
- Volume control

## Requirements

- Python 3.8 or higher
- Sonos device(s) on the same network
- Internet connection (for Google TTS)

## Installation

1. Clone or download this repository

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Make the script executable:
```bash
chmod +x sonos_tts.py
```

## Usage

Basic usage:
```bash
python3 sonos_tts.py "Hello world"
```

With volume control:
```bash
python3 sonos_tts.py "Welcome home" --volume 50
```

Different language:
```bash
python3 sonos_tts.py "Bonjour le monde" --lang fr
```

Show help:
```bash
python3 sonos_tts.py --help
```

## Options

- `message` - Text message to speak (required)
- `--volume, -v` - Volume level 0-100 (optional, defaults to current volume)
- `--lang, -l` - Language code (optional, defaults to 'en')
- `--timeout, -t` - Device discovery timeout in seconds (optional, defaults to 5)

## Language Codes

Common language codes for `--lang`:
- `en` - English (US)
- `en-gb` - English (UK)
- `es` - Spanish
- `fr` - French
- `de` - German
- `it` - Italian
- `ja` - Japanese
- `zh` - Chinese

See [gTTS documentation](https://gtts.readthedocs.io/) for full list.

## How It Works

1. Discovers Sonos devices on your network using UPnP
2. Prompts you to select a device
3. Captures current playback state (what's playing, volume, position)
4. Converts your text to speech using Google TTS
5. Starts a temporary local HTTP server
6. Plays the audio on your Sonos device
7. Restores previous playback state
8. Cleans up temporary files and server

## Troubleshooting

**No devices found:**
- Make sure you're on the same WiFi network as your Sonos
- Check firewall settings (UPnP discovery uses UDP)
- Try increasing timeout: `--timeout 10`

**Cannot reach Google TTS:**
- Check your internet connection
- Google TTS is a free service but may have rate limits

**Playback doesn't work:**
- Make sure the Sonos device can reach your computer's IP
- Check that no firewall is blocking the HTTP server (ports 8000-9000)

## License

MIT License - feel free to use and modify as needed.
