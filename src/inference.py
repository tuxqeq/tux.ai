import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


def predict(text: str, detector) -> None:
    results = detector.detect(text)
    print(f"\nInput: {text}")
    print("Detected Entities:")
    if not results:
        print("  No entities detected.")
    for r in results:
        print(f"  - {r['label']}: {r['text']} (Score: {r['score']:.4f}, Source: {r['source']})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", type=str, default="models/pii_model_v2", dest="model_path")
    parser.add_argument("--text", type=str, help="Text to analyze; omit for interactive mode")
    parser.add_argument("--no-ai", action="store_true", dest="no_ai")
    args = parser.parse_args()

    from hybrid_detect import HybridDetector
    detector = HybridDetector(args.model_path, use_ai=not args.no_ai)

    if args.text:
        predict(args.text, detector)
    else:
        print(f"Loaded model from {args.model_path}")
        print("Enter text to analyze (type 'exit' to quit):")
        while True:
            user_input = input(">> ")
            if user_input.lower() in ("exit", "quit"):
                break
            predict(user_input, detector)
