#import "helpers.typ": todo, todo-inline

= Detection of personal data <Detection>

This chapter describes the hybrid detector:
the entity types it covers, its two components, and how their results are merged.

== Entity types

#todo[Table of the 19 types (PER, ORG, LOC, EMAIL, PHONE, SSN, DOB, CREDIT_CARD, BANK_ACCOUNT, ...)
plus the generic PII label of v4; token names after normalisation (LICENSE → DL, AWS_KEY → API_KEY).
Source: `src/utils.py`, `src/pseudonymize.py`, decision log D-08, D-14, D-18.]

== Rule-based component

#todo[Presidio analyzer with built-in recognisers and custom pattern recognisers
(`src/recognizers.py`); fixes of keyword-triggered patterns (D-15).]

== Neural component

#todo[DistilBERT token classification, BIO labels on the first sub-token of each word.
Training data: v3 = Faker templates with a template-level train/test split (D-03, D-04);
v4 = Nemotron-PII documents cut into windows + templates (D-14). Training settings and times.]

== Word-level inference

#todo[Why the default pipeline produced fragments; one label per word; windows of at most 32 words
at line breaks (D-06, D-07).]

== Merging the components

#todo[Union of overlapping spans; label rule "AI first"; settings chosen on the Nemotron dev set
with the criterion "privacy first" (D-05, D-18).]
