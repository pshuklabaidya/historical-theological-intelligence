#!/usr/bin/env python3
"""Complete a commentary response from the standard structured task files."""
from __future__ import annotations

import sys
import argparse

import finalize_response
import task_state
import terminal_output


def main() -> int:
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--state-dir", help="directory created by scripts/task_state.py new")
        args = parser.parse_args()
        directory = task_state.resolve(args.state_dir)
        terminal_output.begin(directory)
        inputs = terminal_output.capture(directory, ("checkpoint", "plan"))
        checkpoint_path = task_state.path(directory, "checkpoint")
        plan_path = task_state.path(directory, "plan")
        checkpoint = finalize_response.load_object(checkpoint_path, "evidence checkpoint")
        plan = finalize_response.load_object(plan_path, "response plan")
        _, text = finalize_response.finalize(checkpoint, plan)
        terminal_output.publish(directory, text, checkpoint, inputs)
    except finalize_response.FinalizationError as exc:
        print(f"completion error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"completion error: {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
