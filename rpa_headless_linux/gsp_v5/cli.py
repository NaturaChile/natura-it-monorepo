# ──────────────────────────────────────────────
# CLI Quick-Start Script
# ──────────────────────────────────────────────
"""
Quick CLI to load a CSV and start processing without the API.

Usage:
    python -m cli load data/sample_orders.csv --name "Dia de las Madres 2026"
    python -m cli start 1
    python -m cli status 1
    python -m cli retry 1
    python -m cli retry-order 42
"""
from __future__ import annotations

import sys
import argparse

from shared.logging_config import setup_logging
from shared.database import init_db


def main():
    setup_logging()
    init_db()

    parser = argparse.ArgumentParser(description="GSP Bot v5 CLI")
    sub = parser.add_subparsers(dest="command")

    # Load
    p_load = sub.add_parser("load", help="Load orders from CSV/Excel")
    p_load.add_argument("file", help="Path to CSV or Excel file")
    p_load.add_argument("--name", default="", help="Batch name")
    p_load.add_argument("--desc", default="", help="Batch description")

    # Start
    p_start = sub.add_parser("start", help="Start processing a batch")
    p_start.add_argument("batch_id", type=int)

    # Status
    p_status = sub.add_parser("status", help="Show batch status")
    p_status.add_argument("batch_id", type=int)

    # Retry batch
    p_retry = sub.add_parser("retry", help="Retry all failed orders in a batch")
    p_retry.add_argument("batch_id", type=int)

    # Retry single order
    p_retry_order = sub.add_parser("retry-order", help="Retry a single order")
    p_retry_order.add_argument("order_id", type=int)

    # Pause
    p_pause = sub.add_parser("pause", help="Pause a batch")
    p_pause.add_argument("batch_id", type=int)

    # Cancel
    p_cancel = sub.add_parser("cancel", help="Cancel a batch")
    p_cancel.add_argument("batch_id", type=int)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    from master.orchestrator import Orchestrator
    orch = Orchestrator()

    if args.command == "load":
        from master.loader import load_from_csv
        batch_id = load_from_csv(args.file, batch_name=args.name, description=args.desc)
        print(f"✅ Batch created: ID={batch_id}")
        print(f"   Start with: python -m cli start {batch_id}")

    elif args.command == "start":
        result = orch.start_batch(args.batch_id)
        if result.get("success"):
            print(f"🚀 Batch {args.batch_id} dispatched! Task: {result['task_id']}")
        else:
            print(f"❌ Error: {result.get('error')}")

    elif args.command == "status":
        stats = orch.get_batch_stats(args.batch_id)
        if not stats:
            print("❌ Batch not found")
            return
        print(f"📊 Batch {args.batch_id} Status:")
        print(f"   Total:       {stats['total']}")
        print(f"   Pending:     {stats['pending']}")
        print(f"   Queued:      {stats['queued']}")
        print(f"   In Progress: {stats['in_progress']}")
        print(f"   Completed:   {stats['completed']}")
        print(f"   Failed:      {stats['failed']}")
        print(f"   Retrying:    {stats['retrying']}")
        print(f"   Progress:    {stats['progress_pct']}%")
        if stats.get("eta_seconds"):
            mins = stats["eta_seconds"] / 60
            print(f"   ETA:         ~{mins:.0f} min")

    elif args.command == "retry":
        result = orch.retry_batch_failures(args.batch_id)
        print(f"🔄 Retry dispatched for batch {args.batch_id}: {result}")

    elif args.command == "retry-order":
        result = orch.retry_single_order(args.order_id)
        if result.get("success"):
            print(f"🔄 Order {args.order_id} re-queued: {result['task_id']}")
        else:
            print(f"❌ Error: {result.get('error')}")

    elif args.command == "pause":
        result = orch.pause_batch(args.batch_id)
        print(f"⏸️  Batch {args.batch_id}: {result}")

    elif args.command == "cancel":
        result = orch.cancel_batch(args.batch_id)
        print(f"🛑 Batch {args.batch_id}: {result}")


if __name__ == "__main__":
    main()
