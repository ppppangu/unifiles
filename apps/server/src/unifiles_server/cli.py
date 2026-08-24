from __future__ import annotations

import argparse
import os

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the self-hosted Unifiles API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--log-level", default="info")
    options = parser.parse_args()
    if options.host not in {"127.0.0.1", "localhost", "::1"} and not os.getenv(
        "UNIFILES_BOOTSTRAP_API_KEY"
    ):
        parser.error("UNIFILES_BOOTSTRAP_API_KEY is required when binding beyond localhost")
    uvicorn.run(
        "unifiles_server.app:app",
        host=options.host,
        port=options.port,
        workers=1,
        reload=options.reload,
        log_level=options.log_level,
    )


if __name__ == "__main__":
    main()
