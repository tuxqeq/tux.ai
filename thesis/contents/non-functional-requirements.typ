#import "helpers.typ": todo, todo-inline

= Non-functional requirements <NonFunctionalRequirements>

#todo[AI-drafted text (Claude, 2026-11-08), kept only as a reference.
The AI-use statement in this thesis says that AI did not generate essential parts of the work.
Rewrite this chapter in your own words, check every claim against its source,
and list the use of AI in the AI Usage Report.]

This chapter lists the qualities that the system must have.
Most of them concern privacy and security, which are the purpose of the system.

#todo[Draft. Add measured values where a requirement has a number (latency, detector targets).]

== Privacy and security

- *NFR-01.* Personal data found by the detector are never sent to the language model,
  stored in the chat history or written to the retrieval index in plaintext; only tokens are.
- *NFR-02.* Token identifiers cannot be computed or reversed without the key of the dataset.
- *NFR-03.* The values in token maps are stored encrypted.
  The keys of datasets are stored encrypted with a master key,
  which is kept only in the configuration of the server.
- *NFR-04.* The hybrid detector leaves fewer personal-data characters uncovered
  than either of its components alone, on every test set.
- *NFR-05.* Retrieval never returns records of a dataset other than the one selected in the chat.
- *NFR-06.* Login attempts are limited to 10 per minute per client.

== Operation

- *NFR-07.* Answers are streamed to the user while they are generated.
  #todo-inline[time to the first visible word, measured on the GPU pod]
- *NFR-08.* The whole system runs on one machine with one GPU with 24 GB of memory;
  the detector runs on the CPU.
- *NFR-09.* The system can be installed from a fresh clone of the repository with the provided scripts.
- *NFR-10.* Experiments are reproducible:
  data generation and training use fixed random seeds,
  and model weights are identified by their SHA-256 hashes.
