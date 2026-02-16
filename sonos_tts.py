#!/usr/bin/env python3
"""
Sonos Text-to-Speech Tool

Discovers Sonos devices on the network and plays text messages using Google TTS.
"""

__version__ = "1.0.0"

import sys
import warnings

# Suppress urllib3 OpenSSL warning
warnings.filterwarnings('ignore', message='urllib3 v2 only supports OpenSSL')

import sys
import soco
from typing import List, Optional
from gtts import gTTS
import tempfile
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading
import socket
import time
from soco.exceptions import SoCoException
import argparse

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

    # Build groups
    groups = {}
    for device in devices:
        coordinator = get_group_coordinator(device)
        coord_name = coordinator.player_name
        if coord_name not in groups:
            groups[coord_name] = []
        groups[coord_name].append(device.player_name)

    # Display devices organized by groups
    print(f"Found {len(devices)} device(s) in {len(groups)} group(s):")
    for coord, members in groups.items():
        if len(members) > 1:
            print(f"  - {coord} (coordinator): {', '.join(members)}")
        else:
            print(f"  - {coord} (standalone)")

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

def capture_state(device: soco.SoCo) -> dict:
    """
    Capture current playback state of Sonos device.

    Args:
        device: SoCo device object

    Returns:
        Dictionary containing state information
    """
    try:
        transport_info = device.get_current_transport_info()
        track_info = device.get_current_track_info()

        state = {
            'transport_state': transport_info['current_transport_state'],
            'track_uri': track_info.get('uri', ''),
            'position': track_info.get('position', '0:00:00'),
            'volume': device.volume,
            'status_light': device.status_light,
        }

        print(f"Captured state: {state['transport_state']}")
        return state

    except Exception as e:
        print(f"Warning: Could not capture state: {e}")
        return {}


def restore_state(device: soco.SoCo, state: dict) -> bool:
    """
    Restore previous playback state of Sonos device.

    Args:
        device: SoCo device object
        state: State dictionary from capture_state()

    Returns:
        True if restoration succeeded, False otherwise
    """
    if not state:
        return False

    try:
        # Restore volume
        if 'volume' in state:
            device.volume = state['volume']

        # Restore status light
        if 'status_light' in state:
            device.status_light = state['status_light']

        # Restore playback if there was something playing
        if state.get('track_uri') and state['transport_state'] in ['PLAYING', 'PAUSED_PLAYBACK']:
            device.play_uri(state['track_uri'])

            # Seek to position if available and valid
            position = state.get('position', '0:00:00')
            if position and position != '0:00:00' and position != 'NOT_IMPLEMENTED':
                try:
                    device.seek(position)
                except Exception:
                    pass  # Skip seek if position is invalid

            # Resume if it was paused
            if state['transport_state'] == 'PAUSED_PLAYBACK':
                device.pause()

            print("Restored previous playback")
            return True

    except Exception as e:
        print(f"Warning: Could not restore state: {e}")
        return False

    return True


def get_group_coordinator(device: soco.SoCo) -> soco.SoCo:
    """
    Get the coordinator (master) of a device's group.

    Args:
        device: SoCo device object

    Returns:
        The group coordinator device
    """
    return device.group.coordinator


def check_if_grouped(devices: List[soco.SoCo]) -> Optional[soco.SoCo]:
    """
    Check if all devices are already in the same group.

    Args:
        devices: List of SoCo device objects to check

    Returns:
        The coordinator if all devices are grouped together, None otherwise
    """
    if not devices:
        return None

    if len(devices) == 1:
        return devices[0]

    # Get coordinators for all devices
    coordinators = [get_group_coordinator(d) for d in devices]

    # Check if all have the same coordinator
    first_coord = coordinators[0]
    if all(c.player_name == first_coord.player_name for c in coordinators):
        # All devices are already in the same group
        return first_coord

    return None


def is_home_theater(device: soco.SoCo) -> bool:
    """
    Check if device is a home theater setup (has bonded speakers).

    Args:
        device: SoCo device object

    Returns:
        True if device is part of a home theater setup
    """
    try:
        # Check if device has bonded speakers (surround/sub)
        return len(list(device.group.members)) > 1 and device.group.coordinator == device
    except Exception:
        return False


def create_group(devices: List[soco.SoCo]) -> soco.SoCo:
    """
    Create a group with all devices and return the coordinator.

    Args:
        devices: List of SoCo device objects to group

    Returns:
        The group coordinator device
    """
    if not devices:
        return None

    if len(devices) == 1:
        return devices[0]

    # Prefer home theater device as coordinator (they often can't be grouped as members)
    coordinator = None
    for device in devices:
        if is_home_theater(device):
            coordinator = device
            print(f"  Using {coordinator.player_name} as coordinator (home theater setup)")
            break

    # Otherwise use first device
    if not coordinator:
        coordinator = devices[0]
        print(f"  Using {coordinator.player_name} as group coordinator")

    # Join other devices to the coordinator's group
    for device in devices:
        if device.player_name == coordinator.player_name:
            continue  # Skip coordinator itself

        try:
            print(f"  Joining {device.player_name} to group...")
            device.join(coordinator)
            time.sleep(0.5)  # Give it time to join
        except Exception as e:
            print(f"  ERROR: Could not group {device.player_name}: {e}")

    # Verify the group was formed
    time.sleep(1)  # Wait for group to stabilize
    group_members = coordinator.group.members
    # Get unique visible player names (exclude bonded/hidden speakers)
    visible_members = list(set([m.player_name for m in group_members]))
    print(f"  Group formed with {len(visible_members)} visible device(s): {', '.join(visible_members)}")

    # Check if all target devices are in the group
    target_names = set([d.player_name for d in devices])
    grouped_names = set(visible_members)
    if not target_names.issubset(grouped_names):
        missing = target_names - grouped_names
        print(f"  WARNING: Some devices didn't join: {', '.join(missing)}")

    return coordinator


def ungroup_all(devices: List[soco.SoCo]) -> None:
    """
    Ungroup all devices (each becomes its own group).

    Args:
        devices: List of SoCo device objects to ungroup
    """
    for device in devices:
        try:
            device.unjoin()
        except Exception:
            pass  # Already ungrouped or error


def play_on_sonos(device: soco.SoCo, audio_url: str, volume: Optional[int] = None) -> bool:
    """
    Play audio on Sonos device and restore previous state.

    Args:
        device: SoCo device object
        audio_url: HTTP URL to audio file
        volume: Optional volume level (0-100)

    Returns:
        True if playback succeeded, False otherwise
    """
    # Capture current state
    previous_state = capture_state(device)

    try:
        # Turn off status light to prevent LED from turning on
        device.status_light = False

        # Set volume if specified
        if volume is not None:
            print(f"Setting volume to {volume}")
            device.volume = volume

        # Play TTS audio
        device.play_uri(audio_url)

        # Wait for playback to complete
        # Poll transport state until it's no longer playing
        max_wait = 30  # Maximum 30 seconds
        start_time = time.time()

        while time.time() - start_time < max_wait:
            time.sleep(0.5)
            try:
                transport_info = device.get_current_transport_info()
                state = transport_info['current_transport_state']

                if state == 'STOPPED':
                    print("Playback completed")
                    break
            except Exception:
                continue

        # Restore previous state
        time.sleep(0.5)  # Brief pause before restoring
        restore_state(device, previous_state)

        return True

    except SoCoException as e:
        print(f"Error playing on Sonos: {e}")
        # Attempt to restore state even on error
        restore_state(device, previous_state)
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        restore_state(device, previous_state)
        return False

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Play text-to-speech messages on Sonos devices',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --list-devices                      # List available devices
  %(prog)s "Hello world"                       # Play on all devices (simultaneously)
  %(prog)s "Welcome home" --volume 50          # All devices at volume 50
  %(prog)s "Good morning" --device Kitchen     # Play on specific device
  %(prog)s "Bonjour" --lang fr --device Bedroom
        """
    )

    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {__version__}'
    )

    parser.add_argument(
        'message',
        nargs='?',
        help='Text message to speak'
    )

    parser.add_argument(
        '--volume', '-v',
        type=int,
        metavar='N',
        help='Volume level (0-100), defaults to current volume'
    )

    parser.add_argument(
        '--lang', '-l',
        default='en',
        metavar='CODE',
        help='Language code (default: en). Examples: en, en-gb, es, fr, de'
    )

    parser.add_argument(
        '--timeout', '-t',
        type=int,
        default=5,
        metavar='SEC',
        help='Device discovery timeout in seconds (default: 5)'
    )

    parser.add_argument(
        '--device', '-d',
        metavar='NAME',
        help='Play on specific device by name. If not specified, plays on all devices.'
    )

    parser.add_argument(
        '--list-devices',
        action='store_true',
        help='List available Sonos devices and exit'
    )

    args = parser.parse_args()

    # Validate volume
    if args.volume is not None and not (0 <= args.volume <= 100):
        parser.error("Volume must be between 0 and 100")

    # Make message optional if just listing devices
    if args.list_devices and not args.message:
        args.message = None

    return args

def main():
    """Main entry point for the CLI."""
    args = parse_args()

    # Discovery
    devices = discover_devices(timeout=args.timeout)
    if not devices:
        return 1

    # If --list-devices flag, show devices and exit
    if args.list_devices:
        print("\nAvailable Sonos devices:")
        for device in devices:
            print(f"  - {device.player_name} ({device.ip_address})")
        return 0

    # Require message if not just listing
    if not args.message:
        print("Error: message is required (unless using --list-devices)")
        return 1

    # Determine which devices to use
    if args.device:
        # Find specific device by name
        target_devices = [d for d in devices if d.player_name.lower() == args.device.lower()]
        if not target_devices:
            print(f"Device '{args.device}' not found.")
            print("Available devices:")
            for device in devices:
                print(f"  - {device.player_name}")
            return 1
        print(f"Selected device: {target_devices[0].player_name}")
    else:
        # Use all devices
        target_devices = devices
        print(f"Playing on all {len(target_devices)} device(s)")

    # Generate TTS
    audio_file = generate_tts(args.message, lang=args.lang)
    if not audio_file:
        return 1

    # Start HTTP server
    server_result = start_http_server(audio_file)
    if not server_result:
        os.remove(audio_file)
        return 1

    server, audio_url = server_result

    try:
        # If playing on multiple devices, use grouping for synchronized playback
        if len(target_devices) > 1 and not args.device:
            # Check if devices are already grouped together
            existing_coordinator = check_if_grouped(target_devices)

            if existing_coordinator:
                # Use existing group
                device_names = ', '.join([d.player_name for d in target_devices])
                print(f"Using existing group: {device_names}")
                coordinator = existing_coordinator
                needs_ungroup = False
            else:
                # Create temporary group
                print("Creating temporary group for synchronized playback...")
                coordinator = create_group(target_devices)
                device_names = ', '.join([d.player_name for d in target_devices])
                print(f"Playing on group: {device_names}")
                needs_ungroup = True

            # Play on the group coordinator (plays on all grouped devices simultaneously)
            success = play_on_sonos(coordinator, audio_url, volume=args.volume)

            # Restore original grouping only if we created a temporary group
            if needs_ungroup:
                print("Restoring original speaker groups...")
                ungroup_all(target_devices)

            if not success:
                print("Warning: Playback failed")
        else:
            # Single device or specific device selected - play directly
            for device in target_devices:
                success = play_on_sonos(device, audio_url, volume=args.volume)
                if not success:
                    print(f"Warning: Playback failed on {device.player_name}")

    finally:
        # Cleanup
        print("\nCleaning up...")
        server.shutdown()
        time.sleep(0.5)

        try:
            os.remove(audio_file)
        except Exception as e:
            print(f"Warning: Could not delete temp file: {e}")

    print("\nDone!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
