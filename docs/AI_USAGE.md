# AI usage disclosure

Prompts: `prompts/PROMPT_LOG.md`. `make check` fails until every `TODO(candidate)` below is replaced with your own truthful text.

## Tools used
- Claude (claude.ai) - used for a final review of the repository against the YottaFlex submission guidelines and for packaging fixes (Makefile, `.gitignore`, `requirements.txt`, submission self-check script, removal of unused Docker/Postgres files, README sections 14-15, "How I know it works" in the design note).
- TODO(candidate): list every other AI tool + model you used while building the pipeline, and what for.

## Where AI accelerated my work
- TODO(candidate): e.g. first draft of module layout, test scaffolding, README tables - only what is true.

## Where I relied heavily on AI
- TODO(candidate): be specific and honest (e.g. the synthetic data generator, benchmark script, SQL samples).

## What I personally reviewed, changed and validated
- Ran the full test suite and `make demo` from a fresh clone in a clean virtual environment.
- TODO(candidate): one real bug you found and how you fixed it.
- TODO(candidate): one design decision you made or changed against an AI suggestion, and why.
- TODO(candidate): something you verified by hand (e.g. compared quarantine rows with the source file lines).

## What I can explain without AI help
Flow `validation -> loader -> ingest -> replay -> reconcile`: version-aware idempotent upsert on `(order_id, updated_at)`, one transaction per file, immutable quarantine payload plus separate replay audit columns.

## Limits of my understanding
- TODO(candidate): anything you are less sure about (be honest; reviewers value it).
