"""Create a reproducible, source-document-level validation split."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from sklearn.model_selection import GroupShuffleSplit


DATA = Path(__file__).resolve().parent / "data"
SOURCE = DATA / "train.csv"
TRAIN_OUT = DATA / "train_fit.csv"
VALIDATION_OUT = DATA / "val.csv"
SEED = 42
VALIDATION_FRACTION = 0.2


def main() -> None:
    frame = pd.read_csv(SOURCE)
    required = {"original_file", "text", "label"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Training CSV is missing columns: {sorted(missing)}")
    if frame[list(required)].isna().any().any():
        raise ValueError("Training CSV has missing source, text, or label values")

    groups = frame["original_file"].astype(str)
    labels = set(frame["label"].astype(int))
    splitter = GroupShuffleSplit(
        n_splits=500,
        test_size=VALIDATION_FRACTION,
        random_state=SEED,
    )
    for train_indices, validation_indices in splitter.split(frame, groups=groups):
        train = frame.iloc[train_indices]
        validation = frame.iloc[validation_indices]
        if set(train["label"].astype(int)) == labels and set(validation["label"].astype(int)) == labels:
            break
    else:
        raise RuntimeError("Could not split all risk classes across train and validation")

    TRAIN_OUT.parent.mkdir(parents=True, exist_ok=True)
    train.to_csv(TRAIN_OUT, index=False)
    validation.to_csv(VALIDATION_OUT, index=False)
    overlap = set(train["original_file"]) & set(validation["original_file"])
    if overlap:
        raise RuntimeError("Source-document leakage detected in validation split")
    print(f"Training rows: {len(train)} -> {TRAIN_OUT}")
    print(f"Validation rows: {len(validation)} -> {VALIDATION_OUT}")
    print(f"Training labels: {train['label'].value_counts().sort_index().to_dict()}")
    print(f"Validation labels: {validation['label'].value_counts().sort_index().to_dict()}")


if __name__ == "__main__":
    main()
