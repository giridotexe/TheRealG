# Instagram "Real" Auto-Reply Bot

A lightweight Python + Playwright bot that watches a private Instagram group chat and automatically replies **`Real`** (after a ~2-second delay) whenever another member sends `real` or `Real`.

Built for entertainment in private, consenting group chats.

## Features

- **Real browser session:** Uses [Playwright](https://playwright.dev/python/) with Chromium and saves your login locally in `ig_profile/` so you only log in once.
- **Headless background mode (`--headless`):** Runs quietly without a visible browser window after your one-time setup.
- **Loop protection:** Ignores older chat history on startup and skips its own outgoing messages so it never replies to itself.
- **Natural pacing & anti-spam:** Adds slight random delay jitter (`1.8s–2.4s`) before replying and enforces a `10s` cooldown between replies.
- **Auto-recovery:** Automatically reloads the group chat and re-syncs if your Wi-Fi drops or Instagram refreshes the page.
- **Automatic chat saving:** Saves your open group chat URL to `chat_url.txt` automatically during first-time setup.

## Prerequisites

- **Python 3.11+**
- A dedicated throwaway Instagram account already added to your group chat (with the group chat invite accepted).
- A home Wi-Fi or personal mobile connection (restricted corporate/office Wi-Fi networks may block Instagram Web).

## Installation

### Windows (PowerShell)

```powershell
git clone https://github.com/giridotexe/TheRealG.git
cd TheRealG

py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
```

### macOS / Linux

```bash
git clone https://github.com/giridotexe/TheRealG.git
cd TheRealG

python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m playwright install chromium
```

## Usage

### 1. First-time setup (visible browser)

Run the script once in visible mode so you can log in and save your group chat URL:

```powershell
# Windows
.\.venv\Scripts\python.exe real_bot.py

# macOS / Linux
./.venv/bin/python real_bot.py
```

1. In the Chromium window that opens, log in to your bot's Instagram account.
2. Click to open your friends' group chat.
3. Return to the terminal and press **Enter**.
4. Confirm it prints `Saved group chat URL to: ...chat_url.txt` and `Connected to open group chat!`.
5. Press **Ctrl+C** when you're ready to switch to headless mode.

### 2. Run in headless mode (no browser window)

Once `ig_profile/` and `chat_url.txt` are saved, run invisibly in the background:

```powershell
# Windows
.\.venv\Scripts\python.exe real_bot.py --headless

# macOS / Linux
./.venv/bin/python real_bot.py --headless
```

Press **Ctrl+C** in the terminal anytime to stop the bot.

### Command-line options

| Flag | Description |
| :--- | :--- |
| *(none)* | Launches a visible Chromium window for login, selecting a group chat, and live watching. |
| `--headless` | Runs without a visible browser window using your saved `ig_profile/` and `chat_url.txt`. |
| `--chat-url "URL"` | Directly sets and saves the group chat URL (e.g. `https://www.instagram.com/direct/t/123456789/`). |
| `--export-session` | Exports saved Instagram cookies from `ig_profile/` into a portable `ig_state.json` file offline. |

## Configuration

You can customize the bot's behavior by editing the constants at the top of `real_bot.py`:

| Setting | Default | Description |
| :--- | :--- | :--- |
| `TRIGGERS` | `{"real", "Real"}` | Exact message strings that trigger a reply. |
| `REPLY_TEXT` | `"Real"` | The reply message sent by the bot. |
| `REPLY_DELAY_MIN` / `MAX` | `1.8` / `2.4` | Random delay range (in seconds) before replying. |
| `COOLDOWN_SECONDS` | `10.0` | Minimum wait (in seconds) between bot replies. |
| `CHECK_INTERVAL_SECONDS` | `0.5` | How often the script checks the open chat for new messages. |

## Project Files & Privacy

Keep the following local files out of Git (already listed in `.gitignore`):

- `ig_profile/` — Local Chromium browser profile containing your logged-in Instagram session.
- `ig_state.json` / `session.json` — Exported Instagram session cookies.
- `chat_url.txt` — Your private group chat URL.
- `.venv/` — Local Python virtual environment.

**Never commit or share `ig_profile/` or `ig_state.json`**, as anyone with those files can access the bot's Instagram account.

## Troubleshooting

- **Instagram asks for login or security verification in headless mode:** Stop the script (`Ctrl+C`), run once **without** `--headless`, complete the login/verification in the browser window, press **Enter**, then switch back to `--headless`.
- **`chat_url.txt` wasn't saved with a `/direct/t/...` link:** Open your group chat in Instagram Web, copy the full URL from the address bar, and paste it into `chat_url.txt` (or pass it with `--chat-url`).
- **Bot doesn't reply when testing from the bot account:** By design, the bot ignores its own outgoing messages to prevent infinite loops. Send `real` from a friend's account or your main account to test it.

## Disclaimer

This project uses unofficial browser automation for personal entertainment in private, consenting group chats. Automating Instagram accounts carries a risk of temporary security checks or account suspension—always use a separate throwaway account that is not linked to your primary Instagram profile.
