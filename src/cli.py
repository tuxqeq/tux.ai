"""
cli.py — Interactive CLI for tux.ai PII detection and tokenization.
"""

import os
import subprocess
import sys
import time
from getpass import getpass
from pathlib import Path

import questionary
from questionary import Style
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

sys.path.insert(0, os.path.dirname(__file__))
import redis_client as rc

INPUT_DIR  = Path(__file__).parent.parent / "input"
OUTPUT_DIR = Path(__file__).parent.parent / "output"
DEFAULT_MODEL_PATH = "models/pii_model_advanced"
DEFAULT_AES_KEY    = "16ByteSecureKey!"

console = Console()

STYLE = Style([
    ("qmark",        "fg:#00d7ff bold"),
    ("question",     "bold"),
    ("answer",       "fg:#00d7ff bold"),
    ("pointer",      "fg:#00d7ff bold"),
    ("highlighted",  "fg:#00d7ff bold"),
    ("selected",     "fg:#00d7ff"),
    ("separator",    "fg:#444444"),
    ("instruction",  "fg:#888888"),
])


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

def print_banner() -> None:
    banner = Text()
    banner.append("tux", style="bold cyan")
    banner.append(".ai", style="bold white")
    banner.append("  —  PII Detection & Tokenization", style="dim white")
    console.print(Panel(banner, border_style="cyan", padding=(0, 2)))
    console.print()


def print_section(title: str) -> None:
    console.print(f"\n[bold cyan]❯[/bold cyan] [bold]{title}[/bold]\n")


def print_success(msg: str) -> None:
    console.print(f"[bold green]✓[/bold green] {msg}")


def print_error(msg: str) -> None:
    console.print(f"[bold red]✗[/bold red] {msg}")


def print_info(msg: str) -> None:
    console.print(f"[dim]→[/dim] {msg}")


# ---------------------------------------------------------------------------
# File picker
# ---------------------------------------------------------------------------

def pick_input_file() -> Path | None:
    if not INPUT_DIR.exists():
        print_error(f"input/ directory not found at {INPUT_DIR}")
        return None

    files = sorted(f for f in INPUT_DIR.iterdir() if f.is_file())
    if not files:
        print_error("No files found in input/")
        return None

    choices = [f.name for f in files] + ["← Back"]
    choice = questionary.select(
        "Select a file from input/:",
        choices=choices,
        style=STYLE,
    ).ask()

    if choice is None or choice == "← Back":
        return None

    return INPUT_DIR / choice


# ---------------------------------------------------------------------------
# AI mode + model picker
# ---------------------------------------------------------------------------

MODELS_DIR = Path(__file__).parent.parent / "models"


def pick_model() -> str | None:
    """List models/ subdirectories and let the user pick one."""
    if not MODELS_DIR.exists():
        print_error("models/ directory not found.")
        return None

    models = sorted(d.name for d in MODELS_DIR.iterdir() if d.is_dir())
    if not models:
        print_error("No models found in models/")
        return None

    choice = questionary.select(
        "Select AI model:",
        choices=models + ["← Back"],
        style=STYLE,
    ).ask()

    if choice is None or choice == "← Back":
        return None

    return str(MODELS_DIR / choice)


def ask_ai_mode() -> tuple[bool, str]:
    """Returns (use_ai, model_path). model_path is DEFAULT_MODEL_PATH if AI disabled."""
    use_ai = questionary.confirm(
        "Use AI model for detection? (requires trained model)",
        default=False,
        style=STYLE,
    ).ask()

    if not use_ai:
        return False, DEFAULT_MODEL_PATH

    model_path = pick_model()
    if model_path is None:
        return False, DEFAULT_MODEL_PATH

    return True, model_path


# ---------------------------------------------------------------------------
# Redis helpers
# ---------------------------------------------------------------------------

def is_redis_running(url: str) -> bool:
    return rc.ping(url)


def ensure_redis(url: str) -> bool:
    """Return True if Redis is ready, prompting to start it if not."""
    if is_redis_running(url):
        return True

    print_error(f"Redis is not running at {url}")
    start = questionary.confirm(
        "Would you like to start Redis now?",
        default=True,
        style=STYLE,
    ).ask()

    if not start:
        return False

    with console.status("[cyan]Starting Redis...[/cyan]", spinner="dots"):
        try:
            subprocess.Popen(
                ["redis-server", "--daemonize", "yes"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            for _ in range(10):
                time.sleep(0.5)
                if is_redis_running(url):
                    print_success("Redis started successfully.")
                    return True
        except FileNotFoundError:
            pass

    print_error("Could not start Redis. Install it with: brew install redis  or  docker run -d -p 6379:6379 redis")
    return False


# ---------------------------------------------------------------------------
# Option 1: Detect PII
# ---------------------------------------------------------------------------

def run_detect() -> None:
    print_section("Detect PII")

    source = questionary.select(
        "Choose input source:",
        choices=["Enter text manually", "Choose file from input/", "← Back"],
        style=STYLE,
    ).ask()

    if source is None or source == "← Back":
        return

    if source == "Enter text manually":
        text = questionary.text("Enter text:", style=STYLE).ask()
        if not text:
            return
    else:
        path = pick_input_file()
        if path is None:
            return
        text = path.read_text(encoding="utf-8", errors="replace")
        print_info(f"Loaded {path.name} ({len(text):,} chars)")

    use_ai, model_path = ask_ai_mode()

    console.print()
    with console.status("[cyan]Loading detector...[/cyan]", spinner="dots"):
        from hybrid_detect import HybridDetector
        try:
            detector = HybridDetector(model_path, use_ai=use_ai)
        except FileNotFoundError:
            print_error("AI model not found. Run with AI disabled or train the model first.")
            return

    with console.status("[cyan]Scanning for PII...[/cyan]", spinner="dots"):
        results = detector.detect(text)

    if not results:
        print_success("No PII detected.")
        return

    table = Table(
        box=box.ROUNDED,
        border_style="cyan",
        header_style="bold cyan",
        show_lines=True,
    )
    table.add_column("Label",  style="bold yellow", no_wrap=True)
    table.add_column("Value",  style="white")
    table.add_column("Source", style="dim")
    table.add_column("Score",  style="green", justify="right")

    for r in results:
        table.add_row(
            r["label"],
            r["text"],
            r["source"],
            f"{r['score']:.2f}",
        )

    console.print()
    console.print(Panel(
        table,
        title=f"[bold cyan]{len(results)} PII entities found[/bold cyan]",
        border_style="cyan",
        padding=(0, 1),
    ))


# ---------------------------------------------------------------------------
# Option 2: Tokenize file
# ---------------------------------------------------------------------------

def run_tokenize() -> None:
    print_section("Tokenize File")

    path = pick_input_file()
    if path is None:
        return

    use_default_key = questionary.confirm(
        f"Use default AES key? ({DEFAULT_AES_KEY})",
        default=True,
        style=STYLE,
    ).ask()

    if use_default_key:
        aes_key = DEFAULT_AES_KEY.encode("utf-8")
    else:
        key = getpass("AES key (16, 24, or 32 chars): ")
        aes_key = key.encode("utf-8")
        if len(aes_key) not in (16, 24, 32):
            print_error(f"Key must be 16, 24, or 32 bytes — got {len(aes_key)}")
            return

    redis_url = questionary.text(
        "Redis URL:",
        default=rc.DEFAULT_REDIS_URL,
        style=STYLE,
    ).ask()
    if not redis_url:
        return

    if not ensure_redis(redis_url):
        return

    use_ai, model_path = ask_ai_mode()

    OUTPUT_DIR.mkdir(exist_ok=True)
    stem = path.stem
    ext  = path.suffix
    output_path    = OUTPUT_DIR / f"{stem}_tokenized{ext}"
    token_map_path = OUTPUT_DIR / f"{stem}_token_map.json"

    console.print()
    with console.status("[cyan]Tokenizing...[/cyan]", spinner="dots"):
        from tokenize_file import process_file
        try:
            result = process_file(
                input_path=str(path),
                output_path=str(output_path),
                token_map_path=str(token_map_path),
                aes_key=aes_key,
                model_path=model_path,
                use_ai=use_ai,
                redis_url=redis_url,
            )
        except FileNotFoundError as e:
            print_error(str(e))
            return
        except Exception as e:
            print_error(f"Tokenization failed: {e}")
            return

    summary = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    summary.add_column("Key",   style="dim")
    summary.add_column("Value", style="white")
    summary.add_row("Input",          str(path))
    summary.add_row("Tokenized file", str(output_path))
    summary.add_row("Token map",      f"Redis @ {redis_url}")
    summary.add_row("Session ID",     result["session_id"])
    summary.add_row("Key ID",         result["key_id"])

    console.print(Panel(
        summary,
        title="[bold green]✓ Done[/bold green]",
        border_style="green",
        padding=(0, 1),
    ))


# ---------------------------------------------------------------------------
# Option 3: Decrypt file
# ---------------------------------------------------------------------------

def pick_output_file() -> Path | None:
    if not OUTPUT_DIR.exists():
        print_error(f"output/ directory not found at {OUTPUT_DIR}")
        return None

    files = sorted(f for f in OUTPUT_DIR.iterdir() if f.is_file() and "_tokenized" in f.name)
    if not files:
        print_error("No tokenized files found in output/")
        return None

    choices = [f.name for f in files] + ["← Back"]
    choice = questionary.select(
        "Select a tokenized file from output/:",
        choices=choices,
        style=STYLE,
    ).ask()

    if choice is None or choice == "← Back":
        return None

    return OUTPUT_DIR / choice


def run_decrypt() -> None:
    print_section("Decrypt File")

    path = pick_output_file()
    if path is None:
        return

    redis_url = questionary.text(
        "Redis URL:",
        default=rc.DEFAULT_REDIS_URL,
        style=STYLE,
    ).ask()
    if not redis_url:
        return

    if not ensure_redis(redis_url):
        return

    # Try to auto-resolve session ID from filemap
    original_filename = path.name.replace("_tokenized", "")
    with console.status("[cyan]Looking up session...[/cyan]", spinner="dots"):
        session_id = rc.get_session_id(original_filename, url=redis_url)

    if session_id:
        meta = rc.get_session_meta(session_id, url=redis_url)
        print_success(f"Session found: {session_id}")
        if meta:
            print_info(f"Tokens: {meta.get('token_count', '?')}  |  Key ID: {meta.get('key_id', '?')}")
    else:
        print_error(f"No session found in Redis for '{original_filename}'")
        session_id = questionary.text(
            "Enter session ID manually:",
            style=STYLE,
        ).ask()
        if not session_id or not session_id.strip():
            return
        session_id = session_id.strip()

    use_default_key = questionary.confirm(
        f"Use default AES key? ({DEFAULT_AES_KEY})",
        default=True,
        style=STYLE,
    ).ask()

    if use_default_key:
        aes_key = DEFAULT_AES_KEY.encode("utf-8")
    else:
        key = getpass("AES key (16, 24, or 32 chars): ")
        aes_key = key.encode("utf-8")
        if len(aes_key) not in (16, 24, 32):
            print_error(f"Key must be 16, 24, or 32 bytes — got {len(aes_key)}")
            return

    stem = path.stem
    ext  = path.suffix
    output_path = OUTPUT_DIR / f"{stem}_decrypted{ext}"

    console.print()
    with console.status("[cyan]Decrypting...[/cyan]", spinner="dots"):
        from decrypt_file import restore_file
        try:
            result = restore_file(
                input_path=str(path),
                output_path=str(output_path),
                session_id=session_id,
                aes_key=aes_key,
                redis_url=redis_url,
            )
        except Exception as e:
            print_error(f"Decryption failed: {e}")
            return

    if result["restored"] == 0 and result["missing"] == 0:
        print_info("No tokens found in the file.")
        return

    summary = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    summary.add_column("Key",   style="dim")
    summary.add_column("Value", style="white")
    summary.add_row("Input",           str(path))
    summary.add_row("Decrypted file",  str(output_path))
    summary.add_row("Tokens restored", str(result["restored"]))

    if result["missing"]:
        summary.add_row(
            "[yellow]Missing tokens[/yellow]",
            f"{result['missing']} (expired or wrong session)",
        )
    if result["failed"]:
        summary.add_row(
            "[red]Failed tokens[/red]",
            f"{result['failed']} (wrong AES key?)",
        )

    console.print(Panel(
        summary,
        title="[bold green]✓ Done[/bold green]",
        border_style="green",
        padding=(0, 1),
    ))


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main() -> None:
    console.clear()
    print_banner()

    while True:
        action = questionary.select(
            "What would you like to do?",
            choices=[
                "Detect PII",
                "Tokenize file",
                "Decrypt file",
                "Exit",
            ],
            style=STYLE,
        ).ask()

        if action is None or action == "Exit":
            console.print("\n[dim]Bye.[/dim]\n")
            break
        elif action == "Detect PII":
            run_detect()
        elif action == "Tokenize file":
            run_tokenize()
        elif action == "Decrypt file":
            run_decrypt()


if __name__ == "__main__":
    main()
