"""CLI entry point for the BAET dashboard server."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import uvicorn

from baet.core.events import EventStore
from baet.core.health import HealthMonitor
from baet.core.certify import Certifier
from baet.core.snapshot import SnapshotManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Start the BAET dashboard server."""
    import argparse

    parser = argparse.ArgumentParser(description="BAET Dashboard Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8080, help="Bind port")
    parser.add_argument("--event-dir", default="data/results", help="Event journal directory")
    parser.add_argument("--snapshot-dir", default="data/results/snapshots", help="Snapshot directory")
    parser.add_argument("--cert-dir", default="data/results/cert", help="Certification directory")
    parser.add_argument("--ui-dir", default=None, help="React build output directory")
    args = parser.parse_args()

    event_dir = Path(args.event_dir)
    snapshot_dir = Path(args.snapshot_dir)
    cert_dir = Path(args.cert_dir)
    ui_dir = Path(args.ui_dir) if args.ui_dir else None

    event_dir.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    cert_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Event journal: {event_dir}")
    logger.info(f"Snapshots: {snapshot_dir}")
    logger.info(f"Certification: {cert_dir}")

    # Initialize components
    event_store = EventStore(event_dir)
    health_monitor = HealthMonitor()
    snapshot_manager = SnapshotManager(snapshot_dir)
    certifier = Certifier(event_store, snapshot_manager, cert_dir=cert_dir)

    # Create FastAPI app
    from baet.dashboard.api.server import create_app

    app = create_app(
        event_store=event_store,
        health_monitor=health_monitor,
        certifier=certifier,
        snapshot_manager=snapshot_manager,
        ui_dir=ui_dir,
    )

    logger.info(f"Starting dashboard server on {args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
