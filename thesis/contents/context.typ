#import "helpers.typ": todo, todo-inline

= Context <Context>

#todo[AI-drafted text (Claude, 2026-11-08), kept only as a reference.
The AI-use statement in this thesis says that AI did not generate essential parts of the work.
Rewrite this chapter in your own words, check every claim against its source,
and list the use of AI in the AI Usage Report.]

This chapter describes the background of the work:
the legal notions of personal data and pseudonymisation,
the specific risks that language models create for personal data,
and the existing tools and methods that address these risks.

== Personal data and pseudonymisation

The GDPR defines personal data as any information relating to an identified or identifiable natural person.
A person is identifiable if they can be identified, directly or indirectly,
for example by a name, an identification number, location data or an online identifier @GDPR.
The term _personally identifiable information_ (PII), common in US practice,
has a similar meaning @NIST800122.

Article 4(5) of the GDPR defines pseudonymisation as processing
in such a manner that personal data can no longer be attributed to a specific person
without the use of additional information,
provided that this information is kept separately
and is subject to technical and organisational measures @GDPR.
Pseudonymised data remain personal data for anyone who can re-identify them.
The European Data Protection Board recommends pseudonymisation as a safeguard
and stresses that the information needed for re-identification,
in practice cryptographic keys or lookup tables,
must be kept separate and protected @EDPB2025Pseudonymisation.

In 2025, the Court of Justice of the European Union held
that pseudonymised data are not necessarily personal data for a recipient
who has no means reasonably likely to be used to re-identify the persons concerned,
while they remain personal data for the controller that holds the additional information @CJEU2025SRB.
For the system described here,
the organisation that holds the keys must treat tokenised records as personal data.
For an operator of a language model that receives only tokens,
the assessment depends on whether re-identification is reasonably likely,
for example from the remaining, untokenised text.
This thesis does not rely on that distinction
and treats all tokenised data as personal data.

Outside the European Union, the HIPAA Privacy Rule in the United States
defines the _Safe Harbor_ method of de-identification of health information:
18 types of identifiers must be removed,
among them names, geographic subdivisions smaller than a state,
all elements of dates (except the year) directly related to a person,
and identification numbers @HIPAASafeHarbor.
The entity types of this work overlap with this list,
and its rule for geographic units is used in the evaluation of the detector (@DetectorEvaluation).

== Privacy risks of language models

Language models expose personal data in three ways.

+ *Disclosure in prompts.*
  A text sent to a model is processed, and often stored, by the operator of the model.
  The OWASP Top 10 for LLM Applications names the disclosure of personal and confidential data
  through prompts, outputs and training data as one of the most critical risks @OWASP2025LLM02.
+ *Memorisation.*
  Carlini et al. extracted hundreds of verbatim training sequences from GPT-2,
  among them names, telephone numbers and e-mail addresses @Carlini2021Extracting.
  Lukas et al. measured the leakage of PII from fine-tuned language models
  and showed that removing PII from the training data (scrubbing)
  and differentially private training reduce the leakage but do not prevent it @Lukas2023Leakage.
+ *Retrieval.*
  Retrieval-augmented generation adds an external store
  whose content is shown to the model at query time.
  Zeng et al. showed that data from this store can be extracted through crafted prompts,
  while retrieval can at the same time reduce the leakage of the model's training data @Zeng2024RAGPrivacy.

A pseudonymisation layer addresses the three exposures in the same way.
If records are tokenised before they are used in prompts, in training or in a retrieval store,
what can be disclosed, memorised or extracted are tokens.
The effectiveness of the layer then depends on the recall of the detector.
This is why the detector in this work is evaluated mainly by the share of personal-data characters it leaves uncovered.

== Related works and alternatives

Related work falls into three groups:
tools that detect personal data,
methods that transform detected values,
and methods that make the use of language models more private.

=== Detection of personal data

Microsoft Presidio is an open-source framework for the detection and anonymisation of personal data.
It detects entities with pattern recognisers, which can use context words and checksums,
and with a named-entity recognition model;
detected values can then be replaced, masked, hashed or encrypted @Presidio.
This work uses Presidio as the rule-based component of its detector.

Cloud providers offer detection of personal data as a service.
Amazon Comprehend detects PII entities in English and Spanish documents @AWSComprehendPII.
Azure AI Language identifies, categorises and redacts PII in texts, conversations and documents @AzurePII.
Google Cloud Sensitive Data Protection detects sensitive data and supports several de-identification transformations @GoogleSDPPseudonymization.
These services require the text to be sent to the provider,
which is the kind of disclosure that this work tries to avoid,
and their models cannot be adapted to the formats of a particular organisation.

Detection can also be treated as named-entity recognition with a fine-tuned transformer encoder,
such as BERT @Devlin2019BERT or its distilled variant DistilBERT,
which is 40% smaller and 60% faster than BERT while it keeps 97% of its language-understanding performance @Sanh2019DistilBERT.
Such models need labelled training data.
Because real personal data cannot be shared freely,
public datasets for this task are synthetic,
for example Nemotron-PII, generated with NVIDIA NeMo Data Designer for documents of more than 50 industries @NemotronPII,
and the ai4privacy corpora @Ai4PrivacyPII300k.
Both are used in this work.

=== Transformations of detected values

Once a value is detected, it can be transformed in several ways.
@tab-transformations compares the main options
by three properties that matter for use with a language model:
whether the original value can be recovered by its owner,
whether equal values receive equal replacements (so that records about the same person stay linked),
and whether the replacement keeps the format of the original value.

#block(breakable: false)[#figure(
    table(
        columns: (2.1fr, 1.2fr, 1.1fr, 0.9fr),
        align: (left, center, center, center),
        table.header([*Transformation*], [*Reversible*], [*Equal → equal*], [*Keeps format*]),
        [Redaction or masking (`<PERSON>`, `****`)], [no], [no], [no],
        [Keyed hashing, e.g. HMAC @RFC2104], [no], [yes], [no],
        [Deterministic encryption with a type annotation @GoogleSDPPseudonymization], [yes, with the key], [yes], [no],
        [Format-preserving encryption @NIST80038G], [yes, with the key], [yes], [yes],
        [This work: typed token with a keyed-hash identifier; encrypted value stored separately], [yes, with the key and the token map], [yes, within a dataset], [no],
    ),
    caption: [Transformations of detected personal data.],
) <tab-transformations>]

Deterministic transformations keep equality.
This allows a model to relate records about the same person,
and in this work it allows records to be retrieved by the token of a person.
The price is that equality becomes visible:
an observer of tokenised data learns which records share a value,
and frequency analysis can reveal frequent values,
a known weakness of deterministic and other property-preserving encryption @Naveed2015Inference.
Format-preserving encryption hides the fact that a value was replaced.
This is useful for systems that validate formats,
but a language model cannot tell such a value from a real one.
The approach of this work is closest to deterministic encryption with a type annotation:
the type of the value stays visible, which helps the model,
and the identifier is consistent within a dataset but differs between datasets with different keys.

=== Privacy-preserving use of language models

Differentially private training,
in which the influence of every single training example on the model is bounded @Abadi2016DPSGD,
reduces memorisation at a cost in model quality,
and it does not protect data that are sent to the model in prompts @Lukas2023Leakage.
Scrubbing personal data from training data
is a form of the same detection-and-removal step as in this work,
but without the possibility to restore the values for authorised users.
Running the model on the organisation's own infrastructure removes the third-party operator,
but it does not prevent memorisation,
and it does not restrict which users see which data in the answers.

The system described in this thesis combines
pseudonymisation of all text before it reaches the model,
retrieval over pseudonymised records,
and decryption of the model's answers under role-based access control.
None of these components is new on its own.
The contribution of the work lies in their combination
and in the measurement of how well the combination protects personal data.
