from __future__ import annotations

import json
import sys

from . import route

if __name__ == "__main__":
    board_path, phase, state_path, result_path = sys.argv[1:5]
    with open(state_path, encoding="utf-8") as handle:
        state = json.load(handle)
    outcome = route.run_tidy_phase(board_path, phase, state)
    with open(result_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(outcome, handle, indent=2, sort_keys=True)
        handle.write("\n")
