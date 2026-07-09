"""Production entry point with full exception capture and pre-flight checks."""
import os
import sys
import traceback
import asyncio
import faulthandler

# Redirect faulthandler to stdout so it's captured in deployment logs
faulthandler.enable(file=sys.stdout)

# Mirror stderr to stdout so everything ends up in the same capture stream
import io
class _TeeStdout(io.TextIOBase):
    def write(self, s):
        sys.stdout.write(s)
        sys.stdout.flush()
        return len(s)
    def flush(self):
        sys.stdout.flush()

sys.stderr = _TeeStdout()

import logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger("run_server")


def log(msg):
    sys.stdout.write(f"[run_server] {msg}\n")
    sys.stdout.flush()


def preflight_checks():
    """Import backend.app.main and uvicorn before starting the event loop.
    Any import-time errors (missing env vars, bad modules) are caught here
    and logged clearly before the process exits.
    """
    log("=== PRE-FLIGHT CHECKS ===")
    checks = [
        ("backend.app.main import", lambda: __import__("backend.app.main")),
        ("uvicorn import",      lambda: __import__("uvicorn")),
    ]
    for name, fn in checks:
        try:
            fn()
            log(f"  OK: {name}")
        except BaseException as e:
            log(f"  FAIL: {name} -> {type(e).__name__}: {e}")
            traceback.print_exc(file=sys.stdout)
            sys.stdout.flush()
            sys.exit(1)
    log("=== PRE-FLIGHT OK ===")


def handle_asyncio_exception(loop, context):
    exc = context.get("exception")
    msg = context.get("message", "Unknown asyncio error")
    log(f"ASYNCIO EXCEPTION: {msg}")
    if exc is not None:
        log(f"  Type: {type(exc).__name__}: {exc}")
        traceback.print_exception(type(exc), exc, exc.__traceback__, file=sys.stdout)
    sys.stdout.flush()


def main():
    log("Starting production server")
    preflight_checks()

    import uvicorn

    loop = asyncio.new_event_loop()
    loop.set_exception_handler(handle_asyncio_exception)
    asyncio.set_event_loop(loop)

    config = uvicorn.Config(
        "backend.app.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        log_level="info",
        loop="none",
    )
    server = uvicorn.Server(config)
    log("Calling server.serve()")

    try:
        loop.run_until_complete(server.serve())
        log("server.serve() exited normally")
    except BaseException as e:
        log(f"FATAL: server.serve() raised {type(e).__name__}: {e}")
        traceback.print_exc(file=sys.stdout)
        sys.stdout.flush()
        sys.exit(1)
    finally:
        try:
            loop.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
