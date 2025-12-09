import json
import argparse
import numpy as np
from datasets import Dataset, DatasetDict
from transformers import AutoTokenizer, AutoModelForTokenClassification, TrainingArguments, Trainer
from transformers import DataCollatorForTokenClassification
import evaluate
import torch

def load_data(file_path):
    with open(file_path, 'r') as f:
        data = json.load(f)
    return data

def align_labels_with_tokens(labels, word_ids):
    new_labels = []
    current_word = None
    for word_id in word_ids:
        if word_id != current_word:
            # Start of a new word!
            current_word = word_id
            label = -100 if word_id is None else labels[word_id]
            new_labels.append(label)
        elif word_id is None:
            # Special token
            new_labels.append(-100)
        else:
            # Same word as previous token
            label = labels[word_id]
            # If the label is B-XXX we change it to I-XXX
            if label % 2 == 1:
                label += 1
            new_labels.append(label)
    return new_labels

def tokenize_and_align_labels(examples, tokenizer, label2id):
    tokenized_inputs = tokenizer(examples["tokens"], truncation=True, is_split_into_words=True)

    labels = []
    for i, label in enumerate(examples["ner_tags"]):
        word_ids = tokenized_inputs.word_ids(batch_index=i)
        previous_word_idx = None
        label_ids = []
        for word_idx in word_ids:
            # Special tokens have a word id that is None. We set the label to -100 so they are automatically
            # ignored in the loss function.
            if word_idx is None:
                label_ids.append(-100)
            elif word_idx != previous_word_idx:
                # Only label the first token of a given word.
                label_ids.append(label[word_idx])
            else:
                # For subsequent tokens in a word, we set the label to -100 or the same label (I-tag)
                # Here we ignore them for simplicity, or we can use I-tag.
                # Let's use -100 to only train on the first token of each word, which is a common strategy.
                label_ids.append(-100)
            previous_word_idx = word_idx

        labels.append(label_ids)

    tokenized_inputs["labels"] = labels
    return tokenized_inputs

def prepare_dataset(data, tokenizer, label2id):
    # Convert character offsets to token-level tags (BIO scheme)
    # This requires tokenizing the text first to map char offsets to words?
    # Or we can do a simpler pre-tokenization split by space, then align.
    
    formatted_data = {
        "id": [],
        "tokens": [],
        "ner_tags": []
    }
    
    for idx, item in enumerate(data):
        text = item['text']
        entities = item['entities'] # list of [start, end, label]
        
        # Simple whitespace tokenization for alignment
        # Note: This assumes the tokenizer will handle subwords later.
        # We need to map char offsets to these "words".
        
        words = text.split()
        tags = ["O"] * len(words)
        
        # We need to map char indices to word indices.
        # This is tricky if we just split().
        # Let's reconstruct the mapping.
        
        char_to_word_idx = []
        current_word_idx = 0
        current_char_idx = 0
        
        # This loop is fragile if multiple spaces.
        # Let's use a more robust way: iterate through the text.
        
        word_starts = []
        word_ends = []
        
        # Find all words and their spans
        import re
        word_spans = [m.span() for m in re.finditer(r'\S+', text)]
        
        tokens = []
        ner_tags = []
        
        for start, end in word_spans:
            tokens.append(text[start:end])
            
            # Check if this word overlaps with any entity
            token_label = "O"
            for estart, eend, elabel in entities:
                # Check overlap
                if max(start, estart) < min(end, eend):
                    # Overlap found.
                    # Determine if B or I
                    if start == estart: # Exact match start
                        token_label = f"B-{elabel}"
                    elif start > estart: # Inside
                        token_label = f"I-{elabel}"
                    else: # Word starts before entity?
                        # "The[Name]" -> "The" is O? No, if "TheName" is one token?
                        # Assuming whitespace separation for now as per generation script.
                        if start < estart:
                             # If the word contains the start of the entity
                             # e.g. "Name:" where Name is entity.
                             # This is complex.
                             # For our generated data, we put spaces around things usually?
                             # The generation script: "My name is {name}." -> "My name is John Doe."
                             # "John" is B-PER, "Doe" is I-PER.
                             pass
                        token_label = f"B-{elabel}" # Fallback/Simplification
                    
                    # Refine logic:
                    if start >= estart and start < eend:
                        if start == estart:
                            token_label = f"B-{elabel}"
                        else:
                            token_label = f"I-{elabel}"
                    break
            ner_tags.append(token_label)
            
        # Convert tags to IDs
        ner_tag_ids = [label2id.get(t, label2id["O"]) for t in ner_tags]
        
        formatted_data["id"].append(str(idx))
        formatted_data["tokens"].append(tokens)
        formatted_data["ner_tags"].append(ner_tag_ids)

    return Dataset.from_dict(formatted_data)

def compute_metrics(p):
    predictions, labels = p
    predictions = np.argmax(predictions, axis=2)

    # Remove ignored index (special tokens)
    true_predictions = [
        [id2label[p] for (p, l) in zip(prediction, label) if l != -100]
        for prediction, label in zip(predictions, labels)
    ]
    true_labels = [
        [id2label[l] for (p, l) in zip(prediction, label) if l != -100]
        for prediction, label in zip(predictions, labels)
    ]

    results = metric.compute(predictions=true_predictions, references=true_labels)
    return {
        "precision": results["overall_precision"],
        "recall": results["overall_recall"],
        "f1": results["overall_f1"],
        "accuracy": results["overall_accuracy"],
    }

# Global maps
label_list = ["O", "B-PER", "I-PER", "B-LOC", "I-LOC", "B-ORG", "I-ORG", "B-PII", "I-PII"]
label2id = {l: i for i, l in enumerate(label_list)}
id2label = {i: l for i, l in enumerate(label_list)}
metric = evaluate.load("seqeval")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_file", type=str, default="data/train_data.json")
    parser.add_argument("--model_name", type=str, default="distilbert-base-uncased")
    parser.add_argument("--output_dir", type=str, default="models/pii_model")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--smoke_test", action="store_true")
    args = parser.parse_args()

    # Load data
    raw_data = load_data(args.data_file)
    
    # Initialize tokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    
    # Prepare dataset
    dataset = prepare_dataset(raw_data, tokenizer, label2id)
    
    # Split dataset
    dataset = dataset.train_test_split(test_size=0.2)
    
    # Tokenize
    tokenized_datasets = dataset.map(
        lambda x: tokenize_and_align_labels(x, tokenizer, label2id),
        batched=True
    )
    
    # Model
    model = AutoModelForTokenClassification.from_pretrained(
        args.model_name, num_labels=len(label_list), id2label=id2label, label2id=label2id
    )
    
    # Training Args
    training_args = TrainingArguments(
        output_dir=args.output_dir,
        eval_strategy="epoch",
        learning_rate=2e-5,
        per_device_train_batch_size=16 if not args.smoke_test else 2,
        per_device_eval_batch_size=16 if not args.smoke_test else 2,
        num_train_epochs=args.epochs if not args.smoke_test else 1,
        weight_decay=0.01,
        save_strategy="epoch",
        use_cpu=not torch.cuda.is_available() and not torch.backends.mps.is_available(),
    )
    
    # Data Collator
    data_collator = DataCollatorForTokenClassification(tokenizer=tokenizer)
    
    # Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_datasets["train"],
        eval_dataset=tokenized_datasets["test"],
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
    )
    
    # Train
    trainer.train()
    
    # Save
    trainer.save_model(args.output_dir)
    print(f"Model saved to {args.output_dir}")

if __name__ == "__main__":
    main()
