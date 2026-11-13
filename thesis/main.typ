// Thesis of the tux.ai project.
// Template: https://github.com/Filip-FK-Kwiatkowski/PJAIT-Typst-Thesis-Template (commit f0f8be3).
// Build (from this folder):  typst compile main.typ --font-path contents/assets/fonts
// Every value marked TODO below must be confirmed with the dean's office / the supervisor.
// The abstracts below are AI drafts (Claude, 2026-11-08): rewrite them in your own words (AI-use statement).
#import "pjatk-template.typ": apply-pjatk-template

#let abstract-en = [
    Large language models are increasingly used to answer questions about organisational records,
    but such records contain personal data that a model should neither receive nor memorise.
    This thesis presents tux.ai, a system that places a pseudonymisation layer between users and a language model.
    A hybrid detector, which combines the rule-based recognisers of Microsoft Presidio with a fine-tuned DistilBERT model,
    finds personal data in English text.
    Each detected value is replaced by a typed token whose identifier is a keyed hash of the value,
    and the original value is stored encrypted in a separate store.
    The model receives only tokens and the tokenised records retrieved for the question,
    and its answers are decrypted only for the types of data that the user's role permits; every decryption is logged.
    On an external test set of 1,000 synthetic documents,
    the hybrid detector reaches an F1 score of 0.930 and leaves 3.1% of the personal-data characters uncovered,
    compared with 30.9% for the rules alone.
    #text(fill: rgb("#a07000"))[TODO: one sentence with the results of the LLM evaluation.]
    The work also shows the limits of the approach:
    the detector is biased towards US formats, and a value that it misses reaches the model in plaintext.
]

#let abstract-pl = [
    Duże modele językowe są coraz częściej wykorzystywane do odpowiadania na pytania dotyczące dokumentów organizacji,
    jednak takie dokumenty zawierają dane osobowe, których model nie powinien ani otrzymywać, ani zapamiętywać.
    Praca przedstawia system tux.ai, który umieszcza warstwę pseudonimizacji pomiędzy użytkownikami a modelem językowym.
    Hybrydowy detektor, łączący oparte na regułach mechanizmy rozpoznawania biblioteki Microsoft Presidio z dostrojonym modelem DistilBERT,
    wykrywa dane osobowe w tekście w języku angielskim.
    Każda wykryta wartość jest zastępowana tokenem określającym jej typ, którego identyfikator jest skrótem wartości obliczanym z użyciem klucza,
    a oryginalna wartość jest przechowywana w postaci zaszyfrowanej w osobnym magazynie.
    Model otrzymuje wyłącznie tokeny oraz rekordy z tokenami wyszukane dla danego pytania,
    a jego odpowiedzi są odszyfrowywane tylko dla tych typów danych, na które pozwala rola użytkownika; każde odszyfrowanie jest rejestrowane.
    Na zewnętrznym zbiorze testowym liczącym 1000 syntetycznych dokumentów
    detektor hybrydowy osiąga miarę F1 równą 0,930 i pozostawia niewykryte 3,1% znaków danych osobowych,
    wobec 30,9% w przypadku samych reguł.
    #text(fill: rgb("#a07000"))[TODO: jedno zdanie z wynikami oceny modelu językowego.]
    Praca wskazuje także ograniczenia podejścia:
    detektor jest ukierunkowany na formaty amerykańskie, a wartość, której nie wykryje, trafia do modelu w postaci jawnej.
]

#show: apply-pjatk-template.with(
    language: "en",
    thesis-type: "engineering",
    // TODO: full name and album number, e.g. ("Arseny Surname --- s12345",)
    authors: ("Arseny SURNAME --- s00000",),
    // Working title. TODO: use the title registered with the dean's office.
    title: "Privacy-Preserving Use of Large Language Models on Personal Data with Hybrid PII Detection and Keyed Pseudonymisation",
    title-pl: "Wykorzystanie dużych modeli językowych na danych osobowych z ochroną prywatności dzięki hybrydowemu wykrywaniu danych osobowych i pseudonimizacji z kluczem",
    supervisor: "TODO: supervisor's academic title and name",
    supervisor-pl: "TODO: tytuł i imię i nazwisko promotora",
    reviewer: "TODO: reviewer's academic title and name",
    reviewer-pl: "TODO: tytuł i imię i nazwisko recenzenta",
    faculty: "Faculty of Computer Science",
    faculty-pl: "Wydział Informatyki",
    department: "TODO: department of the specialization",
    department-pl: "TODO: nazwa katedry",
    specialization: "TODO: specialization",
    specialization-pl: "TODO: nazwa specjalizacji",
    field-of-study: "Computer Science",
    field-of-study-pl: "Informatyka",
    abstract: abstract-en,
    keywords: [
        personal data #sym.dot.op pseudonymisation #sym.dot.op PII detection
        #sym.dot.op large language models #sym.dot.op retrieval-augmented generation
        #sym.dot.op role-based access control
    ],
    abstract-pl: abstract-pl,
    keywords-pl: [
        dane osobowe #sym.dot.op pseudonimizacja #sym.dot.op wykrywanie danych osobowych
        #sym.dot.op duże modele językowe #sym.dot.op generowanie wspomagane wyszukiwaniem
        #sym.dot.op kontrola dostępu oparta na rolach
    ],
)

#include "contents/introduction.typ"
#include "contents/context.typ"
#include "contents/functional-requirements.typ"
#include "contents/non-functional-requirements.typ"
#include "contents/use-cases.typ"
#include "contents/architecture.typ"
#include "contents/detection.typ"
#include "contents/pseudonymisation.typ"
#include "contents/llm-integration.typ"
#include "contents/detector-evaluation.typ"
#include "contents/llm-evaluation.typ"
#include "contents/conclusions.typ"
