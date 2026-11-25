"""
Instagram Group Chat Auto-Reply Bot (Local + Headless Version)
--------------------------------------------------------------
Watches an Instagram group chat in Chromium using Playwright.

Features:
- Case-insensitive multi-trigger & multi-output replies via TRIGGER_REPLIES
  (each trigger can map to a single string or a list of random replies).
- Visible setup mode (default) and headless background mode (`--headless`).
- Natural delay jitter (1.8s - 2.4s), 3s anti-spam cooldown, loop protection,
  and automatic page reload on Wi-Fi/page drops.

Intended for private, consenting group chats for entertainment purposes.
"""

import argparse
import random
import sys
import time
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

# --- Configuration (all local files stay next to real_bot.py) ---
SCRIPT_DIR = Path(__file__).resolve().parent
PROFILE_DIR = SCRIPT_DIR / "ig_profile"
CHAT_URL_FILE = SCRIPT_DIR / "chat_url.txt"
STATE_FILE = SCRIPT_DIR / "ig_state.json"

# Case-insensitive static triggers (keep keys lowercase).
# Each value can be a single string OR a list of strings (the bot picks one at random).
TRIGGER_REPLIES: dict[str, str | list[str]] = {
    "real": ["Real"],
    "bruh": ["Bruh", "Bro..."],
    "fr": ["Fr fr"],
    "cap": ["Stop the cap"],
    "badar k ho?": ["Chhakka", "Gay", "Badar more like Fatdar"],
    "skwaii k ho?": ["Chinker", "Chinese", "Chhakka ho"],
    "talai kasle banako?": ["Giri dada le"],
    "goat": ["Goat? Ko? Giri? Real"],
    "@sa.shang": ["Girlfriend sanga hola pakka", "Marisakyo tyo", "Khai k gardai hola mote"],
}

# Slight natural jitter around 2 seconds
REPLY_DELAY_MIN = 1.8
REPLY_DELAY_MAX = 2.4

# Minimum gap between bot replies (prevents spam-filter triggers if friends spam)
COOLDOWN_SECONDS = 3.0

CHECK_INTERVAL_SECONDS = 0.5
RELOAD_RETRY_SECONDS = 15.0
MAX_MISSING_PANE_CHECKS = 20  # ~10 seconds of missing chat pane triggers a reload

SCAN_MESSAGES_JS = """
({ markOnly }) => {
    const textboxes = Array.from(
        document.querySelectorAll('div[role="textbox"][contenteditable="true"]')
    );
    const textbox = textboxes[textboxes.length - 1];
    if (!textbox) {
        return { error: "no_textbox", messages: [] };
    }

    const tbRect = textbox.getBoundingClientRect();

    // Find the chat grid/pane that sits directly above the message textbox
    const grids = Array.from(document.querySelectorAll('div[role="grid"]'));
    let chatPane = grids.find((g) => {
        const r = g.getBoundingClientRect();
        return r.width > 200 && r.left >= tbRect.left - 120 && r.right <= tbRect.right + 120;
    });

    if (!chatPane) {
        let node = textbox.parentElement;
        while (node && node !== document.body) {
            const r = node.getBoundingClientRect();
            if (r.height > 300 && r.width >= tbRect.width) {
                chatPane = node;
                break;
            }
            node = node.parentElement;
        }
    }

    if (!chatPane) {
        return { error: "no_chat_pane", messages: [] };
    }

    const paneRect = chatPane.getBoundingClientRect();
    const candidates = chatPane.querySelectorAll('div[dir="auto"], span[dir="auto"]');
    const newMessages = [];

    for (const el of candidates) {
        if (el.dataset.realBotSeen === "1") continue;
        if (el.closest('div[role="textbox"]')) continue;
        if (el.querySelector('div[dir="auto"], span[dir="auto"]')) continue;

        const rect = el.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) continue;
        if (rect.bottom > tbRect.top) continue;

        const text = (el.innerText || "").trim();
        if (!text) continue;

        el.dataset.realBotSeen = "1";
        if (markOnly) continue;

        const distFromLeft = rect.left - paneRect.left;
        const distFromRight = paneRect.right - rect.right;
        const isOutgoing = distFromLeft > distFromRight;

        newMessages.push({ text, isOutgoing });
    }

    return { error: null, messages: newMessages };
}
"""


def compute_reply(text: str) -> str | None:
    """Return the matching reply for an incoming message, or None if ignored."""
    lowered = text.lower()
    if lowered not in TRIGGER_REPLIES:
        return None

    option = TRIGGER_REPLIES[lowered]
    if isinstance(option, list):
        return random.choice(option) if option else None
    return option


def send_reply(page, text: str) -> bool:
    """Click the message box, type real keystrokes (Lexical-compatible), and press Enter."""
    textbox = page.locator('div[role="textbox"][contenteditable="true"]').last
    if textbox.count() == 0:
        print("Could not find the message box.", flush=True)
        return False

    textbox.click()
    page.keyboard.type(text, delay=random.randint(25, 50))
    page.keyboard.press("Enter")
    return True


def is_login_or_challenge(url: str) -> bool:
    """Return True if Instagram redirected to a login or verification screen."""
    lowered = url.lower()
    return "/accounts/login" in lowered or "/challenge" in lowered or "/checkpoint" in lowered


def save_chat_url(url: str) -> None:
    """Save the group chat URL to chat_url.txt right next to real_bot.py."""
    CHAT_URL_FILE.write_text(url.strip() + "\n", encoding="utf-8")
    print(f"Saved group chat URL to: {CHAT_URL_FILE}", flush=True)


def open_and_sync_chat(page, chat_url: str, headless: bool) -> bool:
    """Navigate to chat_url, wait for the message box, and mark existing messages seen."""
    try:
        page.goto(chat_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_selector(
            'div[role="textbox"][contenteditable="true"]',
            timeout=25000,
        )
    except PlaywrightError:
        if is_login_or_challenge(page.url):
            print(
                "\nInstagram asked for login or security verification.\n"
                "Run once WITHOUT --headless to log in/verify, then switch back to --headless.",
                flush=True,
            )
            if headless:
                sys.exit(1)
        return False

    time.sleep(1.5)
    res = page.evaluate(SCAN_MESSAGES_JS, {"markOnly": True})
    return res.get("error") is None


def resolve_chat_url(cli_url: str) -> str:
    """Return --chat-url if provided (and save it), otherwise load from chat_url.txt."""
    if cli_url.strip():
        save_chat_url(cli_url.strip())
        return cli_url.strip()
    if CHAT_URL_FILE.exists():
        saved = CHAT_URL_FILE.read_text(encoding="utf-8").strip()
        if saved:
            return saved
    return ""


def get_active_chat_page(context):
    """Find whichever open tab has the Instagram Direct chat open."""
    for p in reversed(context.pages):
        if not p.is_closed() and "/direct/t/" in p.url:
            return p
    for p in reversed(context.pages):
        if not p.is_closed() and "instagram.com" in p.url:
            return p
    return context.pages[0]


def export_session() -> None:
    """Export portable cookies from ./ig_profile into ig_state.json offline."""
    if not PROFILE_DIR.exists():
        print("No ig_profile folder found yet. Run real_bot.py normally to log in first.", flush=True)
        sys.exit(1)

    print("Exporting saved cookies from ig_profile to ig_state.json (offline)...", flush=True)
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=True,
            viewport={"width": 1280, "height": 850},
        )
        try:
            state = context.storage_state(path=str(STATE_FILE))
            ig_cookies = [c for c in state.get("cookies", []) if "instagram.com" in c.get("domain", "")]
            has_session = any(c.get("name") == "sessionid" for c in ig_cookies)
            print(f"Exported {len(ig_cookies)} Instagram cookies to: {STATE_FILE}", flush=True)
            if has_session:
                print("Verified: active Instagram login session (sessionid) found!", flush=True)
            else:
                print(
                    "Warning: no 'sessionid' cookie found. Make sure you are logged in inside ig_profile.",
                    flush=True,
                )
            print("Keep ig_state.json private (it contains your bot's login cookies).", flush=True)
        finally:
            context.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Instagram group chat auto-reply bot.")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run invisibly in the background (requires saved login + chat URL).",
    )
    parser.add_argument(
        "--chat-url",
        default="",
        help="Direct URL of your Instagram group chat (e.g. https://www.instagram.com/direct/t/12345/).",
    )
    parser.add_argument(
        "--export-session",
        action="store_true",
        help="Export login cookies from ig_profile into portable ig_state.json.",
    )
    args = parser.parse_args()

    if args.export_session:
        export_session()
        return

    chat_url = resolve_chat_url(args.chat_url)

    if args.headless and not chat_url:
        print(
            "No saved group chat URL found yet.\n"
            "Run once WITHOUT --headless first so the bot can save your group chat URL, "
            "or pass --chat-url \"https://www.instagram.com/direct/t/YOUR_CHAT_ID/\".",
            flush=True,
        )
        sys.exit(1)

    mode_label = "headless (background)" if args.headless else "visible"
    print(f"Launching Chromium in {mode_label} mode...", flush=True)

    with sync_playwright() as p:
        browser = None
        use_state_file = args.headless and STATE_FILE.exists() and not PROFILE_DIR.exists()

        if use_state_file:
            print(f"Loading portable session from {STATE_FILE.name}...", flush=True)
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                storage_state=str(STATE_FILE),
                viewport={"width": 1280, "height": 850},
            )
            page = context.new_page()
        else:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE_DIR),
                headless=args.headless,
                viewport={"width": 1280, "height": 850},
            )
            page = context.pages[0] if context.pages else context.new_page()

        if args.headless:
            print(f"Opening saved group chat: {chat_url}", flush=True)
            while not open_and_sync_chat(page, chat_url, headless=True):
                print(
                    f"Could not load chat (network or Instagram blip). Retrying in {RELOAD_RETRY_SECONDS:.0f}s...",
                    flush=True,
                )
                time.sleep(RELOAD_RETRY_SECONDS)
            if use_state_file:
                context.storage_state(path=str(STATE_FILE))
            print("Connected in headless mode! Watching for new messages...", flush=True)
        else:
            start_url = chat_url or "https://www.instagram.com/direct/inbox/"
            page.goto(start_url, wait_until="domcontentloaded")
            print("\n" + "=" * 60, flush=True)
            print("1. Make sure you are logged in to your bot account.", flush=True)
            print("2. Open your friends' group chat in the browser window.", flush=True)
            print("3. Come back here and press ENTER to start watching.", flush=True)
            print("=" * 60 + "\n", flush=True)
            input("Press ENTER once your group chat is open... ")

            page = get_active_chat_page(context)
            live_url = page.evaluate("() => window.location.href") or page.url
            print(f"Detected browser URL: {live_url}", flush=True)

            chat_url = live_url
            save_chat_url(chat_url)
            context.storage_state(path=str(STATE_FILE))
            print(f"Saved portable session to: {STATE_FILE}", flush=True)

            if "/direct/t/" not in live_url:
                print(
                    "Note: URL does not contain '/direct/t/'. Make sure you clicked inside "
                    "the group chat (not just the inbox list) before pressing ENTER.",
                    flush=True,
                )

            init_res = page.evaluate(SCAN_MESSAGES_JS, {"markOnly": True})
            if init_res.get("error"):
                print(
                    f"Warning: couldn't detect open chat ({init_res['error']}). "
                    "Make sure a group chat is open in the browser window.",
                    flush=True,
                )
            else:
                print("Connected to open group chat! Watching for new messages...", flush=True)

        print("Press Ctrl+C here to stop.\n", flush=True)

        last_reply_time = 0.0
        missing_pane_streak = 0

        try:
            while True:
                if page.is_closed():
                    print("Browser window was closed. Stopping bot.", flush=True)
                    break

                try:
                    res = page.evaluate(SCAN_MESSAGES_JS, {"markOnly": False})
                except PlaywrightError as exc:
                    print(
                        f"Connection/page error ({exc}). Reloading in {RELOAD_RETRY_SECONDS:.0f}s...",
                        flush=True,
                    )
                    time.sleep(RELOAD_RETRY_SECONDS)
                    if open_and_sync_chat(page, chat_url, headless=args.headless):
                        print("Reconnected to group chat!", flush=True)
                        missing_pane_streak = 0
                    continue

                if res.get("error"):
                    missing_pane_streak += 1
                    if missing_pane_streak >= MAX_MISSING_PANE_CHECKS:
                        print(
                            "Chat pane disappeared (possible disconnect or refresh). Reloading...",
                            flush=True,
                        )
                        if open_and_sync_chat(page, chat_url, headless=args.headless):
                            print("Reconnected to group chat!", flush=True)
                            missing_pane_streak = 0
                        else:
                            time.sleep(RELOAD_RETRY_SECONDS)
                    time.sleep(CHECK_INTERVAL_SECONDS)
                    continue

                missing_pane_streak = 0

                for item in res.get("messages", []):
                    text = item["text"]
                    if item["isOutgoing"]:
                        continue

                    print(f"[Incoming] {text!r}", flush=True)

                    reply_text = compute_reply(text)
                    if not reply_text:
                        continue

                    now = time.monotonic()
                    since_last = now - last_reply_time
                    if since_last < COOLDOWN_SECONDS:
                        remaining = COOLDOWN_SECONDS - since_last
                        print(
                            f"--> Trigger matched, skipped (cooldown: {remaining:.1f}s left).",
                            flush=True,
                        )
                        continue

                    delay = random.uniform(REPLY_DELAY_MIN, REPLY_DELAY_MAX)
                    print(f"--> Matched '{text.lower()}'! Waiting {delay:.2f}s...", flush=True)
                    time.sleep(delay)

                    if send_reply(page, reply_text):
                        last_reply_time = time.monotonic()
                        print(f"--> Replied: {reply_text!r}", flush=True)
                        time.sleep(0.8)
                        page.evaluate(SCAN_MESSAGES_JS, {"markOnly": True})
                        if use_state_file:
                            context.storage_state(path=str(STATE_FILE))

                time.sleep(CHECK_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("\nBot stopped.", flush=True)
        finally:
            context.close()
            if browser:
                browser.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Error: {type(exc).__name__}: {exc}", flush=True)
        sys.exit(1)