#!/usr/bin/env bash

set -euo pipefail

timestamp="$(date '+%-m%d_%H%M')"
output_dir="runresult/${timestamp}"
mkdir -p "$output_dir"

python3 -m scripts.run_public_set_local \
    --profile d4 \
    --dataset data/public_set.jsonl \
    --output "${output_dir}/test-public.json"

python3 -m scripts.run_public_set_local \
    --profile d4 \
    --dataset data/owntest.jsonl \
    --output "${output_dir}/test-own.json"

python3 -m scripts.run_public_set_local \
    --profile d4 \
    --dataset data/owntest2.jsonl \
    --output "${output_dir}/test-own2.json"
