# Competition Data

## `public_set.jsonl`

Contains 200 labeled development sessions: 80 Buying, 80 Browsing, 30 Intent Override, and 10 Boundary sessions.

Each session contains a safe aggregate `user_profile` and public labels for local development. Direct user identifiers, timestamps, free-text reviews, raw purchase history, hidden intent cards, and simulator-policy internals are not shipped in this participant file.

## `catalog.jsonl`

Obtain `catalog.jsonl.gz` from the organizer participant-kit release and decompress it as `catalog.jsonl` in this directory. Expected row count: 50,000. The file is intentionally ignored and is not part of the public project repository.

Expected SHA-256:

```text
da979b05a68af864cb0dcf9ee6a81c010c7e66a57978ad286c7a2e005fc69a67
```

## `public_smoke.jsonl`

Contains eight stratified public sessions for fast execution checks. It does not replace the full public evaluation.

## `catalog_sample_100.jsonl`

Contains a small text/metadata catalog fixture used by the local browser demo and startup self-check. Scores produced on this fixture are not headline evaluation results.

## `sample_smoke.jsonl`

Contains four project-authored synthetic sessions whose targets are present in
`catalog_sample_100.jsonl`. It verifies execution only and is not an official
evaluation set.

Never place API keys, private evaluation data, or participant outputs in this directory.
