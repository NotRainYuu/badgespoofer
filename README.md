# BadgeSpoofer

# ReadMe.md is generate by gemini

> A lightweight, asynchronous-style Discord Science & Analytics Spoofer for game activity, playtime hours, and profile badges.

---

## Features

- **🎮 Spoof Playtime**: Emulate and boost recorded playtime hours across hundreds of detectable games.
- **🕹️ Spoof Played Games Count**: Quickly register activity across games to show up on your profile.
- **🛡️ HypeSquad Badge Switcher**: Instantly switch between House of Bravery, Brilliance, Balance, or remove your HypeSquad badge.
- **⚡ Zero External Dependencies**: Built entirely with Python standard libraries (`urllib`, `dataclasses`, `json`, `uuid`, etc.). No `pip install` required.
- **🔒 Session & Payload Emulation**: Accurately mimics official Discord desktop client telemetry events (heartbeats, launch signatures, and super properties).

---

## Requirements

- **Python 3.10+** (Windows / macOS / Linux)

---

## Quick Start

1. **Clone the repository:**
   ```bash
   git clone https://github.com/NotRainYuu/badgespoofer.git
   cd badgespoofer
   ```

2. **Run the script:**
   ```bash
   python main.py
   ```

3. **Follow the on-screen interactive prompts:**
   - Input your Discord account **Token** when prompted.
   - Input your Discord account **Cookie** (from your browser headers) when prompted for Science API validation.
   - Select the desired operation from the interactive menu.

---

## Menu Options

```text
  1  Spoof Playtime (Boost total playtime hours)
  2  Spoof Games Played (For played games badge)
  3  Set / Switch HypeSquad Badge
  4  Update Credentials (Token / Cookie)
  5  Exit
```

---

## Disclaimer

This software is for educational and research purposes only. Using automated tools on Discord may violate Discord's Terms of Service. Use at your own risk.
