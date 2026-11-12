"""CLI controller for AI agents using Jev Ultrafast's indexed DOM action space without paid policy keys."""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

STATE_DIR = Path(os.environ.get("JEV_STATE_DIR") or (Path.home() / ".cache" / "jev-ultrafast"))
ISOLATED_PORT = int(os.environ.get("JEV_ISOLATED_PORT", "9224"))
ISOLATED_PROFILE = STATE_DIR / "chrome-profile"


def find_chrome_binary() -> str:
    candidates = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        shutil.which("chrome") or "",
        shutil.which("google-chrome") or "",
        shutil.which("chromium") or "",
    ]
    for path in candidates:
        if path and Path(path).is_file():
            return path
    raise RuntimeError("Google Chrome executable not found.")


def port_ready(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=0.5) as resp:
            data = json.loads(resp.read())
            return bool(data.get("webSocketDebuggerUrl"))
    except Exception:
        return False


def ensure_isolated_chrome(headless: bool = False) -> str:
    if not port_ready(ISOLATED_PORT):
        ISOLATED_PROFILE.mkdir(parents=True, exist_ok=True)
        chrome = find_chrome_binary()
        cmd = [
            chrome,
            f"--remote-debugging-port={ISOLATED_PORT}",
            f"--user-data-dir={ISOLATED_PROFILE}",
            "--no-first-run",
            "--no-default-browser-check",
        ]
        if headless:
            cmd.append("--headless=new")
        cmd.append("about:blank")
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=flags,
        )
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if port_ready(ISOLATED_PORT):
                break
            time.sleep(0.15)
        else:
            raise RuntimeError(f"Isolated Chrome failed to listen on port {ISOLATED_PORT}.")
    return f"http://127.0.0.1:{ISOLATED_PORT}"


def configure_mode(user_chrome: bool, headless: bool) -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if user_chrome:
        os.environ["BU_NAME"] = "default"
        os.environ.pop("BU_CDP_URL", None)
        return STATE_DIR / "session_user.json"
    cdp_url = ensure_isolated_chrome(headless=headless)
    os.environ["BU_NAME"] = "ag-isolated"
    os.environ["BU_CDP_URL"] = cdp_url
    return STATE_DIR / "session_isolated.json"


def attach_saved_browser(session_file: Path):
    from browser_harness.admin import ensure_daemon

    from .browser import Browser

    if not session_file.exists():
        raise RuntimeError("No active Jev session. Run `open <url>` first.")
    saved = json.loads(session_file.read_text(encoding="utf-8"))
    ensure_daemon()
    browser = Browser.__new__(Browser)
    browser.target = saved["target"]
    browser.session = saved["session"]
    browser.after_input = None
    return browser, saved["page"]


def save_session(session_file: Path, browser: Any, page: dict[str, Any], screenshot_path: Path | None = None) -> None:
    page_copy = {k: v for k, v in page.items() if k != "screenshot"}
    if screenshot_path and page.get("screenshot"):
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        screenshot_path.write_bytes(base64.b64decode(page["screenshot"]))
    session_file.write_text(
        json.dumps({"target": browser.target, "session": browser.session, "page": page_copy}, ensure_ascii=False),
        encoding="utf-8",
    )


def format_observation(page: dict[str, Any], elapsed_ms: int) -> str:
    from .model import action_space

    elements, _targets, controls = action_space(page["actions"])
    lines = [
        f"URL      : {page.get('url', '')}",
        f"Title    : {page.get('title', '')}",
        f"Latency  : {elapsed_ms} ms | Elements: {len(elements)} | Controls: {', '.join(controls) or 'none'}",
    ]
    visible_text = (page.get("text") or "").strip()
    if visible_text:
        snippet = " ".join(visible_text.split())[:320]
        lines.append(f"Snippet  : {snippet}")
    lines.append("--- INDEXED ELEMENTS ---")
    for el in elements:
        ops = ",".join(el["operations"])
        role = el.get("role", "control")
        label = " ".join(str(el.get("label", "")).split())
        val = el.get("value", "")
        extra = f" = {val!r}" if val != "" else ""
        flags = [f for f in ("checked", "selected", "expanded") if el.get(f) is True]
        flag_str = f" ({','.join(flags)})" if flags else ""
        lines.append(f"[{el['index']}] {role:<10} ({ops}) {label}{extra}{flag_str}")
        for opt in el.get("options", []):
            opt_label = " ".join(str(opt["label"]).split())
            lines.append(f"    [{opt['index']}] option {opt_label} (value={opt['value']!r})")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Jev Ultrafast Agent CLI Runner")
    parser.add_argument(
        "--user-chrome",
        action="store_true",
        help="Attach to user's main running Chrome instead of popup-free isolated Chrome",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Launch isolated Chrome in headless mode when starting fresh",
    )
    parser.add_argument(
        "--screenshot",
        type=str,
        default="",
        help="Optional path to save JPEG screenshot on observation",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_open = sub.add_parser("open", help="Open URL in a Jev Ultrafast session")
    p_open.add_argument("url", type=str)

    sub.add_parser("observe", help="Observe current page and print indexed elements")

    p_click = sub.add_parser("click", help="Click element by index")
    p_click.add_argument("index", type=str)

    p_type = sub.add_parser("type", help="Type text into element by index")
    p_type.add_argument("index", type=str)
    p_type.add_argument("text", type=str)

    p_select = sub.add_parser("select", help="Select dropdown option by target index (e.g. 3:2)")
    p_select.add_argument("target", type=str)

    p_scroll = sub.add_parser("scroll", help="Scroll viewport up or down")
    p_scroll.add_argument("direction", choices=["up", "down"])

    sub.add_parser("wait", help="Wait briefly and re-observe")
    sub.add_parser("close", help="Close active Jev Ultrafast tab")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    session_file = configure_mode(user_chrome=args.user_chrome, headless=args.headless)
    shot_path = Path(args.screenshot) if args.screenshot else None
    want_shot = shot_path is not None

    from .browser import Browser, StalePage
    from .model import action_space

    t0 = time.perf_counter()

    if args.cmd == "close":
        if session_file.exists():
            try:
                browser, _ = attach_saved_browser(session_file)
                browser.close()
            except Exception:
                pass
            session_file.unlink(missing_ok=True)
        print("Session closed.")
        return

    if args.cmd == "open":
        if session_file.exists():
            try:
                old_browser, _ = attach_saved_browser(session_file)
                old_browser.close()
            except Exception:
                pass
            session_file.unlink(missing_ok=True)
        browser = Browser(args.url)
        page = browser.observe(screenshot=want_shot)
        save_session(session_file, browser, page, shot_path)
        elapsed = round((time.perf_counter() - t0) * 1000)
        print(format_observation(page, elapsed))
        return

    browser, page = attach_saved_browser(session_file)

    if args.cmd == "observe":
        page = browser.observe(screenshot=want_shot)
        save_session(session_file, browser, page, shot_path)
        elapsed = round((time.perf_counter() - t0) * 1000)
        print(format_observation(page, elapsed))
        return

    _elements, targets, controls = action_space(page["actions"])

    if args.cmd == "click":
        candidates = targets.get("CLICK", {})
        if args.index not in candidates:
            raise SystemExit(f"Index [{args.index}] is not clickable. Valid: {list(candidates)}")
        action = candidates[args.index]
        text_val = None
    elif args.cmd == "type":
        candidates = targets.get("TYPE_TEXT", {})
        if args.index not in candidates:
            raise SystemExit(f"Index [{args.index}] does not accept TYPE_TEXT. Valid: {list(candidates)}")
        action = candidates[args.index]
        text_val = args.text
    elif args.cmd == "select":
        candidates = targets.get("SELECT", {})
        if args.target not in candidates:
            raise SystemExit(f"Target [{args.target}] is not a valid SELECT option. Valid: {list(candidates)}")
        action = candidates[args.target]
        text_val = None
    elif args.cmd == "scroll":
        key = f"SCROLL_{args.direction.upper()}"
        if key not in controls:
            raise SystemExit(f"{key} not available on current page.")
        action = controls[key]
        text_val = None
    elif args.cmd == "wait":
        action = controls.get("WAIT", {"id": "wait", "kind": "wait", "label": "Wait"})
        text_val = None
    else:
        raise SystemExit("Unsupported command")

    try:
        browser.act(action, page, text=text_val)
    except StalePage as exc:
        page = browser.observe(screenshot=want_shot)
        save_session(session_file, browser, page, shot_path)
        elapsed = round((time.perf_counter() - t0) * 1000)
        print(f"STALE_PAGE: {exc} -- refreshed state without executing action:")
        print(format_observation(page, elapsed))
        sys.exit(2)

    page = browser.observe(screenshot=want_shot)
    save_session(session_file, browser, page, shot_path)
    elapsed = round((time.perf_counter() - t0) * 1000)
    print(f"EXECUTED : {args.cmd.upper()} -> {action['label']}")
    print(format_observation(page, elapsed))
