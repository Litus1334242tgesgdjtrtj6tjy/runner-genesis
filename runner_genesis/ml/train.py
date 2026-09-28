from __future__ import annotations

"""Compatibility entrypoint for Genesis training.

The canonical implementation lives in runner_genesis.training because it enforces
label-availability purging, token-group OOS separation, token-balanced fitting and
chronological calibration. Keeping a second independent trainer here previously created a
future-leakage risk.
"""

import argparse
import json

from ..training import train_genesis_from_dataset


def train(input_path: str, out_path: str, time_col: str = "decision_time"):
    if time_col != "decision_time":
        raise ValueError(
            "Genesis training requires canonical decision_time semantics; "
            "build the executable dataset with runner_genesis.cli build-dataset."
        )
    return train_genesis_from_dataset(
        input_path,
        out_path,
        min_rows=100,
        group_purge_tokens=True,
        token_balance=True,
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    args = ap.parse_args()
    print(json.dumps(train(args.input, args.output), indent=2, default=str))
