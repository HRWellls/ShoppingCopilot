from __future__ import annotations

import argparse
import json
import os
import random
import tempfile
from pathlib import Path


def sample_catalog(
    source: Path,
    output: Path,
    sample_size: int,
    seed: int,
    *,
    overwrite: bool = False,
) -> int:
    if sample_size <= 0:
        raise ValueError("N must be greater than zero")
    if source.resolve() == output.resolve():
        raise ValueError("output must be different from source")
    if output.exists() and not overwrite:
        raise FileExistsError(f"output already exists: {output} (use --force to overwrite)")

    with source.open(encoding="utf-8") as handle:
        row_count = sum(1 for line in handle if line.strip())
    if sample_size > row_count:
        raise ValueError(f"N ({sample_size}) exceeds the catalog row count ({row_count})")

    selected_indices = set(random.Random(seed).sample(range(row_count), sample_size))
    output.parent.mkdir(parents=True, exist_ok=True)

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            row_index = 0
            with source.open(encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if not line.strip():
                        continue
                    if row_index in selected_indices:
                        try:
                            json.loads(line)
                        except json.JSONDecodeError as exc:
                            raise ValueError(f"invalid JSON on source line {line_number}: {exc.msg}") from exc
                        temporary.write(line if line.endswith("\n") else line + "\n")
                    row_index += 1
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, output)
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise

    return row_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Randomly sample N products from a JSONL catalog")
    parser.add_argument("n", type=int, help="number of catalog rows to sample")
    parser.add_argument("--source", type=Path, default=Path("data/catalog.jsonl"))
    parser.add_argument(
        "--output",
        type=Path,
        help="output path (default: data/catalog_sample_N.jsonl)",
    )
    parser.add_argument("--seed", type=int, default=42, help="random seed (default: 42)")
    parser.add_argument("--force", action="store_true", help="overwrite an existing output file")
    args = parser.parse_args()

    output = args.output or args.source.with_name(
        f"{args.source.stem}_sample_{args.n}{args.source.suffix}"
    )
    try:
        row_count = sample_catalog(args.source, output, args.n, args.seed, overwrite=args.force)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    print(
        json.dumps(
            {
                "source": str(args.source),
                "source_rows": row_count,
                "output": str(output),
                "sample_rows": args.n,
                "seed": args.seed,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
