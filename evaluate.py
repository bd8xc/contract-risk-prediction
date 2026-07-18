import torch

from torch.utils.data import DataLoader

from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    confusion_matrix,
    classification_report,
)

from models.dataset import ContractRiskDataset
from models.collate import sliding_window_collate
from models.sliding_legalbert import SlidingWindowLegalBERT


##############################################
# CONFIGURATION
##############################################

TEST_CSV = "data/test.csv"

MODEL_NAME = "nlpaueb/legal-bert-base-uncased"

CHECKPOINT = "checkpoints/best_model.pt"

BATCH_SIZE = 4

DEVICE = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)

##############################################
# DATASET
##############################################

test_dataset = ContractRiskDataset(
    csv_path=TEST_CSV,
    model_name=MODEL_NAME,
)

test_loader = DataLoader(
    test_dataset,
    batch_size=BATCH_SIZE,
    shuffle=False,
    collate_fn=sliding_window_collate,
)

##############################################
# MODEL
##############################################

model = SlidingWindowLegalBERT(
    model_name=MODEL_NAME,
    num_classes=4,
)

model.load_state_dict(
    torch.load(
        CHECKPOINT,
        map_location=DEVICE,
    )
)

model.to(DEVICE)

model.eval()

##############################################
# EVALUATION
##############################################

predictions = []

labels = []

with torch.no_grad():

    for batch in test_loader:

        input_ids = batch["input_ids"].to(DEVICE)

        attention_mask = batch["attention_mask"].to(DEVICE)

        window_counts = batch["window_counts"]

        target = batch["labels"].to(DEVICE)

        logits = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            window_counts=window_counts,
        )

        preds = torch.argmax(
            logits,
            dim=1,
        )

        predictions.extend(
            preds.cpu().numpy()
        )

        labels.extend(
            target.cpu().numpy()
        )

##############################################
# METRICS
##############################################

accuracy = accuracy_score(
    labels,
    predictions,
)

precision, recall, f1, _ = precision_recall_fscore_support(
    labels,
    predictions,
    average="weighted",
    zero_division=0,
)

print("=" * 60)

print(f"Accuracy : {accuracy:.4f}")

print(f"Precision: {precision:.4f}")

print(f"Recall   : {recall:.4f}")

print(f"F1 Score : {f1:.4f}")

print("=" * 60)

print("\nClassification Report\n")

print(
    classification_report(
        labels,
        predictions,
        target_names=[
            "Seed",
            "Low",
            "Medium",
            "High",
        ],
        zero_division=0,
    )
)

print("\nConfusion Matrix\n")

print(
    confusion_matrix(
        labels,
        predictions,
    )
)