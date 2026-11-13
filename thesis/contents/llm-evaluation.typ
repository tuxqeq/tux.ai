#import "helpers.typ": todo, todo-inline

= Evaluation of the language model <LLMEvaluation>

This chapter reports how faithfully the language model handles tokens
and how much personal data appears in its answers.

#todo[Phase 3, not done yet. About 100 questions with known answers (the records are synthetic);
metrics: hallucinated-token rate, accuracy, leakage; configurations: A = fine-tuned without retrieval,
B = base Qwen3 with retrieval, C = fine-tuned with retrieval (optional).
Note: the old fine-tuned model was trained on the old corpus and must be retrained on corpus v2 for a fair A.]
