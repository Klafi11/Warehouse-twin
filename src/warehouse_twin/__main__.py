"""`uv run warehouse-twin`: start the whole app locally, no cloud account or network needed."""

import argparse
import webbrowser
from pathlib import Path

import uvicorn

from warehouse_twin.app import create_app


def main() -> None:
    parser = argparse.ArgumentParser(prog="warehouse-twin", description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--log-dir", type=Path, default=Path("runs"))
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    app = create_app(args.log_dir, seed=args.seed, speed=args.speed)
    if not args.no_browser:
        webbrowser.open(f"http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
