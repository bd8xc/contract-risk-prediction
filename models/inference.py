import os

import torch
import torch.nn.functional as F
from transformers import AutoTokenizer

from models.config import Config
from models.sliding_legalbert import SlidingWindowLegalBERT


class ContractRiskPredictor:
    """
    Inference wrapper for the trained Sliding-Window LegalBERT model.

    Takes raw legal text and returns:
        - predicted risk class
        - model score
        - score for every class

    IMPORTANT:
    The softmax scores are not calibrated probabilities.
    """

    LABEL_NAMES = [
        "Seed",
        "Low",
        "Medium",
        "High",
    ]

    def __init__(
        self,
        checkpoint_path=None,
        device=None,
    ):

        self.cfg = Config()

        ######################################################
        # DEVICE
        ######################################################

        if device is None:
            self.device = self.cfg.device
        else:
            self.device = torch.device(device)

        ######################################################
        # CHECKPOINT
        ######################################################

        if checkpoint_path is None:
            checkpoint_path = self.cfg.checkpoint_path

        self.checkpoint_path = checkpoint_path

        if not os.path.exists(self.checkpoint_path):

            raise FileNotFoundError(
                f"Checkpoint not found: "
                f"{self.checkpoint_path}"
            )

        print(
            f"Using device : {self.device}"
        )

        ######################################################
        # TOKENIZER
        ######################################################

        print(
            "Loading LegalBERT tokenizer..."
        )

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.cfg.model_name
        )

        ######################################################
        # MODEL
        ######################################################

        print(
            "Loading SlidingWindowLegalBERT..."
        )

        self.model = SlidingWindowLegalBERT(
            model_name=self.cfg.model_name,
            num_classes=self.cfg.num_classes,
            dropout=self.cfg.dropout,
        )

        ######################################################
        # LOAD CHECKPOINT
        ######################################################

        checkpoint = torch.load(
            self.checkpoint_path,
            map_location=self.device,
            weights_only=False,
        )

        # Supports our full training checkpoint format
        if (
            isinstance(checkpoint, dict)
            and "model_state_dict" in checkpoint
        ):

            self.model.load_state_dict(
                checkpoint["model_state_dict"]
            )

        else:

            # Also supports raw state_dict checkpoints
            self.model.load_state_dict(
                checkpoint
            )

        self.model.to(
            self.device
        )

        self.model.eval()

        print(
            "Model loaded successfully."
        )

    ##########################################################
    # TOKENIZE INTO SLIDING WINDOWS
    ##########################################################

    def _tokenize(self, text):

        if not isinstance(text, str):

            raise TypeError(
                "Input text must be a string."
            )

        text = text.strip()

        if not text:

            raise ValueError(
                "Input text cannot be empty."
            )

        encoding = self.tokenizer(
            text,
            truncation=True,
            max_length=self.cfg.max_length,
            stride=self.cfg.stride,
            return_overflowing_tokens=True,
            padding="max_length",
            return_tensors="pt",
        )

        input_ids = encoding[
            "input_ids"
        ]

        attention_mask = encoding[
            "attention_mask"
        ]

        return (
            input_ids,
            attention_mask,
        )

    ##########################################################
    # PREDICT
    ##########################################################

    def predict(self, text):

        input_ids, attention_mask = (
            self._tokenize(text)
        )

        ######################################################
        # NUMBER OF WINDOWS
        ######################################################

        num_windows = input_ids.shape[0]

        ######################################################
        # MOVE TO DEVICE
        ######################################################

        input_ids = input_ids.to(
            self.device
        )

        attention_mask = attention_mask.to(
            self.device
        )

        ######################################################
        # WINDOW COUNTS
        #
        # One input document/clause is being predicted.
        # Therefore all generated windows belong to
        # this one sample.
        ######################################################

        window_counts = torch.tensor(
            [num_windows],
            dtype=torch.long,
        )

        ######################################################
        # INFERENCE
        ######################################################

        with torch.no_grad():

            logits = self.model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                window_counts=window_counts,
            )

            probabilities = F.softmax(
                logits,
                dim=1,
            )

        ######################################################
        # EXTRACT SCORES
        ######################################################

        probabilities = (
            probabilities
            .squeeze(0)
            .cpu()
            .numpy()
        )

        predicted_id = int(
            probabilities.argmax()
        )

        predicted_label = (
            self.LABEL_NAMES[
                predicted_id
            ]
        )

        model_score = float(
            probabilities[
                predicted_id
            ]
        )

        class_scores = {

            label:
                float(
                    probabilities[index]
                )

            for index, label
            in enumerate(
                self.LABEL_NAMES
            )
        }

        ######################################################
        # RETURN RESULT
        ######################################################

        return {

            "prediction":
                predicted_label,

            "prediction_id":
                predicted_id,

            "model_score":
                model_score,

            "class_scores":
                class_scores,

            "num_windows":
                int(
                    num_windows
                ),
        }


##############################################################
# OPTIONAL COMMAND-LINE TEST
##############################################################

if __name__ == "__main__":

    predictor = ContractRiskPredictor()

    print(
        "\n"
        + "=" * 70
    )

    print(
        "CONTRACT RISK PREDICTION"
    )

    print(
        "=" * 70
    )

    while True:

        print(
            "\nPaste a legal clause."
        )

        print(
            "Type 'quit' to exit.\n"
        )

        text = input(
            "Clause: "
        ).strip()

        if text.lower() in {
            "quit",
            "exit",
            "q",
        }:

            print(
                "\nExiting."
            )

            break

        if not text:

            print(
                "Please enter some text."
            )

            continue

        try:

            result = predictor.predict(
                text
            )

            print(
                "\n"
                + "-" * 70
            )

            print(
                f"Prediction  : "
                f"{result['prediction']}"
            )

            print(
                f"Model score : "
                f"{result['model_score'] * 100:.2f}%"
            )

            print(
                f"Windows     : "
                f"{result['num_windows']}"
            )

            print(
                "\nClass scores:"
            )

            for (
                label,
                score,
            ) in result[
                "class_scores"
            ].items():

                print(
                    f"{label:<8}: "
                    f"{score * 100:.2f}%"
                )

            print(
                "-" * 70
            )

            print(
                "\nNote: Scores are raw model "
                "softmax outputs and are not "
                "calibrated probabilities."
            )

        except Exception as error:

            print(
                f"\nPrediction failed: "
                f"{error}"
            )