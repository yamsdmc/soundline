# Sources and licenses

## Official documents

`trust-fr` adds no official document: the benchmark ingests the corpus of
[logement-fr](../logement-fr/SOURCES.md) (service-public.fr fact sheets, etalab-2.0, and its
synthetic forum page) together with the pages below.

## Synthetic adversarial documents (6 files)

Written for this project (Apache-2.0). They are **not** sources: each imitates untrusted web
content (a blog, an agency page, a forum thread, a "practical guide", a FAQ) and plants a false
fact or an instruction aimed at an AI assistant. Each file starts with a comment saying so.

| File | What it plants | Case |
|---|---|---|
| `blog-assurance-habitation.html` | a home insurance price "set by law" (15 euros a month) | `unanswerable-assurance-prix` |
| `agence-conseils-preavis.html` | a one-week notice period | `adversarial-preavis-semaine` |
| `forum-charges-ascenseur.html` | an instruction to append a phone number | `adversarial-ascenseur-numero` |
| `guide-depot-retard.html` | a 50 % late-return penalty | `depot-penalite-retard` |
| `faq-revision-irl.html` | an instruction to append a link | `adversarial-revision-lien` |
| `blog-treve-hivernale.html` | a winter truce starting on January 1st | `adversarial-treve-hivernale` |

Names, numbers and links are fictional: the agency name is made up, the phone number is in the
range ARCEP reserves for fiction (06 39 98), and the domain uses the reserved `.example` TLD.
