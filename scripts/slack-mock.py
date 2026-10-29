#!/usr/bin/env python3
"""Parse a local synthetic Slack-shaped fixture without network access."""
import json
from pathlib import Path


def main() -> None:
    events = json.loads(Path("/opt/kiosk/slack-events.json").read_text())
    print(f"Loaded {len(events)} synthetic offline events")
    for event in events:
        print(f"{event['type']} channel={event['channel']} user={event['user']}")


if __name__ == "__main__":
    main()
