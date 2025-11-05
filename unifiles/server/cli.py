"""
CLI entry point for Unifiles server

Usage:
    unifiles-server --help
    unifiles-server --host 0.0.0.0 --port 8088
"""

import argparse
import sys


def main():
    """Main CLI entry point for starting the Unifiles server"""
    parser = argparse.ArgumentParser(
        description="Unifiles Document Processing Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start server with default settings (0.0.0.0:8088)
  unifiles-server

  # Start server on custom host/port
  unifiles-server --host 127.0.0.1 --port 8000

  # Start with auto-reload (development)
  unifiles-server --reload

  # Start with custom workers
  unifiles-server --workers 4
        """,
    )

    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Bind socket to this host (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8088,
        help="Bind socket to this port (default: 8088)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload (development only)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default: 1)",
    )
    parser.add_argument(
        "--log-level",
        default="info",
        choices=["critical", "error", "warning", "info", "debug", "trace"],
        help="Set the log level (default: info)",
    )

    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError:
        print(
            "Error: uvicorn not installed. Install server dependencies with:\n"
            "  pip install unifiles[server]",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"🚀 Starting Unifiles server on http://{args.host}:{args.port}")
    print(f"📝 Log level: {args.log_level}")
    if args.reload:
        print("🔄 Auto-reload enabled (development mode)")
    if args.workers > 1:
        print(f"👷 Workers: {args.workers}")

    uvicorn.run(
        "unifiles.server.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
