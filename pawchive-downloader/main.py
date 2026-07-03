import inspect
import signal
import sys

# Many creator names are Japanese; the default Windows console codec (cp932)
# would raise UnicodeEncodeError when printing them. Force UTF-8 output.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from src import (
    API, Cache, CLIContext, Downloader, Logger, Scheduler, Storage,
)
from src.plugins import dynamic_get
from src.prompt import CLIPromptSession


def get_commands() -> dict:
    """Load the command map fresh each call so edits to src/cli.py hot-reload."""
    from src.cli import COMMAND_MAP
    return dynamic_get('COMMAND_MAP', 'src/cli.py', default=COMMAND_MAP)

_interrupts = 0


def parse_command(text: str):
    """Split ``command:key=value,key=value`` into (command, params dict)."""
    if ':' not in text:
        return text, {}
    command, _, rest = text.partition(':')
    params = {}
    for part in rest.split(','):
        if '=' in part:
            key, _, value = part.partition('=')
            params[key.strip()] = value.strip()
    return command.strip(), params


def initialize():
    storage = Storage("data")
    config = storage.load_config()
    logger = Logger(config.logs_dir)
    cache = Cache(config.cache_dir, logger, config, storage)
    api = API(logger, config)
    downloader = Downloader(config, logger, storage, cache, api)
    scheduler = Scheduler(storage, downloader, logger, config.global_timer,
                          max_workers=config.max_concurrent_artists)
    ctx = CLIContext(storage, cache, api, downloader, scheduler)
    return ctx, scheduler, logger


def run_cli(ctx: CLIContext):
    session = CLIPromptSession(ctx.storage, get_commands)
    while True:
        try:
            text = session.prompt("> ").strip()
        except EOFError:
            break
        if not text:
            continue

        command, params = parse_command(text)
        handler = get_commands().get(command)
        if not handler:
            print("Unknown command. Type 'help'.")
            continue

        accepted = set(inspect.signature(handler).parameters) - {'ctx'}
        kwargs = {k: v for k, v in params.items() if k in accepted}
        unknown = set(params) - accepted
        if unknown:
            print(f"Ignoring unsupported params: {', '.join(unknown)}")

        try:
            handler(ctx, **kwargs)
            ctx.storage.add_history(command, success=True, artist_id=ctx._last_artist, params=kwargs)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            ctx.storage.add_history(command, success=False, artist_id=ctx._last_artist,
                                    params=kwargs, note=str(e))
            print(f"Error: {e}")
        finally:
            ctx._last_artist = None


def main():
    def on_sigint(signum, frame):
        global _interrupts
        _interrupts += 1
        if _interrupts == 1:
            print("\n\nShutdown requested. Ctrl+C again to force quit.")
            raise KeyboardInterrupt
        import os
        os._exit(1)

    signal.signal(signal.SIGINT, on_sigint)

    ctx, scheduler, logger = initialize()
    scheduler.start()
    logger.app_started(artists=len(ctx.storage.get_artists()))
    print("Pawchive Downloader. Type 'help' for commands, 'exit' to quit.")

    try:
        run_cli(ctx)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        ctx.downloader.stop()
        scheduler.stop()
        logger.app_stopped()
        print("Bye.")


if __name__ == "__main__":
    main()
