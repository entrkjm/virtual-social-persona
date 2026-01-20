# Virtual Agent 🤖

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**Autonomous AI Agent for Social Media** - A human-like Twitter bot powered by LLM intelligence.

[한국어 README](./README_KR.md)

---

## ✨ Features

- 🧠 **3-Layer Intelligence**: Core identity + Learned interests + Real-time trends
- 💾 **Dynamic Memory**: Experience → Inspiration → Long-term memory (with decay/reinforcement)
- 🎭 **Human-like Behavior**: Mood fluctuations, fatigue system, personality traits
- 🔄 **Independent Actions**: Like/Repost/Reply probabilities calculated separately
- 🔌 **Platform Agnostic**: Adapter pattern for easy platform switching
- 👥 **Multi-Persona**: Run multiple personas with environment variables

---

## 🚀 Quick Start

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/virtual.git
cd virtual

# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your API keys

# Run
python main.py
```

---

## 🔧 Configuration

### Required Environment Variables

```env
# LLM (Choose one)
GEMINI_API_KEY=your_gemini_key
# or USE_VERTEX_AI=true with GCP credentials

# Twitter (Cookie-based auth - recommended)
TWITTER_AUTH_TOKEN=your_auth_token
TWITTER_CT0=your_ct0_token
```

### Getting Twitter Cookies

1. Login to twitter.com in your browser
2. Open DevTools → Application → Cookies → twitter.com
3. Copy `auth_token` and `ct0` values
4. Or use: `python scripts/manage_cookies.py import cookies.json`

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                        main.py                          │
│                    (Entry Point)                        │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                      SocialAgent                        │
│                      (bot.py)                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │   Scout     │→ │   Perceive  │→ │   Decide/Act    │ │
│  │ (Search)    │  │ (LLM Intel) │  │ (Behavior Eng)  │ │
│  └─────────────┘  └─────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌───────────┐   ┌───────────┐   ┌───────────┐
    │  Memory   │   │  Persona  │   │  Platform │
    │  System   │   │  Loader   │   │  Adapter  │
    │ (SQLite+  │   │ (YAML)    │   │ (Twitter) │
    │  Chroma)  │   │           │   │           │
    └───────────┘   └───────────┘   └───────────┘
```

---

## 📁 Project Structure

```
virtual/
├── agent/                    # Core Agent Logic
│   ├── bot.py               # Main workflow orchestrator
│   ├── core/                # Platform-independent modules
│   ├── memory/              # Memory system (DB, Vector, Session)
│   ├── persona/             # Persona loading
│   └── platforms/           # Platform adapters
│       └── twitter/         # Twitter implementation
│           ├── adapter.py   # Platform adapter
│           ├── api/         # API wrapper (twikit)
│           └── modes/       # Execution modes
│               ├── casual/  # Independent posting
│               ├── social/  # Interaction & replies
│               └── series/  # Themed content series
│
├── personas/                # Persona configurations
│   └── chef_choi/          # Example: Chef persona
│       ├── identity.yaml   # Core identity
│       ├── speech_style.yaml
│       └── platforms/twitter/
│
├── core/                    # Shared utilities
│   └── llm.py              # Multi-LLM client
│
├── scripts/                 # Utility scripts
│   └── manage_cookies.py   # Cookie management CLI
│
└── docs/                    # Documentation
```

---

## 🎭 Multi-Persona Deployment

Run multiple personas on one machine:

```bash
# Terminal 1 - Persona A
PERSONA_NAME=chef_choi python main.py

# Terminal 2 - Persona B (different Twitter account)
PERSONA_NAME=client_a \
TWITTER_AUTH_TOKEN="client_a_token" \
TWITTER_CT0="client_a_ct0" \
python main.py
```

Using `screen` for background:
```bash
screen -S chef
PERSONA_NAME=chef_choi python main.py
# Ctrl+A, D to detach

screen -ls  # List sessions
screen -r chef  # Reattach
```

---

## 📊 Execution Modes

| Mode | Description |
|------|-------------|
| `normal` | Standard operation with sleep schedules |
| `test` | Fast iterations, no rate limiting |
| `aggressive` | Maximum activity, no breaks |

```bash
AGENT_MODE=aggressive python main.py
```

---

## 🛡️ Platform Sustainability

This project uses `twikit` (unofficial Twitter library) which may break when Twitter updates their internal API. The codebase is designed with an **Adapter Pattern** to minimize impact:

- All Twitter-specific code is isolated in `agent/platforms/twitter/`
- `bot.py` only uses abstract `SocialPlatformAdapter` interface
- Switching to Playwright or official API requires only adapter changes

---

## 📚 Documentation

- [Deployment Guide](./docs/DEPLOYMENT_STRATEGY.md)
- [Memory System Design](./docs/MEMORY_SYSTEM_DESIGN.md)
- [Changelog](./docs/CHANGELOG_20260120.md)

---

## 📄 License

MIT License - See [LICENSE](./LICENSE) for details.

---

## ⚠️ Disclaimer

This project is for educational purposes. Use responsibly and comply with Twitter's Terms of Service. The authors are not responsible for any misuse or account suspensions.
