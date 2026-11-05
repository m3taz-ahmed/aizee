# Resources — vendored rubrics & reviewer personas

Apache-2.0 content ported from [`google/elephant-goldfish-model`](https://github.com/google/elephant-goldfish-model) (EGM). License: `LICENSE-EGM`.

| Path | Content |
|------|---------|
| `document_standards/` | 5 versioned review rubrics (zoom-out, feature-spec, implementation-readiness, heilmeier, re-implementation) |
| `goldfish_personas/` | 10 zero-context reviewer personas spawned by the Goldfish review protocol |
| `execution_instructions.md` | Mandatory gates: design-only scope, one-question-per-turn, contradiction audit, artifact-first |

Consumed by `workflows/65-goldfish-review.md` and `runtime/spec/review.py` (`aizee spec review`). Do not edit vendored files casually — track upstream; local adaptations go in wrappers, not in these files.
