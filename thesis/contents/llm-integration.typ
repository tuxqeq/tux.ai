#import "helpers.typ": todo, todo-inline

= Language model integration <LLMIntegration>

This chapter describes how the language model receives the records of a dataset
and how its answers reach the user.

#todo[AI-drafted text (Claude, 2026-11-13), kept only as a reference.
The AI-use statement in this thesis says that AI did not generate essential parts of the work.
Rewrite this chapter in your own words, check every number against the decision log
(D-12, D-20 – D-30) and the code, and list the use of AI in the AI Usage Report.
The numbers of the corpus come from the run of 2026-11-13 (D-28); the final run (D-31)
re-created the corpus with a new key, so check that the counts are the same.]

== Two ways to give a model the records

A language model can answer questions about a set of records in two ways.
In the first way, the records are put into the weights of the model by fine-tuning,
and the model answers from what it has learned ("closed book").
In the second way, a retriever finds the records that are relevant to the question
and puts them into the prompt,
and the model answers from the text that it has just read
(retrieval-augmented generation, RAG) @Lewis2020RAG.
For factual knowledge, retrieval usually gives better answers than fine-tuning,
both for facts that the model saw during pre-training and for new facts @Ovadia2024FTvsRAG.

In this system the two ways differ also in their privacy properties,
because the model sees only pseudonymised text in both of them:

- *Erasure.* A record that is removed from the index is not available from the next question on.
  A record that was used for fine-tuning stays in the weights until the model is trained again.
- *New records.* A new record can be indexed in seconds.
  A fine-tuned model knows nothing about records that were added after training.
- *Missed values.* A value that the detector did not replace
  goes into the training data or into the index in plaintext.
  A fine-tuned model can memorise such a value and repeat it to any user @Carlini2021Extracting @Lukas2023Leakage;
  with retrieval, the value reaches the model only when its record is retrieved,
  and retrieval can itself leak the content of the index @Zeng2024RAGPrivacy.
- *Key separation.* Token ids are keyed per dataset (@Pseudonymisation).
  A fine-tuned model holds the ids of one dataset and is useless for another one;
  a retrieval index is created per dataset and needs no training.

The prototype started with fine-tuning; the final system uses retrieval.
@LLMEvaluation compares both ways on the same data.

== First prototype: fine-tuning without the records

The first prototype fine-tuned Qwen3-8B @Qwen3Report with QLoRA @Dettmers2023QLoRA
on the tokenised corpus.
Most training examples asked the model to *generate* a record of a given type
("Generate a customer record for …") without any record in the prompt.
The model learned the format of the records and of the tokens, but not their content:
it wrote well-formed tokens such as `[SSN_…]` that did not exist in the token map.
Such a token cannot be decrypted,
and an answer that contains it looks like an answer but carries an invented identifier.
This observation (decision log D-12) led to retrieval.

== Corpus

The corpus consists of synthetic records generated with Faker:
1,000 documents of five types (government contractor, healthcare professional,
international business, personal banking, technology start-up), 200 of each type, seed 42.
A record has about 1,300 characters on average (1,129 – 1,592).
The detector (version 4, @Detection) replaced the personal data with tokens
under a random 32-byte dataset key;
the plaintext documents were deleted after tokenisation.
The corpus contains 26,339 token occurrences and 24,748 distinct tokens;
the most frequent labels are the generic `PII` label (2,053), `PERSON` (1,796), `EMAIL` (1,732)
and `DOB` (1,601).
The token map (token → encrypted value) is stored in Redis without expiry,
and the dataset key is stored in PostgreSQL, wrapped with the master key.

#todo[Figure: one record before and after tokenisation (synthetic data, so it can be shown).
Note the values that stay in plaintext: income, card expiry date, project codes, hospital names,
and some identifiers that the detector missed (badge ids, access codes, GitHub user names).]

== Retrieval

Every dataset has its own ChromaDB collection,
so that a question in one dataset can never retrieve a record of another dataset.
Only tokenised text is indexed, embedded and put into prompts.

The embedding model all-MiniLM-L6-v2 reads at most 256 word pieces,
and one token such as `[PERSON_1a2b3c4d5e6f]` costs about ten word pieces.
An embedding of a whole record would therefore miss its later sections.
Each record is split into sections at blank lines,
the sections are embedded,
and each section points to its record ("small to big").
For the corpus this gives 1,000 records and 6,398 sections.

Retrieval returns at most three records ($k = 3$) in two steps:

+ *Token match.* The question is tokenised with the dataset key before retrieval.
  Because token ids are keyed but deterministic within a dataset,
  a name in the question gets the same id as the same name in the records.
  Records that contain an id of the question are ranked by the number of matched ids.
  Ids from the last turns of the chat are also used, with a lower weight,
  so that a follow-up question such as "And her date of birth?" finds the same record.
+ *Semantic search.* The free places are filled with the records of the most similar sections
  (cosine similarity at least 0.15).

The token match does the real work for questions about a person.
For the embedding model, a token is a random string, so semantic search can only use the words
around the tokens (field names, hospital names).
Questions that need many records, such as "Which people have their primary care at Johns Hopkins Hospital?",
cannot be answered with three records (decision log D-28).

== Prompt and chat flow

The retrieved records are put into the system prompt together with four rules:
use only the records, copy tokens exactly, never invent a token or guess a value,
and say so when the answer is not in the records.
The model is Qwen3-4B-Instruct-2507, quantised to 4 bits (q4_K_M),
served by Ollama with a context of 8,192 tokens.
The default Ollama tag `qwen3:4b` was not used:
it is the "thinking" variant, which writes its reasoning into the answer even when thinking is switched off,
and that reasoning would reach the user and the decryption step (decision log D-27).

One chat turn runs as follows:

+ The question is tokenised with the key of the chat's dataset.
  A chat must have a dataset with a key; otherwise the question would reach the model in plaintext.
+ Retrieval selects the records (previous section).
+ The model receives the system prompt with the records and the tokenised history,
  and streams its answer.
+ The streaming resolver (@Pseudonymisation) replaces tokens by their values
  for the entity types that the user's role may see, and writes every decryption to the audit log.
+ Only the tokenised question, the tokenised answer and a tokenised chat title are stored.

#todo[Sequence diagram of one chat turn: browser → Envoy (gRPC-Web) → API → detector → Chroma →
Ollama → resolver → browser.
Mention the four gaps found in the first test through the web UI (D-29): no dataset selector
(plaintext reached the model), plaintext chat titles, history without decryption,
no session id (no follow-up questions). None of them was visible in the component tests.]

== Closed-book fine-tuning as a fair alternative

The training data of the first prototype could not teach the model the content of the records.
For a fair comparison with retrieval (@LLMEvaluation),
a second fine-tuning data set puts the facts of the records into question–answer pairs:

- every pair "field → token" of a record becomes a question ("What is the SSN of `[PERSON_x]`?")
  with the answer "The SSN of `[PERSON_x]` is `[SSN_y]`.",
  in three phrasings, because a fact that is seen in one phrasing only
  may be memorised but not retrievable by other questions @AllenZhu2024Physics31;
- every record is also recited in full for two different requests;
- 5 % of the examples ask about people who do not exist, with the answer "I have no record of …".

Of the 1,000 records, 100 are held out as "new records":
they are in the retrieval index but not in the training data,
like records that are added after the model was trained.
The remaining 899 records give 19,062 facts and 56,089 training examples.
Qwen3-4B-Instruct-2507 was fine-tuned with QLoRA @Dettmers2023QLoRA
(LoRA @Hu2022LoRA with rank 64 on all projection matrices, 3 epochs, 10,308 steps)
on one RTX 4090 GPU.
