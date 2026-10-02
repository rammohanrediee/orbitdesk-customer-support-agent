"""Dry-run-first retention control for reviewed synthetic support tickets."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
import json
import os

from orbitdesk_support_agent.tickets import TicketStore


def run_retention(
    store: TicketStore,
    *,
    days: int,
    apply: bool,
    now: datetime | None = None,
) -> dict:
    if days <= 0:
        raise ValueError("Retention days must be positive.")
    cutoff = (now or datetime.now(UTC)) - timedelta(days=days)
    counts = store.prune_reviewed_before(cutoff, apply=apply)
    return {
        "mode": "apply" if apply else "dry_run",
        "retention_days": days,
        "cutoff_utc": cutoff.isoformat(),
        **counts,
        "policy": "Only reviewed tickets older than the cutoff; pending tickets are kept.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview or apply reviewed-ticket retention.")
    parser.add_argument("--days", type=int, help="Age threshold, overriding ORBITDESK_RETENTION_DAYS")
    parser.add_argument("--apply", action="store_true", help="Delete eligible reviewed tickets (default: preview only)")
    args = parser.parse_args()
    raw_days = args.days if args.days is not None else os.getenv("ORBITDESK_RETENTION_DAYS")
    if raw_days is None:
        parser.error("Set --days or ORBITDESK_RETENTION_DAYS.")
    try:
        days = int(raw_days)
    except ValueError:
        parser.error("Retention days must be an integer.")
    from orbitdesk_support_agent.api import ticket_store

    print(json.dumps(run_retention(ticket_store(), days=days, apply=args.apply), indent=2))


if __name__ == "__main__":
    main()
