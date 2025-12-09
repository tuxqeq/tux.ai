from transformers import pipeline
import argparse

def predict(text, model_path):
    # Load the token classification pipeline
    # aggregation_strategy="simple" merges sub-tokens back into words/entities
    classifier = pipeline("token-classification", model=model_path, tokenizer=model_path, aggregation_strategy="simple")
    
    results = classifier(text)
    
    print(f"\nInput: {text}")
    print("Detected Entities:")
    if not results:
        print("  No entities detected.")
    
    for entity in results:
        print(f"  - {entity['entity_group']}: {entity['word']} (Score: {entity['score']:.4f})")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_path", type=str, default="models/pii_model_full")
    parser.add_argument("--text", type=str, help="Text to analyze. If not provided, runs in interactive mode.")
    args = parser.parse_args()

    if args.text:
        predict(args.text, args.model_path)
    else:
        print(f"Loaded model from {args.model_path}")
        print("Enter text to analyze (type 'exit' to quit):")
        while True:
            user_input = input(">> ")
            if user_input.lower() in ["exit", "quit"]:
                break
            predict(user_input, args.model_path)
