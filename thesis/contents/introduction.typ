#import "helpers.typ": todo, todo-inline

= Introduction <Introduction>

#todo[AI-drafted text (Claude, 2026-11-08), kept only as a reference.
The AI-use statement in this thesis says that AI did not generate essential parts of the work.
Rewrite this chapter in your own words, check every claim against its source,
and list the use of AI in the AI Usage Report.]

Large language models (LLMs) are increasingly used
to search, summarise and answer questions about organisational records,
such as personnel files, customer databases and patient records.
These records contain personal data.
When a record is placed in a prompt,
the personal data in it are disclosed to the operator of the model
and stored in prompt logs and chat histories.
When records are used to fine-tune a model,
the model can memorise them:
verbatim training data, including names, telephone numbers and e-mail addresses,
can be extracted from trained language models @Carlini2021Extracting,
and removing identifiers before training reduces this leakage
but does not eliminate it @Lukas2023Leakage.
The OWASP Top 10 for LLM Applications
lists sensitive information disclosure
among the most critical risks of systems built on language models @OWASP2025LLM02.

Organisations often react to these risks by restricting the use of language models altogether.
In 2023, after engineers had uploaded internal source code to ChatGPT,
Samsung prohibited the use of generative AI tools on company devices @Gurman2023Samsung.
A ban removes the risk, but it also removes the benefit.

A less drastic approach is to remove personal data before a text reaches the model.
Simple redaction, which replaces every name with the same placeholder such as `<PERSON>`,
protects the data but destroys the references between records:
the model can no longer tell which salary belongs to which employee,
and a user cannot ask a question about a specific person.

This thesis presents _tux.ai_,
a system that places a pseudonymisation layer between its users and the model.
Each detected value is replaced by a typed token, for example `[PERSON_1a2b3c4d5e6f]`.
The identifier in the token is a keyed hash of the value:
the same value receives the same token everywhere in a dataset,
but the value cannot be recovered from the token without the key.
The original value is encrypted and stored separately from the text.
The model therefore works only with tokens.
When an answer of the model contains tokens,
the system decrypts them only for the types of data that the user's role permits
and records every decryption in an audit log.
This corresponds to the definition of pseudonymisation in the General Data Protection Regulation (GDPR):
personal data that can no longer be attributed to a person without additional information,
which is kept separately and protected by technical and organisational measures @GDPR.

The protection is only as good as the detection of personal data:
a value that the detector misses reaches the model in plaintext.
For this reason the system uses a hybrid detector.
The rule-based recognisers of Microsoft Presidio @Presidio
are combined with a DistilBERT model @Sanh2019DistilBERT fine-tuned for token classification,
and the spans that the two components find are merged.

A second design question is how the model obtains the records.
A first prototype fine-tuned a Qwen3 model @Qwen3Report on the tokenised records.
In manual tests this model answered with tokens that had the correct format
but did not exist in the token store, so they could not be decrypted.
The system was therefore redesigned around retrieval-augmented generation (RAG) @Lewis2020RAG:
for every question, the relevant tokenised records are retrieved and placed in the prompt,
and the model is instructed to copy tokens exactly.

== Goals <Goals>

The main goal of this work is
to design, implement and evaluate a system
that allows a language model to answer questions about records that contain personal data
without the model receiving these data in plaintext,
while authorised users still see the real values.
The specific goals are:

+ *Detection.*
  To build a detector of personal data in English text
  that covers 19 types of entities
  (names, addresses, identification numbers, financial and technical identifiers),
  and to evaluate it on data that it was not trained on,
  with metrics that show how much personal data remains uncovered.
+ *Pseudonymisation.*
  To design a token scheme and a key management scheme
  in which tokens are consistent within a dataset,
  cannot be reversed without the key,
  and are decrypted only on the server.
+ *Application.*
  To implement a chat application
  in which users ask questions about a dataset,
  the model receives the tokenised records retrieved for the question,
  and the answer is decrypted according to role-based permissions and logged.
+ *Evaluation of the language model.*
  To measure how often the model produces tokens that do not exist (hallucinated tokens),
  how often its answers are correct,
  and how often personal data appear in plaintext,
  and to compare a fine-tuned model without retrieval with a base model with retrieval.

For an organisation, the value of the work is a way
to use a language model on records with personal data
while the data stay under the organisation's control.
Because only tokens leave the pseudonymisation layer,
the design also allows the model to be operated by a third party.
For research, the work provides measurements of
how a detector trained on synthetic sentence templates generalises
to realistic documents and to an independent data generator,
and of how faithfully language models copy pseudonymous tokens.

The scope of the work is limited as follows.
Only English text is supported.
All data used for training and evaluation are synthetic;
no real personal data were processed.
Pseudonymised data remain personal data in the sense of the GDPR @EDPB2025Pseudonymisation,
so the system reduces the exposure of personal data but does not anonymise them.
The language model runs locally, on a single rented GPU.

== Conventions

The following conventions are used in this document.

- A monospaced font is used for file names, identifiers from the source code, commands and tokens,
  for example `src/hybrid_detect.py` or `[SSN_9924d46d033a]`.
  Identifiers in example tokens are illustrative;
  real identifiers depend on the key of the dataset.
- Entity types are written in capitals and use the labels of the detector,
  for example PER (name of a person), LOC (location) or SSN (US Social Security number).
  The full list of types is given in @Detection.
- Numbers use a decimal point.
  Shares of uncovered characters are given in per cent with one decimal place.
- The document uses British spelling.
  Names of software components keep their original spelling, for example `tokenizer`.

=== Glossary of terms

/ Personal data, PII: Information relating to an identified or identifiable natural person @GDPR.
  In this document, _personal data_ and _personally identifiable information_ (PII) @NIST800122 are used as synonyms.
/ Entity type: A category of personal data, for example the name of a person or a credit card number.
/ Span: A continuous range of characters in a text that the detector marks as one entity.
/ Pseudonymisation: Processing of personal data in such a way that they can no longer be attributed to a person
  without additional information that is kept separately @GDPR.
/ Token: The placeholder that replaces a detected value, written as `[TYPE_identifier]`,
  where the identifier is a keyed hash of the value.
/ Token map: The mapping from tokens to the encrypted original values of one document or dataset.
/ Dataset key: A random secret key of a dataset.
  It is used to derive token identifiers and to encrypt the values in the token map.
/ Master key: A server-side key that encrypts the dataset keys stored in the database.
/ Hybrid detector: The detector that merges the spans found by the Presidio rules and by the fine-tuned DistilBERT model.
/ Uncovered characters (leak): The share of personal-data characters in the reference annotations
  that no predicted span covers; the main privacy metric of this work.
/ Hallucinated token: A token in an answer of the model that does not exist in the token map of the dataset.
/ RAG: Retrieval-augmented generation:
  generation in which documents retrieved for a question are added to the prompt of the model @Lewis2020RAG.
/ RBAC: Role-based access control;
  here, the permissions of a user to see the decrypted values of given entity types in a given dataset.

== Results

The work produced a working system and an evaluation of its detection component.

The implemented system consists of the hybrid detector,
the pseudonymisation of documents and chat messages with keyed tokens and an encrypted token store,
the retrieval of tokenised records per dataset,
a chat with streamed answers and role-based decryption,
and an audit log of decryptions.
It is built with Python, FastAPI, gRPC, React, PostgreSQL, Redis, ChromaDB and Ollama.

The final detector was tested once on each of three test sets.
On 1,000 synthetic documents from the test split of Nemotron-PII @NemotronPII
(the training used other documents of the same dataset),
it reaches a typed F1 score of 0.930 and leaves 3.1% of the personal-data characters uncovered,
whereas Presidio alone leaves 30.9% and the neural model alone 5.2%.
On sentence templates held out from training, it reaches an F1 score of 0.980 and leaves 1.1% uncovered.
On texts from an independent generator, ai4privacy @Ai4PrivacyPII300k,
22.7% of the characters remain uncovered,
mostly dates written in words, non-US identity numbers and addresses.
On all three sets, the hybrid detector leaves fewer characters uncovered than either of its components alone.

During development, several weaknesses of an earlier prototype were found and corrected,
among them unkeyed token identifiers that could be reversed by guessing values,
a plaintext export of the token map,
and a decryption step that failed for tokens split across streamed chunks of an answer.

#todo[Results of the evaluation of the language model (@LLMEvaluation):
hallucinated-token rate, accuracy and leakage for the compared configurations;
what was not accomplished.]

== Document structure

The rest of the document is organised as follows.

- @Context describes personal data and pseudonymisation,
  the privacy risks of language models, and related tools and methods.
- @FunctionalRequirements and @NonFunctionalRequirements state the requirements of the system.
- @UseCases describes the actors of the system and its use cases.
- @Architecture presents the components of the system and the flow of data between them.
- @Detection describes the hybrid detector.
- @Pseudonymisation describes the tokens, the encryption of values and the management of keys.
- @LLMIntegration describes the retrieval of records and the chat with the language model.
- @DetectorEvaluation and @LLMEvaluation report the evaluation of the detector and of the language model.
- @Conclusions summarises the work, its limitations and possible future work.
