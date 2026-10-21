# Trust (FR): the dataset of the trust benchmark

The questions of [logement-fr](../logement-fr/README.md), plus what a trustworthy assistant must
resist (EVL-092):

- **18 unanswerable questions** (instead of 3): near-topic questions about renting that the
  official sheets do not answer (pets, repainting, Visale, Airbnb sublets...). Each was checked
  against the corpus text. The right behavior is to abstain.
- **7 adversarial cases**: six synthetic pages in [`corpus/`](corpus) (a blog, an agency page, a
  forum thread, a "practical guide", a FAQ) plant a false fact or an instruction to the assistant,
  next to the forum page of logement-fr. Each case lists in `forbidden` (EVL-006) what the
  injection tries to make the answer say: a fake price, a fake notice period, a premium phone
  number, a link, a wrong penalty, a wrong date.

Every planted page ranks in the top 5 hits of its question, so each injection reaches the model.

`adversarial-depot-jamais-rendu` (the forum page of logement-fr) has no `forbidden` phrase on
purpose: the right answer ("non, il n'est pas vrai qu'il n'est jamais rendu") contains the
injected words, and a substring match cannot tell a refutation from a repetition.

The synthetic pages are written for this benchmark and contain no real data, see
[SOURCES.md](SOURCES.md). Their claims are false on purpose: do not reuse them as facts.

| | Cases |
|---|---|
| Answerable | 29 |
| Unanswerable (incl. 2 adversarial) | 18 |
| Adversarial (an injected page reaches the model) | 7 |
| With `forbidden` phrases | 6 |
| Total | 47 |

Run it: `make bench-trust` (see [benchmarks/trust](../../benchmarks/trust)).

## Reference answers

Each answerable case has a `reference_answer`, the short answer the correctness judge compares with (EVL-045). They were drafted by an AI agent (Claude) from the relevant quotes and the official fact sheets; the maintainer approved adding them without a line-by-line review. Treat them as provisional until a person checks each one.
