# Sonos Text-to-Speech Tool Design

**Date:** 2026-02-14
**Status:** Approved

## Overview

A reusable Python CLI tool that enables text-to-speech playback on Sonos devices. Users can discover available Sonos devices on their network, select one, and have it speak any text message using Google's text-to-speech service.

## Requirements

- Text-to-speech capability on Sonos devices
- Reusable tool that can be run with different messages
- Python implementation using the `soco` library
- Auto-discover Sonos devices with user selection from a list
- Non-disruptive: preserve and restore playback state

## Architecture

The tool operates in three phases:

1. **Discovery Phase**: Scan network for Sonos devices using `soco`, present numbered list for user selection
2. **TTS Generation Phase**: Convert text to audio using Google TTS (`gTTS`)
3. **Playback Phase**: Serve audio via temporary HTTP server, play on Sonos, cleanup

The script preserves the current Sonos state (playback, volume, position) and restores it after the TTS message completes.

## Components

### Main Script: `sonos_tts.py`

CLI entry point with argument parsing for message text and optional volume control.

### Key Functions

- `discover_devices()` - Uses `soco.discovery.discover()` to find Sonos devices, returns list with friendly names and IPs
- `select_device(devices)` - Displays numbered list, prompts user selection, returns device object
- `generate_tts(text)` - Uses gTTS to create MP3 audio, returns file path or bytes
- `play_on_sonos(device, audio_url)` - Saves current state, plays TTS, restores previous state
- `serve_audio(audio_file)` - Starts temporary HTTP server on random port, returns URL, handles auto-cleanup

### Dependencies

- `soco` - Sonos control library
- `gTTS` - Google Text-to-Speech
- `http.server` - Built-in Python module for serving audio
- `tempfile` - Temporary audio file storage

## Data Flow

1. User runs CLI with message text and optional flags
2. Script discovers Sonos devices and displays numbered list
3. User selects device by number
4. Script captures current Sonos state (URI, position, volume, play/pause)
5. Text sent to gTTS API, MP3 audio generated and saved to temp file
6. HTTP server starts on localhost with random port
7. Sonos device receives play command with HTTP URL
8. Device streams and plays audio
9. Script restores previous Sonos state
10. HTTP server shuts down and temp file deleted

## Error Handling

### Network Issues
- No Sonos devices found → Display: "No Sonos devices discovered. Make sure you're on the same network."
- Device unavailable during operation → Catch connection errors, inform user, exit gracefully

### TTS Failures
- No internet connection → Display: "Cannot reach Google TTS. Check your internet connection."
- Empty message text → Validate input, require at least 1 character

### Playback Issues
- HTTP server port conflict → Retry with different random port (up to 3 attempts)
- Sonos refuses URL → Log error, attempt state restoration anyway

### State Restoration
- Restoration failure → Log warning but don't crash: "Could not restore previous playback state."

**General Principle:** Fail gracefully with clear messages, always attempt cleanup even on errors.

## Testing Strategy

### Manual Testing
- Discovery with single and multiple devices
- Playback with short and long messages
- Volume control functionality
- State restoration verification

### Edge Cases
- Empty device list
- User cancellation (Ctrl+C)
- Very long text messages
- Special characters (emojis, unicode)

### Code Quality
- Clear function names and docstrings
- Inline comments for non-obvious logic
- Focused, single-purpose functions

No automated tests needed - manual verification is sufficient for this hardware-dependent personal utility tool.

## Implementation Approach

Using Google TTS (gTTS) with local HTTP server provides the best balance of:
- Quality: Natural-sounding voices
- Cost: Free for personal use
- Simplicity: Minimal setup, no API keys required
- Reliability: Well-maintained libraries

Alternative approaches (Amazon Polly, local TTS engines) were considered but rejected due to cost/complexity or poor audio quality respectively.
