#import "helpers.typ": todo, todo-inline

= System architecture <Architecture>

This chapter presents the components of the system and the flow of data between them.

#todo[Components: React web client; Envoy (gRPC-Web); FastAPI REST API + gRPC chat service;
PostgreSQL (users, datasets, wrapped keys, permissions, tokenised chats, audit log);
Redis (token maps); ChromaDB (retrieval index per dataset); Ollama (language model);
the detector (Presidio + DistilBERT) inside the API process.
Diagrams to reuse and update: `presentation/diagrams/diagram_runtime_flow.svg`,
`diagram_tokenization.svg`, `diagram_llm_pipeline.svg`.]

== Preparation of a dataset

#todo[Documents → detection → tokens + encrypted token map (Redis) → tokenised files →
dataset row and wrapped key (PostgreSQL), dataset token map, retrieval index (ChromaDB).
Scripts: `llm/prepare_corpus.py`, `scripts/bootstrap_dataset.py`.]

== Answering a question

#todo[Question → sanitising → detection → tokens → retrieval (token match, then semantic) →
prompt with records → Ollama → streamed tokens → buffered decryption with RBAC → audit log → client.
Only tokenised text is stored in PostgreSQL.]

== Deployment

#todo[Single GPU pod (RunPod, 24 GB), SSH tunnel only; `scripts/pod.sh`, `scripts/pod_rag_setup.sh`;
what persists on the volume and what does not (decision log D-25).]
