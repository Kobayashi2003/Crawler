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
    API, Cache, CLIContext, Downloader, ExternalLinksDownloader, ExternalLinksExtractor,
    Logger, Migrator, Notifier, Scheduler, Storage, Validator,
)
from src.cli.prompt import CLIPromptSession
from src.common.env import load_dotenv
from src.common.hotreload import dynamic_get


def get_commands() -> dict:
    """Load the command map fresh each call so edits to src/cli/commands.py hot-reload."""
    from src.cli.commands import COMMAND_MAP
    return dynamic_get('COMMAND_MAP', 'src/cli/commands.py', default=COMMAND_MAP)

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
    load_dotenv()  # proxies and PAWCHIVE_* overrides, before anything reads them
    storage = Storage()
    config = storage.load_config()
    logger = Logger(config.logs_dir)
    cache = Cache(config.cache_dir, logger, config, storage)
    api = API(logger, config)
    notifier = Notifier(enabled=config.notify)
    downloader = Downloader(config, logger, storage, cache, api, notifier=notifier)
    scheduler = Scheduler(storage, downloader, logger, config.global_timer,
                          max_workers=config.max_concurrent_artists)
    migrator = Migrator(storage, cache)
    validator = Validator(config.data_dir, cache, storage, config, logger)
    links_extractor = ExternalLinksExtractor(cache, logger)
    links_downloader = ExternalLinksDownloader(logger)
    ctx = CLIContext(storage, cache, api, downloader, scheduler, migrator, validator,
                     links_extractor, links_downloader)
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
