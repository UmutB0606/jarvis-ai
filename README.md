# jarvis-ai 🤖

A real-time voice assistant powered by Google Gemini Live API. Speak naturally — Jarvis listens, thinks, and responds through your speakers.

## Features

- 🎙️ **Voice I/O** — Mic input → Gemini Live → speaker output, fully real-time
- 🎵 **Spotify control** — Play songs, skip tracks, control playback by voice
- 🖱️ **Mouse & keyboard control** — Automate clicks and typing via `pyautogui`
- 🔧 **Tool system** — Extensible function-calling architecture (web search, system actions, etc.)

## Requirements

- Python 3.11+
- A Google Gemini API key
- Spotify account (for music control)

## Setup

```bash
git clone https://github.com/UmutB0606/jarvis-ai.git
cd jarvis-ai
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
GEMINI_API_KEY=your_api_key_here
```

## Usage

```bash
py -3.11 jarvis.py
```

Once you see `✅ Jarvis hazır!`, start talking. Jarvis will listen continuously and respond in real time.

## Example Commands

- *"Spotify'da Lo-fi çal"*
- *"Mouse'u sağ üste götür ve tıkla"*
- *"Hava durumu nedir?"*

## Tech Stack

- `google-genai` — Gemini Live API
- `pyaudio` — Microphone & speaker I/O
- `spotipy` — Spotify Web API
- `pyautogui` — Mouse & keyboard automation
