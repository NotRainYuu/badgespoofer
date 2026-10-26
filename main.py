

from __future__ import annotations

import base64
import getpass
import json
import random
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator, Sequence

ROOT = Path(__file__).resolve().parent
GAMES_FILE = ROOT / "games.json"
GAMES_FILE_ALT = ROOT.parent / "data" / "games.json"
STATE_FILE_PRIMARY = ROOT / "science_state.json"
STATE_FILE_V2 = ROOT / "config.json"


ME_URL = "https://discord.com/api/v9/users/@me?with_analytics_token=true"
SCIENCE_URL = "https://discord.com/api/v9/science"
GAMES_CDN_URL = "https://cdn.discordapp.com/detectables/games.json"
HYPESQUAD_URL = "https://discord.com/api/v9/hypesquad/online"

BATCH_SIZE = 100
BATCH_DELAY = 0.3
AUTH_MAX_AGE = 12 * 3600
DEBUG = False


CLIENT_VERSION = "1.0.9264"
FALLBACK_BUILD_NUMBER = 643186
NATIVE_BUILD_NUMBER = 96127
OS_VERSION = "10.0.26100"
USER_AGENT = (
    f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    f"(KHTML, like Gecko) discord/{CLIENT_VERSION} Chrome/148.0.7778.280 "
    f"Electron/42.11.15 Safari/537.36"
)


class Console:


    RED = "\x1b[91m"
    ORANGE = "\x1b[38;5;208m"
    GREEN = "\x1b[92m"
    LIME = "\x1b[38;5;82m"
    PURPLE = "\x1b[38;5;141m"
    YELLOW = "\x1b[93m"
    WHITE = "\x1b[97m"
    GREY = "\x1b[90m"
    RESET = "\x1b[0m"
    RULE = "─" * 44

    def __init__(self) -> None:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
        if sys.platform == "win32":
            self._enable_ansi()

    @staticmethod
    def _enable_ansi() -> None:
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetStdHandle(-11)
            if handle and handle != -1:
                mode = ctypes.c_uint32()
                if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                    kernel32.SetConsoleMode(handle, mode.value | 0x0004)
        except Exception:
            pass

    def _stamp(self) -> str:
        return f"{self.GREY}{time.strftime('%H:%M:%S')}{self.RESET}"

    def _line(self, glyph: str, target: str, detail: str, color: str) -> None:
        print(f"  {self._stamp()} {glyph} {self.WHITE}{target}{self.RESET} "
              f"{self.GREY}·{self.RESET} {color}{detail}{self.RESET}")

    def ok(self, target: str, detail: str) -> None:
        self._line(f"{self.LIME}✓{self.RESET}", target, detail, self.LIME)

    def sent(self, target: str, detail: str) -> None:
        self._line(f"{self.GREY}·{self.RESET} {self.LIME}SENT{self.RESET}", target, detail, self.LIME)

    def warn(self, target: str, detail: str) -> None:
        self._line(f"{self.YELLOW}!{self.RESET}", target, detail, self.YELLOW)

    def err(self, target: str, detail: str) -> None:
        self._line(f"{self.RED}✗{self.RESET}", target, detail, self.RED)

    def info(self, detail: str) -> None:
        print(f"  {self._stamp()} {self.GREY}·{self.RESET} {self.WHITE}{detail}{self.RESET}")

    def rule(self) -> None:
        print(f"  {self.GREY}{self.RULE}{self.RESET}")

    def clear(self) -> None:
        print("\x1b[2J\x1b[3J\x1b[H", end="")

    def banner(self) -> None:
        self.clear()
        print()
        print(f"  {self.LIME}╔══════════════════════════════════════════════════════════════════════╗{self.RESET}")
        print(f"  {self.LIME}║{self.RESET} {self.WHITE}Discord Spoofer     {self.LIME}║{self.RESET}")
        print(f"  {self.LIME}╠══════════════════════════════════════════════════════════════════════╣{self.RESET}")
        print(f"  {self.LIME}║{self.RESET} {self.GREY}Developer:{self.RESET} {self.WHITE}Rain{self.RESET}                                                        {self.LIME}║{self.RESET}")
        print(f"  {self.LIME}║{self.RESET} {self.PURPLE}Discord: {self.RESET} {self.WHITE}{self.RESET}                                    {self.LIME}║{self.RESET}")
        print(f"  {self.LIME}╚══════════════════════════════════════════════════════════════════════╝{self.RESET}")


@dataclass
class State:

    token: str = ""
    cookie: str = ""
    fingerprint: str = ""
    analytics_token: str = ""
    fetched_at: int = 0

    @classmethod
    def load(cls) -> "State":
       
        for path in (STATE_FILE_PRIMARY, STATE_FILE_V2):
            if path.exists():
                try:
                    raw = path.read_text(encoding="utf-8").strip()
                    if raw:
                        data = json.loads(raw)
                        return cls(
                            token=data.get("token", ""),
                            cookie=data.get("cookie", ""),
                            fingerprint=data.get("fingerprint", ""),
                            analytics_token=data.get("analytics_token", ""),
                            fetched_at=data.get("fetched_at", 0)
                        )
                except Exception:
                    continue
        return cls()

    def save(self) -> None:
        data_str = json.dumps(asdict(self), indent=2)
       
        for path in (STATE_FILE_PRIMARY, STATE_FILE_V2):
            try:
                path.write_text(data_str, encoding="utf-8")
            except Exception:
                pass

    @property
    def is_stale(self) -> bool:
        return not self.analytics_token or (time.time() - self.fetched_at) > AUTH_MAX_AGE

    @property
    def has_cookie(self) -> bool:
        return bool(self.cookie.strip()) and len(self.cookie.strip()) > 20

    @property
    def has_token(self) -> bool:
        return bool(self.token.strip()) and len(self.token.strip()) > 20



_CACHED_BUILD_NUMBER: int | None = None

def fetch_latest_build_number() -> int:
  
    global _CACHED_BUILD_NUMBER
    if _CACHED_BUILD_NUMBER is not None:
        return _CACHED_BUILD_NUMBER

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
    }
    try:
        req = urllib.request.Request("https://discord.com/app", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8")
        scripts = re.findall(r'src="(/assets/[^"]+\.js)"', html)
        for s in reversed(scripts[-15:]):
            url = "https://discord.com" + s
            try:
                js_req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(js_req, timeout=8) as js_resp:
                    content = js_resp.read().decode("utf-8")
                m = (re.search(r'buildNumber:\s*["\'](\d+)["\']', content) or
                     re.search(r'build_number["\']?\s*:\s*["\']?(\d+)["\']?', content))
                if m:
                    _CACHED_BUILD_NUMBER = int(m.group(1))
                    return _CACHED_BUILD_NUMBER
            except Exception:
                continue
    except Exception:
        pass

    _CACHED_BUILD_NUMBER = FALLBACK_BUILD_NUMBER
    return _CACHED_BUILD_NUMBER


def build_super_props(launch_signature: str, heartbeat_session: str) -> str:
   
    build_num = fetch_latest_build_number()
    props = {
        "os": "Windows",
        "browser": "Discord Client",
        "release_channel": "stable",
        "client_version": CLIENT_VERSION,
        "os_version": OS_VERSION,
        "os_arch": "x64",
        "app_arch": "x64",
        "system_locale": "zh-TW",
        "has_client_mods": False,
        "client_launch_id": str(uuid.uuid4()),
        "browser_user_agent": USER_AGENT,
        "browser_version": "42.11.15",
        "os_sdk_version": "26100",
        "client_build_number": build_num,
        "native_build_number": NATIVE_BUILD_NUMBER,
        "client_event_source": None,
        "launch_signature": launch_signature,
        "client_heartbeat_session_id": heartbeat_session,
        "client_app_state": "focused",
    }
    raw = json.dumps(props, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def _read_analytics_token(auth_token: str) -> str:
    req = urllib.request.Request(ME_URL, headers={"authorization": auth_token, "user-agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Token verification failed ({exc.code}), please check if token is valid") from exc
    except Exception as exc:
        raise RuntimeError(f"Could not connect to Discord: {exc}") from exc
    token = data.get("analytics_token")
    if not token:
        raise RuntimeError("Unexpected error: Failed to retrieve analytics token.")
    return token


def ensure_token(state: State) -> None:
    if not state.is_stale:
        return
    state.analytics_token = _read_analytics_token(state.token)
    state.fetched_at = int(time.time())
    state.save()


@dataclass(frozen=True)
class Session:
    heartbeat_session: str
    launch_signature: str
    super_props: str

    @classmethod
    def new(cls) -> "Session":
        hb = str(uuid.uuid4())
        sig = str(uuid.uuid4())
        return cls(hb, sig, build_super_props(sig, hb))


@dataclass(frozen=True)
class Game:
    id: str
    name: str
    exe: str


def _win_exe(game: dict) -> str:
    for entry in game.get("executables", []):
        if entry.get("os") == "win32" and entry.get("name"):
            return str(entry["name"])
    return "game.exe"


def _download_games() -> str:
    req = urllib.request.Request(GAMES_CDN_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        content = resp.read().decode("utf-8")
    GAMES_FILE.write_text(content, encoding="utf-8")
    return content


def load_games() -> list[Game]:
    data = None
  
    for path in (GAMES_FILE, GAMES_FILE_ALT):
        if path.exists():
            try:
                raw = path.read_text(encoding="utf-8").strip()
                if raw:
                    data = json.loads(raw)
                    break
            except Exception:
                data = None

    if data is None:
        try:
            raw = _download_games()
            data = json.loads(raw)
        except Exception:
            return []

    games: list[Game] = []
    seen: set[str] = set()
    for entry in data:
        gid = str(entry.get("id", "")).strip()
        if not gid.isdigit() or gid in seen:
            continue
        if not any(e.get("os") == "win32" and e.get("name") for e in entry.get("executables", [])):
            continue
        seen.add(gid)
        games.append(Game(gid, str(entry.get("name", "Unknown")), _win_exe(entry)))
    return games


class ScienceClient:
    def __init__(self, state: State, session: Session) -> None:
        self.state = state
        self.session = session
        self._seq = 0

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def build_launch(self, game: Game) -> dict:
        now = int(time.time() * 1000)
        props = {
            "client_track_timestamp": now,
            "client_heartbeat_session_id": self.session.heartbeat_session,
            "event_sequence_number": self._next_seq(),
            "game": game.name,
            "game_id": game.id,
            "verified": True,
            "elevated": False,
            "is_launcher": False,
            "game_platform": "desktop",
            "detection_method": "verified_game",
            "is_overlay_enabled": False,
            "is_overlay_game_enabled": True,
            "is_overlay_game_source": "OOP_DEFAULT_DATABASE",
            "fullscreen_type": "UNKNOWN",
            "hardware_display_count": 1,
            "overlay_method": "Disabled",
            "activity_status_enabled": True,
            "activity_status_shared_guilds": [],
            "current_user_status": "online",
            "game_detection_enabled": True,
            "executable_path": game.exe,
            "voice_channel_id": None,
            "voice_channel_type": None,
            "voice_channel_bitrate": None,
            "voice_channel_guild_id": None,
            "hidden_by_distributor": False,
            "game_metadata": None,
            "executable_fingerprint": self.state.fingerprint,
            "client_performance_cpu": None,
            "client_performance_memory": None,
            "cpu_core_count": None,
            "accessibility_features": 0,
            "rendered_locale": "zh-TW",
            "launch_signature": self.session.launch_signature,
            "client_rtc_state": None,
            "client_app_state": "focused",
            "client_send_timestamp": now,
        }
        if not self.state.fingerprint:
            del props["executable_fingerprint"]
        return {"type": "launch_game", "properties": props}

    def build_heartbeat(self, game: Game, duration_ms: int, session_id: str,
                        initial: bool, final: bool, ts: int | None = None) -> dict:
        ts = int(time.time() * 1000) if ts is None else ts
        return {
            "type": "running_game_heartbeat",
            "properties": {
                "client_track_timestamp": ts,
                "client_heartbeat_session_id": self.session.heartbeat_session,
                "event_sequence_number": self._next_seq(),
                "game_id": game.id,
                "game_name": game.name,
                "game_metadata": None,
                "game_executable": game.exe,
                "game_detection_enabled": True,
                "initial_heartbeat": initial,
                "final_heartbeat": final,
                "game_session_id": session_id,
                "duration_tracked_ms": max(0, duration_ms),
                "rtc_connection_id": None,
                "media_session_id": None,
                "launch_signature": self.session.launch_signature,
                "client_app_state": "focused",
                "client_send_timestamp": ts,
            },
        }

    def build_session(self, game: Game, duration_ms: int) -> list[dict]:
        sid = str(uuid.uuid4())
        now = int(time.time() * 1000)
        start = max(0, now - duration_ms)
        return [
            self.build_heartbeat(game, 0, sid, initial=True, final=False, ts=start),
            self.build_launch(game),
            self.build_heartbeat(game, duration_ms, sid, initial=False, final=True, ts=now),
        ]

    def post(self, events: Sequence[dict]) -> int:
        payload = {"token": self.state.analytics_token, "events": list(events)}
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "accept": "*/*",
            "accept-language": "zh-TW,zh;q=0.9",
            "authorization": self.state.token,
            "content-type": "application/json",
            "cookie": self.state.cookie,
            "origin": "https://discord.com",
            "referer": "https://discord.com/channels/@me",
            "user-agent": USER_AGENT,
            "x-debug-options": "bugReporterEnabled",
            "x-discord-locale": "zh-TW",
            "x-discord-timezone": "Asia/Taipei",
            "x-super-properties": self.session.super_props,
        }
        if DEBUG:
            print("\n" + "=" * 72)
            print(f"POST {SCIENCE_URL} ({len(payload['events'])} events)")
            print("=" * 72)
        request = urllib.request.Request(SCIENCE_URL, data=body, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return response.status
        except urllib.error.HTTPError as exc:
            return exc.code
        except Exception:
            return -1


def _chunked(items: Sequence[Game], size: int) -> Iterator[Sequence[Game]]:
    for start in range(0, len(items), size):
        yield items[start:start + size]


class SpooferRunner:
    def __init__(self, client: ScienceClient, console: Console) -> None:
        self.client = client
        self.console = console

    def run(self, games: Sequence[Game], build_events) -> int:
        total = len(games)
        sent_ok = 0
        for request_no, chunk in enumerate(_chunked(games, BATCH_SIZE), start=1):
            events = []
            for game in chunk:
                events.extend(build_events(game))
            status = self.client.post(events)
            if status == 204:
                sent_ok += len(chunk)
                self.console.sent(f"batch {request_no}", f"Sent {sent_ok}/{total} games")
            elif status in (401, 403):
                self.console.err(f"batch {request_no}",
                                 f"[{status}] Auth error. Do not change password while running.")
                return sent_ok
            elif status == -1:
                self.console.warn(f"batch {request_no}", "Request failed, skipped.")
            else:
                self.console.warn(f"batch {request_no}", f"[{status}] Unexpected Error")

            time.sleep(BATCH_DELAY + random.uniform(0.5, 1.5))
        return sent_ok


class App:
    def __init__(self) -> None:
        self.console = Console()
        self.state = State.load()
        self.session: Session | None = None
        self.client: ScienceClient | None = None
        self.games: list[Game] = []

    def start(self) -> None:
        self.console.banner()

        if not self.state.has_token:
            self._prompt_token()
        if not self.state.has_token:
            self.console.err("Token", "Must provide token to continue")
            return

        self.games = load_games()[:1000]
        if not self.games:
            self.console.err("game list", f"Could not find games file: {GAMES_FILE}")
            return
        self.console.info(f"Loaded {self.console.LIME}{len(self.games)}{self.console.WHITE} games")

        if not self.state.fingerprint:
            self.console.warn("Fingerprint", "Fingerprint not set yet")

        try:
            ensure_token(self.state)
        except Exception as exc:
            self.console.err("Token error", str(exc))
            return
        self._new_session()

        self.menu()

    def _new_session(self) -> None:
        self.session = Session.new()
        self.client = ScienceClient(self.state, self.session)

    def _prompt_token(self) -> None:
        self.console.info("Please enter your Discord token")
        entered = input(f"  {self.console.GREY}Token (paste here):{self.console.RESET} ").strip()
        if entered:
            self.state.token = entered
            self.state.save()
            self.console.ok("Token", "Saved successfully")

    def _refresh(self, prompt_cookie: bool) -> None:
        if prompt_cookie:
            self.console.info("Enter cookie")
            entered = input(f"  {self.console.GREY}Cookie (paste here, press Enter to keep current):{self.console.RESET} ").strip()
            if entered and len(entered) > 20:
                self.state.cookie = entered
                self.state.save()
                self.console.ok("Cookie", "Updated")
            elif entered:
                self.console.warn("Cookie", "Too short, skipped updating")
            else:
                self.console.info("Cookie unchanged")

        self.console.info("Fetching analytics token...")
        try:
            self.state.fetched_at = 0
            ensure_token(self.state)
        except Exception as exc:
            self.console.err("Verification", str(exc))
            return
        self._new_session()
        self.console.ok("Auth", "Token verified successfully")

    def _require_ready(self) -> bool:
        if not self.state.has_cookie:
            self.console.err("Cookie", "Please set your cookie first")
            return False
        if self.state.is_stale:
            try:
                ensure_token(self.state)
            except Exception as exc:
                self.console.err("Verification", str(exc))
                return False
            self._new_session()
        return bool(self.state.analytics_token)

    def module_playtime(self) -> None:
        if not self._require_ready():
            return
        self.console.info("Select hours (recommended: 2-5)")
        raw = input(f"  {self.console.GREY}Enter hours (e.g. 5):{self.console.RESET} ").strip()
        try:
            hours = float(raw)
            if hours <= 0 or hours > 1000:
                self.console.err("Hours", "Must be greater than 0 and less than 1000")
                return
        except ValueError:
            self.console.err("Hours", "Please enter a valid number")
            return
        duration_ms = int(hours * 3600 * 1000)
        print()
        self.console.info(
            f"Sending to {self.console.LIME}{len(self.games)}{self.console.WHITE} games "
            f"each adding {self.console.LIME}{hours:g} hours{self.console.WHITE} "
            f"{self.console.GREY}·{self.console.WHITE} total: {len(self.games) * hours:,.0f} hours"
        )
        self.console.rule()
        ok = SpooferRunner(self.client, self.console).run(
            self.games,
            lambda g: self.client.build_session(
                g,
                max(1000, duration_ms + random.randint(int(-duration_ms * 0.05), int(duration_ms * 0.05)))
            ),
        )
        print()
        self.console.ok("Finished", f"Completed {ok}/{len(self.games)} games · Total: {ok * hours:,.0f} hours")

    def module_played_count(self) -> None:
        if not self._require_ready():
            return
        print()
        self.console.info(
            f"Marking {self.console.LIME}{len(self.games)}{self.console.WHITE} games as 'played' "
            f"{self.console.GREY}·{self.console.WHITE} Duration set to 1 minute per game for natural behavior"
        )
        self.console.rule()
        ok = SpooferRunner(self.client, self.console).run(
            self.games,
            lambda g: self.client.build_session(g, 60000),
        )
        print()
        self.console.ok("Finished", f"Successfully recorded {ok}/{len(self.games)} games as played")

    def module_hypesquad(self) -> None:
        C = self.console
        C.rule()
        print(f"  {C.LIME}1{C.RESET} {C.WHITE}House of Bravery (Purple Badge){C.RESET}")
        print(f"  {C.LIME}2{C.RESET} {C.WHITE}House of Brilliance (Orange Badge){C.RESET}")
        print(f"  {C.LIME}3{C.RESET} {C.WHITE}House of Balance (Green Badge){C.RESET}")
        print(f"  {C.LIME}4{C.RESET} {C.WHITE}Leave HypeSquad (Remove Badge){C.RESET}")
        print(f"  {C.LIME}5{C.RESET} {C.WHITE}Back to Main Menu{C.RESET}")
        C.rule()

        choice = ""
        while choice not in ("1", "2", "3", "4", "5"):
            choice = input(f"  {C.LIME}›{C.RESET} ").strip()

        if choice == "5":
            return

        headers = {
            "Authorization": self.state.token,
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        }

        try:
            del_req = urllib.request.Request(HYPESQUAD_URL, method="DELETE", headers=headers)
            with urllib.request.urlopen(del_req, timeout=10) as resp:
                pass
        except urllib.error.HTTPError as exc:
            if exc.code not in (204, 404):
                C.warn("HypeSquad", f"Server response while clearing previous house: {exc.code}")
        except Exception as exc:
            C.warn("HypeSquad", f"Connection error while clearing previous house: {exc}")

        if choice == "4":
            C.ok("HypeSquad", "Successfully left HypeSquad (Badge removed).")
            return

        house_names = {"1": "Bravery", "2": "Brilliance", "3": "Balance"}
        payload = json.dumps({"house_id": int(choice)}).encode("utf-8")
        post_req = urllib.request.Request(HYPESQUAD_URL, data=payload, method="POST", headers=headers)

        try:
            with urllib.request.urlopen(post_req, timeout=10) as resp:
                if resp.status == 204:
                    C.ok("HypeSquad", f"Successfully joined {house_names[choice]} House!")
                else:
                    C.warn("HypeSquad", f"Response status code: {resp.status}")
        except urllib.error.HTTPError as exc:
            C.err("HypeSquad", f"Failed to join (Code {exc.code}), please verify your Token.")
        except Exception as exc:
            C.err("HypeSquad", f"Request failed: {exc}")

    def menu(self) -> None:
        C = self.console
        while True:
            self.state = State.load()
            cookie_state = f"{C.LIME}Set{C.RESET}" if self.state.has_cookie else f"{C.RED}Not Set{C.RESET}"
            C.rule()
            print(f"  {C.LIME}1{C.RESET} {C.WHITE}Spoof Playtime (Boost total playtime hours){C.RESET}")
            print(f"  {C.LIME}2{C.RESET} {C.WHITE}Spoof Games Played (For played games badge){C.RESET}")
            print(f"  {C.LIME}3{C.RESET} {C.WHITE}Set / Switch HypeSquad Badge{C.RESET}")
            print(f"  {C.LIME}4{C.RESET} {C.WHITE}Update Credentials (Token / Cookie){C.RESET} {C.GREY}· Status: {cookie_state}{C.RESET}")
            print(f"  {C.LIME}5{C.RESET} {C.WHITE}Exit{C.RESET}")
            C.rule()

            choice = ""
            while choice not in ("1", "2", "3", "4", "5"):
                choice = input(f"  {C.LIME}›{C.RESET} ").strip()

            if choice == "1":
                self.module_playtime()
            elif choice == "2":
                self.module_played_count()
            elif choice == "3":
                self.module_hypesquad()
            elif choice == "4":
                self._refresh(prompt_cookie=True)
            elif choice == "5":
                break


def main() -> None:
    try:
        App().start()
    except KeyboardInterrupt:
        print()
        Console().warn("Exit", "Operation cancelled by user.")


if __name__ == "__main__":
    main()