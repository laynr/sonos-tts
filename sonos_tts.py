#!/usr/bin/env python3
"""
Sonos Text-to-Speech Tool

Discovers Sonos devices on the network and plays text messages using Google TTS.
"""

import sys
import soco
from typing import List, Optional
from gtts import gTTS
import tempfile
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading
import socket

def discover_devices(timeout: int = 5) -> List[soco.SoCo]:
    """
    Discover all Sonos devices on the network.

    Args:
        timeout: Maximum time to wait for discovery in seconds

    Returns:
        List of discovered SoCo device objects
    """
    print(f"Discovering Sonos devices (timeout: {timeout}s)...")
    devices = list(soco.discover(timeout=timeout))

    if not devices:
        print("No Sonos devices found. Make sure you're on the same network.")
        return []

    print(f"Found {len(devices)} device(s)")
    return devices

def select_device(devices: List[soco.SoCo]) -> Optional[soco.SoCo]:
    """
    Display devices and prompt user to select one.

    Args:
        devices: List of discovered devices

    Returns:
        Selected device or None if cancelled
    """
    if not devices:
        return None

    print("\nAvailable Sonos devices:")
    for idx, device in enumerate(devices, 1):
        player_name = device.player_name
        ip_address = device.ip_address
        print(f"  {idx}. {player_name} ({ip_address})")

    while True:
        try:
            choice = input("\nSelect device number (or 'q' to quit): ").strip()

            if choice.lower() == 'q':
                return None

            idx = int(choice)
            if 1 <= idx <= len(devices):
                selected = devices[idx - 1]
                print(f"Selected: {selected.player_name}")
                return selected
            else:
                print(f"Please enter a number between 1 and {len(devices)}")
        except ValueError:
            print("Invalid input. Enter a number or 'q' to quit.")
        except KeyboardInterrupt:
            print("\nCancelled.")
            return None

def generate_tts(text: str, lang: str = 'en') -> Optional[str]:
    """
    Generate TTS audio file from text using Google TTS.

    Args:
        text: Text to convert to speech
        lang: Language code (default: 'en')

    Returns:
        Path to generated MP3 file, or None on failure
    """
    if not text or not text.strip():
        print("Error: Text message cannot be empty")
        return None

    print(f"Generating speech for: '{text}'")

    try:
        tts = gTTS(text=text, lang=lang, slow=False)

        # Create temporary file that won't be auto-deleted
        fd, temp_path = tempfile.mkstemp(suffix='.mp3', prefix='sonos_tts_')
        os.close(fd)  # Close file descriptor, we'll write with gTTS

        tts.save(temp_path)
        print(f"Audio generated: {temp_path}")
        return temp_path

    except Exception as e:
        print(f"Error generating TTS: {e}")
        print("Check your internet connection and try again.")
        return None

def get_local_ip() -> str:
    """
    Get the local IP address of this machine.

    Returns:
        Local IP address as string
    """
    try:
        # Connect to external address to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"

class AudioHTTPHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler that serves a single audio file."""

    audio_file_path = None

    def do_GET(self):
        """Handle GET request for audio file."""
        if self.path == '/audio.mp3':
            try:
                with open(self.audio_file_path, 'rb') as f:
                    self.send_response(200)
                    self.send_header('Content-type', 'audio/mpeg')
                    self.send_header('Content-Length', os.path.getsize(self.audio_file_path))
                    self.end_headers()
                    self.wfile.write(f.read())
            except Exception as e:
                self.send_error(500, f"Error serving file: {e}")
        else:
            self.send_error(404, "File not found")

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def start_http_server(audio_file: str, max_attempts: int = 3) -> Optional[tuple]:
    """
    Start HTTP server to serve audio file.

    Args:
        audio_file: Path to audio file to serve
        max_attempts: Maximum number of port attempts

    Returns:
        Tuple of (server, url) or None on failure
    """
    local_ip = get_local_ip()
    AudioHTTPHandler.audio_file_path = audio_file

    for attempt in range(max_attempts):
        try:
            # Try random port between 8000-9000
            port = 8000 + attempt * 100 + (os.getpid() % 100)
            server = HTTPServer((local_ip, port), AudioHTTPHandler)

            # Start server in background thread
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            url = f"http://{local_ip}:{port}/audio.mp3"
            print(f"HTTP server started: {url}")
            return (server, url)

        except OSError as e:
            if attempt < max_attempts - 1:
                print(f"Port {port} unavailable, retrying...")
                continue
            else:
                print(f"Error starting HTTP server: {e}")
                return None

    return None

def main():
    """Main entry point for the CLI."""
    # Temporary hardcoded message for testing
    message = "Hello world"

    devices = discover_devices()
    if not devices:
        return 1

    device = select_device(devices)
    if not device:
        print("No device selected. Exiting.")
        return 1

    audio_file = generate_tts(message)
    if not audio_file:
        return 1

    print(f"\nReady to play on {device.player_name}")
    print(f"Audio file: {audio_file}")

    # Cleanup temp file
    try:
        os.remove(audio_file)
        print(f"Cleaned up: {audio_file}")
    except Exception as e:
        print(f"Warning: Could not delete temp file: {e}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
