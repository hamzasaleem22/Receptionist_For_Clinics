<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12%2B-blue?style=flat&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/LiveKit_Agents-1.2%2B-00D4AA?style=flat&logo=livekit" alt="LiveKit Agents">
  <img src="https://img.shields.io/badge/OpenAI-GPT_4o--mini-412991?style=flat&logo=openai" alt="OpenAI GPT-4o-mini">
  <img src="https://img.shields.io/badge/Deepgram-Nova_3-13EF93?style=flat&logo=deepgram" alt="Deepgram Nova 3">
  <img src="https://img.shields.io/badge/Cartesia-Sonic_3-FF6B35?style=flat" alt="Cartesia Sonic 3">
  <img src="https://img.shields.io/badge/Cal.com-API_v2-292929?style=flat&logo=cal.com" alt="Cal.com API">
  <img src="https://img.shields.io/badge/license-MIT-green?style=flat" alt="License">
</p>

<h1 align="center">🤖 Voice Receptionist for Clinics</h1>

<p align="center">
  <em>An AI-powered voice receptionist that answers phone calls, books appointments, handles rescheduling and cancellations — all through natural conversation.</em>
</p>

---

## ✨ Features

- **📞 Voice AI Receptionist** — Named "Jassey", handles inbound calls with warm, human-like conversation
- **🗣️ Natural Speech** — SSML-enriched responses with human-like pauses, filler words, and adaptive conversation flow
- **📅 Smart Booking** — Powered by Cal.com API v2: check availability, book, reschedule, or cancel appointments
- **🔊 Best-in-Class AI Pipeline** — Deepgram Nova-3 (STT) → GPT-4o-mini (LLM) → Cartesia Sonic-3 (TTS)
- **🎯 Adaptive Turn Detection** — Multilingual model with dynamic endpointing and adaptive interruption handling
- **🔇 Noise Cancellation** — ai-coustics Quail VF-S for clear audio in noisy environments
- **⚡ Pre-warmed VAD** — Silero VAD loaded at startup for low-latency voice activity detection
- **📊 Built-in Metrics** — Tracks LLM token usage and TTS performance per call
- **🐳 Docker-Ready** — Multi-stage UV-based build for production deployment

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    LiveKit Cloud                             │
│  (WebRTC signaling, room management, participant handling)  │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  Agent Server (AgentServer)                 │
│  - Prewarms Silero VAD model at job start                   │
│  - Manages agent lifecycle and job dispatch                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  AgentSession                               │
│  - STT: Deepgram Nova-3 (multilingual)                      │
│  - LLM: GPT-4o-mini (priority inference, max 150 tokens)   │
│  - TTS: Cartesia Sonic-3 (voice: custom preset)            │
│  - VAD: Silero (prewarmed, 0.5 threshold)                  │
│  - Noise cancellation: ai-coustics Quail VF-S              │
│  - Turn: Multilingual detection + dynamic endpointing       │
│  - Interruption: Adaptive (0.3s min, backchannel aware)    │
│  - Preemptive TTS enabled for faster response              │
└──────────────┬──────────────────────────────┬───────────────┘
               │                              │
               ▼                              ▼
      ┌─────────────────┐          ┌─────────────────────┐
      │  Assistant      │          │  CalToolset         │
      │  (Agent)        │◄────────►│  (Function Tools)   │
      │  - Conversation │          │  - list_event_types │
      │  - SSML speech  │          │  - check_availability│
      │  - Turn control │          │  - create_booking   │
      └─────────────────┘          │  - reschedule_booking│
                                   │  - cancel_booking   │
                                   └────────┬────────────┘
                                            │
                                            ▼
                                   ┌─────────────────┐
                                   │   Cal.com API v2 │
                                   │  (Booking System)│
                                   └─────────────────┘
```

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Agent Framework** | [LiveKit Agents](https://docs.livekit.io/agents/) v1.2+ |
| **Speech-to-Text** | Deepgram Nova-3 (multilingual) |
| **Language Model** | OpenAI GPT-4o-mini (priority inference, 150 max tokens) |
| **Text-to-Speech** | Cartesia Sonic-3 (custom voice preset) |
| **Voice Detection** | Silero VAD |
| **Turn Detection** | LiveKit Multilingual Model |
| **Noise Cancellation** | ai-coustics Quail VF-S |
| **Booking System** | Cal.com API v2 |
| **Deployment** | Docker (UV multi-stage build) |
| **Language** | Python 3.12+ |

## 📁 Project Structure

```
Receptionist_For_Clinics/
├── Receptionist/
│   ├── src/
│   │   ├── agent.py              # Main entry point + Assistant agent
│   │   └── cal_tools.py          # Cal.com API function tools
│   ├── pyproject.toml            # Python dependencies & metadata
│   ├── uv.lock                   # Locked dependencies (reproducible builds)
│   ├── Dockerfile                # Multi-stage production Docker image
│   ├── start.sh                  # Local development runner
│   ├── livekit.toml              # LiveKit Cloud project config
│   ├── .dockerignore
│   └── .gitignore
├── superpowers/
│   └── specs/
│       └── 2026-06-13-voice-receptionist-booking-memory.md  # Future roadmap
└── README.md
```

## 🚀 Getting Started

### Prerequisites

- Python 3.12+
- [UV](https://docs.astral.sh/uv/) package manager (`pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- LiveKit Cloud account (or self-hosted LiveKit server)
- Cal.com account with API key
- API keys: OpenAI, Deepgram, Cartesia, ai-coustics

### Environment Variables

Create a `.env.local` file in the `Receptionist/` directory:

```bash
# LiveKit
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret

# Cal.com
CAL_API_KEY=your_cal_api_key
CAL_USERNAME=your_cal_username

# AI Services
OPENAI_API_KEY=sk-...
DEEPGRAM_API_KEY=...
CARTESIA_API_KEY=...
AI_COUSTICS_API_KEY=...

# Optional — defaults to "Shifa Clinic"
COMPANY_NAME="Your Clinic Name"
```

### Local Development

```bash
cd Receptionist

# Install dependencies
uv sync

# Start the agent
chmod +x start.sh
./start.sh
```

Or directly:

```bash
cd Receptionist
uv run python3 src/agent.py start
```

### Docker Deployment

```bash
cd Receptionist

# Build the image
docker build -t receptionist-agent .

# Run with environment variables
docker run --env-file .env.local receptionist-agent
```

## 🧠 Agent Behavior

Jassey is designed to sound human, not robotic. Key behavior patterns:

- **Conversational SSML** — Every response includes `<break/>` tags at natural pause points (300ms hesitation, 750ms checking, 1s transitions)
- **Adaptive Flow** — No rigid step sequences. If the patient asks about slots, checks immediately. Only asks for name/email when booking.
- **Verbal Fillers** — "Um, let me check that for you…", "Hmm, let me look that up…" before tool calls
- **Self-Correction** — Drops the first version mid-sentence and restarts naturally
- **Warm Tone** — Calm, professional, conversational
- **Schedule Awareness** — Converts relative dates ("tomorrow", "next Monday") automatically

### Appointment Types

| Type | Slug | Duration |
|------|------|----------|
| General Consultation | `30min` | 30 min |
| Routine Checkup | `checkup` | 30 min |
| Follow-up Consultation | `follow-up` | 15 min |
| Urgent Consultation | `secret` | 15 min |
| New Patient Registration | `new-patient` | 45 min |

## 🔧 Tools

All booking operations go through Cal.com API function tools:

| Tool | Description |
|------|-------------|
| `list_event_types()` | List all available appointment types |
| `check_availability(slug, date)` | Check available time slots for a given date |
| `create_booking(slug, start, name, email, ...)` | Book a new appointment |
| `reschedule_booking(uid, new_start)` | Reschedule an existing appointment |
| `cancel_booking(uid)` | Cancel an appointment |

Features: 30-second slot caching, automatic retry with exponential backoff (max 3), human-readable event type names synced to Cal.com on startup.

## 📊 Metrics

The agent logs LLM and TTS metrics per call:
- **LLM**: Time to first token, duration, prompt/completion/total tokens, tokens/second
- **TTS**: Time to first byte, duration, audio duration, characters generated, cancelled status

## 🗺️ Roadmap

Planned enhancements (detailed in `superpowers/specs/`):

- **🧠 Patient Memory** — PostgreSQL database for returning patient recognition
- **📞 WhatsApp Telephony** — Full WhatsApp call integration with webhooks
- **📋 Booking History** — Persistent conversation summaries per patient
- **🏥 Multi-clinic Support** — Handle multiple clinic locations

## 📄 License

MIT
