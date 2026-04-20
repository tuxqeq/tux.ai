import json
import re
import argparse
import numpy as np
from typing import Any, Dict, List
from datasets import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForTokenClassification,
    TrainingArguments,
    Trainer,
    DataCollatorForTokenClassification,
)
import evaluate
import torch


def load_data(file_path: str) -> List[Dict[str, Any]]:
    with open(file_path, "r") as f:
        data = json.load(f)
    for i, item in enumerate(data):
        if not isinstance(item.get("text"), str) or not isinstance(item.get("entities"), list):
            raise ValueError(
                f"Item {i} missing required 'text' (str) or 'entities' (list) keys"
            )
    return data


def prepare_dataset(
    data: List[Dict[str, Any]],
    tokenizer: Any,
    label2id: Dict[str, int],
) -> Dataset:
    formatted: Dict[str, list] = {"id": [], "tokens": [], "ner_tags": []}

    for idx, item in enumerate(data):
        text: str = item["text"]
        entities: list = item["entities"]

        # Single tokenization scheme: non-whitespace spans via regex
        word_spans = [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]
        tokens = [text[s:e] for s, e in word_spans]
        ner_tags = []

        for w_start, w_end in word_spans:
            tag = "O"
            for estart, eend, elabel in entities:
                if max(w_start, estart) < min(w_end, eend):
                    tag = f"B-{elabel}" if w_start <= estart else f"I-{elabel}"
                    break
            ner_tags.append(label2id.get(tag, label2id["O"]))

        formatted["id"].append(str(idx))
        formatted["tokens"].append(tokens)
        formatted["ner_tags"].append(ner_tags)

    return Dataset.from_dict(formatted)


def tokenize_and_align_labels(
    examples: Dict[str, Any],
    tokenizer: Any,
    label2id: Dict[str, int],
) -> Dict[str, Any]:
    tokenized_inputs = tokenizer(
        examples["tokens"], truncation=True, is_split_into_words=True
    )
    labels = []
    for i, label in enumerate(examples["ner_tags"]):
        word_ids = tokenized_inputs.word_ids(batch_index=i)
        prev_word_idx = None
        label_ids = []
        for word_idx in word_ids:
            if word_idx is None:
                label_ids.append(-100)
            elif word_idx != prev_word_idx:
                label_ids.append(label[word_idx])
            else:
                label_ids.append(-100)
            prev_word_idx = word_idx
        labels.append(label_ids)
    tokenized_inputs["labels"] = labels
    return tokenized_inputs


def build_compute_metrics(id2label: Dict[int, str], metric: Any):
    def compute_metrics(p: Any) -> Dict[str, float]:
        predictions, labels = p
        predictions = np.argmax(predictions, axis=2)
        true_preds = [
            [id2label[pred] for pred, lab in zip(row_pred, row_lab) if lab != -100]
            for row_pred, row_lab in zip(predictions, labels)
        ]
        true_labs = [
            [id2label[lab] for pred, lab in zip(row_pred, row_lab) if lab != -100]
            for row_pred, row_lab in zip(predictions, labels)
        ]
        results = metric.compute(predictions=true_preds, references=true_labs)
        return {
            "precision": results["overall_precision"],
            "recall": results["overall_recall"],
            "f1": results["overall_f1"],
            "accuracy": results["overall_accuracy"],
        }
    return compute_metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_file", type=str, default="data/train_data.json")
    parser.add_argument("--model_name", type=str, default="distilbert-base-uncased")
    parser.add_argument("--output_dir", type=str, default="models/pii_model")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--smoke_test", action="store_true")
    args = parser.parse_args()

    label_list = [
        "O",
        "B-PER",          "I-PER",
        "B-ORG",          "I-ORG",
        "B-LOC",          "I-LOC",
        "B-EMAIL",        "I-EMAIL",
        "B-PHONE",        "I-PHONE",
        "B-SSN",          "I-SSN",
        "B-CREDIT_CARD",  "I-CREDIT_CARD",
        "B-DOB",          "I-DOB",
        "B-LICENSE",      "I-LICENSE",
        "B-PASSPORT",     "I-PASSPORT",
        "B-IP_ADDRESS",   "I-IP_ADDRESS",
        "B-MRN",          "I-MRN",
        "B-BANK_ACCOUNT", "I-BANK_ACCOUNT",
        "B-USERNAME",     "I-USERNAME",
        "B-VIN",          "I-VIN",
        "B-API_KEY",      "I-API_KEY",
        "B-MAC",          "I-MAC",
        "B-EMP_ID",       "I-EMP_ID",
        "B-INSURANCE",    "I-INSURANCE",
    ]
    label2id: Dict[str, int] = {l: i for i, l in enumerate(label_list)}
    id2label: Dict[int, str] = {i: l for i, l in enumerate(label_list)}
    metric = evaluate.load("seqeval")

    raw_data = load_data(args.data_file)
    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    dataset = prepare_dataset(raw_data, tokenizer, label2id)
    dataset = dataset.train_test_split(test_size=0.2, seed=42)

    tokenized_datasets = dataset.map(
        lambda x: tokenize_and_align_labels(x, tokenizer, label2id),
        batched=True,
    )

    model = AutoModelForTokenClassification.from_pretrained(
        args.model_name,
        num_labels=len(label_list),
        id2label=id2label,
        label2id=label2id,
    )

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        eval_strategy="epoch",
        learning_rate=2e-5,
        per_device_train_batch_size=2 if args.smoke_test else 16,
        per_device_eval_batch_size=2 if args.smoke_test else 16,
        num_train_epochs=1 if args.smoke_test else args.epochs,
        weight_decay=0.01,
        save_strategy="epoch",
        use_cpu=not torch.cuda.is_available() and not torch.backends.mps.is_available(),
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_datasets["train"],
        eval_dataset=tokenized_datasets["test"],
        tokenizer=tokenizer,
        data_collator=DataCollatorForTokenClassification(tokenizer=tokenizer),
        compute_metrics=build_compute_metrics(id2label, metric),
    )

    trainer.train()
    trainer.save_model(args.output_dir)
    print(f"Model saved to {args.output_dir}")


if __name__ == "__main__":
    main()
