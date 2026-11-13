#import "helpers.typ": todo, todo-inline

= Language model integration <LLMIntegration>

This chapter describes how the language model receives the records of a dataset
and how its answers reach the user.

== First prototype: fine-tuning

#todo[Qwen3-8B fine-tuned with QLoRA on the tokenised corpus; training examples without the record in
the context; the observed hallucinated tokens (D-12). Why this led to retrieval.]

== Corpus

#todo[Synthetic records (`llm/generate_synthetic_docs.py`, 5 record types, seed 42); corpus v2:
random key, maps without expiry, detector v4 (D-22).]

== Retrieval

#todo[One ChromaDB collection per dataset; records split into sections for embeddings
(all-MiniLM-L6-v2 reads 256 word pieces); token match first, then semantic search; k = 3 (D-23).]

== Prompt and chat flow

#todo[System prompt rules; Qwen3 4B via Ollama with an 8,192-token context; streamed answer;
tokenised storage of messages.]
