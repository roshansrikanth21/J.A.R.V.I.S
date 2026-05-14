"""
run_hud.py — Launch the JARVIS HUD overlay independently.

Usage:
    python run_hud.py                    # connects to ws://localhost:8000/ws
    python run_hud.py --ws ws://...      # custom WebSocket URL
"""
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description="JARVIS HUD Overlay")
    parser.add_argument(
        "--ws",
        default="ws://localhost:8000/ws",
        help="WebSocket URL of the JARVIS backend (default: ws://localhost:8000/ws)"
    )
    args = parser.parse_args()

    from jarvis.hud.overlay import launch
    sys.exit(launch(ws_url=args.ws))

if __name__ == "__main__":
    main()
