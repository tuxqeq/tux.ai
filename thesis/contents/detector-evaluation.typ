#import "helpers.typ": todo, todo-inline

= Evaluation of the detector <DetectorEvaluation>

This chapter reports how well the detector finds personal data on data it was not trained on.

== Test data

#todo[Held-out templates (5,000 sentences, seed 7, D-03); Nemotron-PII test sample (1,000 documents,
seed 7, label mapping, merges, HIPAA rule for geography, D-10); ai4privacy English validation sample
(1,000 texts, D-17); the Nemotron dev set used for choosing settings (D-18).]

== Metrics

#todo[Typed precision, recall and F1 (overlap-based, one-to-one); exact F1; entity recall; full coverage;
uncovered characters (all PII and our types); spurious spans; the OTHER and ignore buckets (D-09);
with and without ORG (D-13).]

== Results

#todo[Table of section 0 of the decision log (Presidio only / AI only / hybrid for v3 and v4 on the
three test sets).]

== Error analysis

#todo[Where the characters leak: locale bias on ai4privacy (dates in words, non-US identity numbers,
house numbers and UK postcodes, non-Anglo names); spurious spans on Nemotron.]
