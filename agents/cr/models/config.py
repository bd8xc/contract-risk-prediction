from dataclasses import dataclass
from pathlib import Path

import torch

CR_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Config:
    """
    Central configuration for the Contract Risk Prediction project.
    """

    #########################################################
    # DATA
    #########################################################

    train_csv: Path = CR_ROOT / "data" / "train_fit.csv"
    val_csv: Path = CR_ROOT / "data" / "val.csv"
    test_csv: Path = CR_ROOT / "data" / "test.csv"

    #########################################################
    # MODEL
    #########################################################

    model_name: str = "nlpaueb/legal-bert-base-uncased"

    num_classes: int = 4

    max_length: int = 512

    stride: int = 128

    dropout: float = 0.1

    #########################################################
    # TRAINING
    #########################################################

    batch_size: int = 4

    epochs: int = 10

    learning_rate: float = 2e-5

    weight_decay: float = 0.01

    warmup_ratio: float = 0.10

    gradient_clip: float = 1.0

    patience: int = 3

    #########################################################
    # CLASS WEIGHTS
    #########################################################

    class_weights = [
        2.46785714,
        0.83454106,
        0.83454106,
        0.83454106,
    ]

    #########################################################
    # CHECKPOINTS
    #########################################################

    checkpoint_dir: Path = CR_ROOT / "checkpoints"

    checkpoint_path: Path = CR_ROOT / "checkpoints" / "best_model.pt"

    resume_training: bool = False

    #########################################################
    # RANDOMNESS
    #########################################################

    seed: int = 42

    #########################################################
    # DEVICE
    #########################################################

    @property
    def device(self):
        return torch.device(
            "cuda"
            if torch.cuda.is_available()
            else "cpu"
        )
