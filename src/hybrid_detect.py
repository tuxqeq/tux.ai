import sys
import os
import argparse
from transformers import pipeline
from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
import re
import base64

# Suppress tokenizer warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"

class HybridDetector:
    def __init__(self, ai_model_path, use_ai=True, ai_threshold=0.95):
        print("Initializing Hybrid Detector (AI + `Presidio`)...")
        
        # Configuration
        self.use_ai = use_ai
        self.ai_threshold = ai_threshold
        
        # 1. Load Presidio Rule-Based Engine
        print("Loading `Presidio` analyzer...")
        self.analyzer = AnalyzerEngine()
        
        # 2. Load AI Model (optional)
        if self.use_ai:
            print(f"Loading AI model from {ai_model_path}...")
            self.ai_classifier = pipeline(
                "token-classification", 
                model=ai_model_path, 
                tokenizer=ai_model_path, 
                aggregation_strategy="simple"
            )
            print(f"AI threshold set to: {ai_threshold} (only high-confidence detections)")
        else:
            print("AI detection disabled - using Presidio rules only")
            self.ai_classifier = None
        
        print("Hybrid detector ready!")
        
    def detect(self, text):
        results = []
        
        # --- Step 1: Rule-Based Detection (Presidio) ---
        presidio_entities = [
            "PHONE_NUMBER", "EMAIL_ADDRESS", "CREDIT_CARD", "CRYPTO", 
            "DATE_TIME", "IBAN_CODE", "IP_ADDRESS", "NRP", 
            "LOCATION", "PERSON", "US_BANK_NUMBER", "US_DRIVER_LICENSE",
            "US_ITIN", "US_PASSPORT", "US_SSN", "UK_NHS", 
            "MEDICAL_LICENSE", "URL"
        ]
        
        presidio_results = self.analyzer.analyze(
            text=text,
            entities=presidio_entities,
            language='en'
        )
        
        # Convert Presidio results
        presidio_spans = set()
        for res in presidio_results:
            results.append({
                "start": res.start,
                "end": res.end,
                "label": res.entity_type,
                "text": text[res.start:res.end],
                "source": "PRESIDIO",
                "score": res.score
            })
            # Track spans for deduplication
            for i in range(res.start, res.end):
                presidio_spans.add(i)
        
        # --- Step 2: AI Detection (only if enabled and Presidio didn't catch it) ---
        if self.use_ai and self.ai_classifier:
            ai_results = self.ai_classifier(text)
            
            # Only add AI results that don't overlap with Presidio and meet threshold
            for ai_res in ai_results:
                ai_start = ai_res['start']
                ai_end = ai_res['end']
                ai_score = ai_res['score']
                
                # Skip low-confidence detections
                if ai_score < self.ai_threshold:
                    continue
                
                # Check if ANY character overlaps with Presidio detection
                overlaps = any(i in presidio_spans for i in range(ai_start, ai_end))
                
                if not overlaps:
                    results.append({
                        "start": ai_start,
                        "end": ai_end,
                        "label": ai_res['entity_group'],
                        "text": ai_res['word'],
                        "source": "AI_MODEL",
                        "score": ai_score
                    })
        
        # Sort by start position
        results.sort(key=lambda x: x['start'])
        return results
    
    def encrypt_text(self, text, results, aes_key):
        """
        Encrypt detected PII in text using AES encryption
        Merges overlapping/adjacent detections to avoid breaking tokens
        """
        if not results:
            return text
        
        # Sort results by start position
        sorted_results = sorted(results, key=lambda x: x['start'])
        
        # Merge overlapping or adjacent entities
        merged = []
        current = sorted_results[0].copy()
        
        for next_entity in sorted_results[1:]:
            # If overlapping or adjacent (within 1 char), merge
            if next_entity['start'] <= current['end'] + 1:
                # Extend current entity
                current['end'] = max(current['end'], next_entity['end'])
                current['text'] = text[current['start']:current['end']]
                # Keep higher score
                if next_entity['score'] > current['score']:
                    current['label'] = next_entity['label']
                    current['source'] = next_entity['source']
                    current['score'] = next_entity['score']
            else:
                # No overlap, save current and start new
                merged.append(current)
                current = next_entity.copy()
        
        # Don't forget the last one
        merged.append(current)
        
        # Convert to Presidio RecognizerResult format
        presidio_results = []
        for res in merged:
            presidio_results.append(
                RecognizerResult(
                    entity_type=res['label'],
                    start=res['start'],
                    end=res['end'],
                    score=res['score']
                )
            )
        
        # Initialize anonymizer
        anonymizer = AnonymizerEngine()
        
        # Configure AES encryption
        key_base64 = base64.b64encode(aes_key).decode('utf-8')
        encryption_config = {
            "DEFAULT": OperatorConfig(
                operator_name="encrypt",
                params={"key": key_base64}
            )
        }
        
        # Encrypt the text
        anonymized_result = anonymizer.anonymize(
            text=text,
            analyzer_results=presidio_results,
            operators=encryption_config
        )
        
        return anonymized_result.text

def main():
    parser = argparse.ArgumentParser(description="Hybrid PII Detection and Encryption (AI + Presidio)")
    parser.add_argument("--text", type=str, help="Text to analyze")
    parser.add_argument("--file", type=str, help="File to analyze")
    parser.add_argument("--output", type=str, help="Output file for encrypted text (optional)")
    parser.add_argument("--model_path", type=str, default="models/pii_model_advanced", help="Path to AI model")
    parser.add_argument("--encrypt", action="store_true", help="Encrypt detected PII")
    parser.add_argument("--key", type=str, default="16ByteSecureKey!", help="AES encryption key (16/24/32 bytes)")
    parser.add_argument("--no-ai", action="store_true", help="Disable AI detection, use Presidio rules only")
    parser.add_argument("--ai-threshold", type=float, default=0.95, help="Minimum confidence for AI detections (0.0-1.0, default: 0.95)")
    args = parser.parse_args()
    
    # Validate encryption key
    aes_key = args.key.encode('utf-8')
    if len(aes_key) not in [16, 24, 32]:
        print(f"ERROR: AES key must be 16, 24, or 32 bytes, got {len(aes_key)}")
        return
    
    # Initialize detector with options
    use_ai = not args.no_ai
    detector = HybridDetector(args.model_path, use_ai=use_ai, ai_threshold=args.ai_threshold)
    
    text = ""
    if args.text:
        text = args.text
    elif args.file:
        with open(args.file, 'r') as f:
            text = f.read()
    else:
        print("Enter text to analyze (type 'exit' to quit):")
        while True:
            text = input(">> ")
            if text.lower() in ["exit", "quit"]:
                break
            results = detector.detect(text)
            print_results(results)
            
            if args.encrypt:
                encrypted_text = detector.encrypt_text(text, results, aes_key)
                print(f"\n{'='*70}")
                print("ENCRYPTED TEXT:")
                print(f"{'='*70}")
                print(encrypted_text)
                print(f"{'='*70}\n")
        return

    # Detect PII
    results = detector.detect(text)
    print_results(results)
    
    # Encrypt if requested
    if args.encrypt and results:
        encrypted_text = detector.encrypt_text(text, results, aes_key)
        
        print(f"\n{'='*70}")
        print("ENCRYPTED TEXT:")
        print(f"{'='*70}")
        print(encrypted_text)
        print(f"{'='*70}\n")
        
        # Save to file if output specified
        if args.output:
            with open(args.output, 'w') as f:
                f.write(encrypted_text)
            print(f"✓ Encrypted text saved to: {args.output}\n")
        elif args.file:
            # Auto-generate output filename
            output_file = args.file.replace('.txt', '_encrypted.txt')
            if output_file == args.file:
                output_file = args.file + '_encrypted'
            with open(output_file, 'w') as f:
                f.write(encrypted_text)
            print(f"✓ Encrypted text saved to: {output_file}\n")

def print_results(results):
    print(f"\nFound {len(results)} entities:")
    for res in results:
        print(f"  - [{res['source']}] {res['label']}: '{res['text']}' (Score: {res['score']:.2f})")

if __name__ == "__main__":
    main()
