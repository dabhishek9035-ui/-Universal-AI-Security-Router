"""CLI: run red-team rounds, optionally with before/after benchmark.

Usage:
  python scripts/redteam_run.py --rounds 2 --n 40
  python scripts/redteam_run.py --benchmark   # before/after ASR around learning
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.redteam import load_history, run_round  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Red-team the security router")
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--n", type=int, default=40, help="attacks per round")
    parser.add_argument("--benchmark", action="store_true",
                        help="run before/after benchmark with learning enabled")
    parser.add_argument("--no-learn", action="store_true")
    args = parser.parse_args()

    for i in range(args.rounds):
        summary = run_round(n_attacks=args.n, round_name=f"cli-round-{i + 1}",
                            learn=not args.no_learn)
        print(f"\n=== {summary['round_id']} ===")
        print(f"ASR overall: {summary['asr_overall'] * 100:.1f}%  "
              f"({summary['misses']}/{summary['n_attacks']} missed, "
              f"FPs on benign: {summary['false_positives_on_benign']})")
        for cat, asr in sorted(summary["asr_by_category"].items()):
            print(f"  {cat:<16} ASR {asr * 100:5.1f}%")

    if args.benchmark:
        print("\n--- ASR across all recorded rounds (lower is better) ---")
        for r in load_history(50):
            print(f"{r['round_id']:<28} ASR {r['asr_overall'] * 100:5.1f}%")


if __name__ == "__main__":
    main()
