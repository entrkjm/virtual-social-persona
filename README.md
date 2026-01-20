# 🤖 Virtual Agent - AI Persona Framework

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**Create your own AI personality for Twitter.** Build autonomous social media agents with unique personas, memories, and human-like behaviors.

[한국어 README](./README_KR.md)

---

## 🎯 What is This?

A framework for creating **AI personas** that can:
- 🐦 Post original content on Twitter
- 💬 Reply to others with personality
- 🧠 Remember past interactions
- 😊 Express moods and emotions
- 📈 Learn from trending topics

### 🍳 Demo Persona: Chef Choi

Inspired by Korean cooking show "흑백요리사" (Culinary Class Wars), we include **Chef Choi** as a working example.

> **See it live**: [@ChoigangrokV](https://twitter.com/ChoigangrokV)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🎭 **Multi-Persona** | Swap personalities via YAML config |
| 🧠 **3-Layer Intelligence** | Core identity + Learned interests + Real-time trends |
| 💾 **Dynamic Memory** | Experiences become inspirations, then long-term memories |
| � **Human-like Behavior** | Mood swings, fatigue, personality quirks |
| 🔌 **Platform Agnostic** | Adapter pattern for easy platform switching |
| � **Independent Actions** | Like/Repost/Reply calculated separately |

---

## 🚀 Quick Start

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/virtual.git
cd virtual

# Install
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your API keys (see Configuration below)

# Run demo persona (Chef Choi)
python main.py

# Or run your own persona
PERSONA_NAME=my_persona python main.py
```

---

## 🎨 Create Your Own Persona

```bash
# 1. Copy template
cp -r personas/_template personas/my_persona

# 2. Edit identity
nano personas/my_persona/identity.yaml
```

**identity.yaml** example:
```yaml
name: "My Bot"
role: "A friendly AI assistant"
personality:
  - curious
  - helpful
  - witty
core_topics:
  - technology
  - productivity
  - AI trends
```

```bash
# 3. Run it!
PERSONA_NAME=my_persona python main.py
```

---

## 🔧 Configuration

### Required Environment Variables

```env
# LLM (Gemini recommended)
GEMINI_API_KEY=your_gemini_key

# Twitter Authentication (Cookie-based)
TWITTER_AUTH_TOKEN=your_auth_token
TWITTER_CT0=your_ct0_token
```

### Getting Twitter Cookies

1. Login to twitter.com in your browser
2. DevTools (F12) → Application → Cookies → twitter.com
3. Copy `auth_token` and `ct0` values

Or use our helper script:
```bash
python scripts/manage_cookies.py import cookies.json
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      SocialAgent                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │   Scout     │→ │   Perceive  │→ │   Decide/Act    │ │
│  │ (Search)    │  │ (LLM Intel) │  │ (Behavior Eng)  │ │
│  └─────────────┘  └─────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────┘
           │               │               │
           ▼               ▼               ▼
    ┌───────────┐   ┌───────────┐   ┌───────────┐
    │  Memory   │   │  Persona  │   │  Platform │
    │ (SQLite+  │   │  (YAML)   │   │ (Twitter) │
    │  Vector)  │   │           │   │           │
    └───────────┘   └───────────┘   └───────────┘
```

---

## 📁 Project Structure

```
virtual/
├── agent/                    # Core agent logic
│   ├── bot.py               # Main workflow
│   ├── memory/              # Memory system
│   └── platforms/twitter/   # Twitter adapter
│
├── personas/                # 🎭 Persona configs
│   ├── _template/          # Start here!
│   └── chef_choi/          # Demo: Chef Choi
│
├── scripts/
│   └── manage_cookies.py   # Cookie helper
│
└── docs/                    # Documentation
```

---

## 🎭 Multi-Persona Deployment

Run multiple personas on one machine:

```bash
# Terminal 1
PERSONA_NAME=chef_choi python main.py

# Terminal 2 (different Twitter account)
PERSONA_NAME=my_bot \
TWITTER_AUTH_TOKEN="other_token" \
TWITTER_CT0="other_ct0" \
python main.py
```

---

## 📊 Execution Modes

| Mode | Description |
|------|-------------|
| `normal` | Standard with sleep schedules |
| `aggressive` | Maximum activity, no breaks |

```bash
AGENT_MODE=aggressive python main.py
```

---

## ⚠️ Platform Notice

This project uses `twikit` (unofficial Twitter library). If Twitter updates their internal API, it may break. The codebase uses an **Adapter Pattern** to minimize impact - switching to Playwright or official API requires only adapter changes.

---

## 📚 Documentation

- [Deployment Guide](./docs/DEPLOYMENT_STRATEGY.md)
- [Memory System](./docs/MEMORY_SYSTEM_DESIGN.md)
- [Changelog](./docs/CHANGELOG_20260120.md)

---

## 🤝 Contributing

1. Fork this repo
2. Create your persona in `personas/`
3. Share your config (if you want!)

---

## 📄 License

MIT License - See [LICENSE](./LICENSE)

---

## ⚠️ Disclaimer

This project is for educational purposes. Use responsibly and comply with Twitter's Terms of Service. The authors are not responsible for any misuse or account suspensions.

**Chef Choi persona** is a fan-made tribute inspired by Korean TV show "흑백요리사". No copyright infringement intended.
