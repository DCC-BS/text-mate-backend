"""Build a blinded A/B comparison set from two ``--texts-out`` directories.

The ZIX number answers "is the result easier to read". It cannot answer "is this a text a
Basel-Stadt department could send out": whether the register is right, whether a legal
qualifier survived, whether the result reads like German or like a rule-compliance
exercise. That question needs a reader, and a reader who knows which system produced
which text is not a reader, it is a confirmation.

So this writes, per case, a directory holding ``original.txt``, ``A.txt`` and ``B.txt``,
with the A/B assignment **drawn per case** from a seeded RNG. Per case, not per run: a
fixed assignment lets a judge who guesses the pattern on one case apply it to the rest,
and a judge who develops a position-bias ("A is usually the careful one") has that bias
land on one system throughout. The key mapping A/B back to the systems is written
*outside* the comparison tree, so the directory handed to a judge cannot be walked upwards
into the answer.

The seed is recorded in the key file: the assignment must be reproducible, or a
disagreement between two judges cannot be traced back to what each actually read.

Usage::

    python -m text_mate_tools.simplify_eval.build_blind_pairs \\
        --left  out/texts_main    --left-name  main_single_shot \\
        --right out/texts_loop    --right-name simplify \\
        --out   out/blind         --seed 20260815
"""

import argparse
import json
import random
from pathlib import Path

from text_mate_tools.simplify_eval.corpus import DEFAULT_CASES_DIR, load_cases

RUN_SUFFIX = ".run1.txt"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left", type=Path, required=True, help="texts-out directory of system 1")
    parser.add_argument("--right", type=Path, required=True, help="texts-out directory of system 2")
    parser.add_argument("--left-name", default="left")
    parser.add_argument("--right-name", default="right")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_DIR)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260815)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    args.out.mkdir(parents=True, exist_ok=True)

    key: dict[str, dict[str, str]] = {}
    for case in load_cases(args.cases, []):
        left_file = args.left / f"{case.id}{RUN_SUFFIX}"
        right_file = args.right / f"{case.id}{RUN_SUFFIX}"
        if not left_file.exists() or not right_file.exists():
            # A case only one side produced cannot be compared, and silently emitting it
            # with one empty side would read as "this system wrote nothing", which is a
            # verdict rather than a gap.
            print(f"  skipping {case.id}: missing output on one side")
            continue

        case_dir = args.out / case.id
        case_dir.mkdir(parents=True, exist_ok=True)
        (case_dir / "original.txt").write_text(case.source_text, encoding="utf-8")

        swap = rng.random() < 0.5
        a_source, b_source = (right_file, left_file) if swap else (left_file, right_file)
        a_name, b_name = (args.right_name, args.left_name) if swap else (args.left_name, args.right_name)
        (case_dir / "A.txt").write_text(a_source.read_text(encoding="utf-8"), encoding="utf-8")
        (case_dir / "B.txt").write_text(b_source.read_text(encoding="utf-8"), encoding="utf-8")
        key[case.id] = {"A": a_name, "B": b_name}

    key_file = args.out.parent / f"{args.out.name}_key.json"
    key_file.write_text(json.dumps({"seed": args.seed, "mapping": key}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(key)} case(s) written to {args.out}; key (NOT for judges) at {key_file}")


if __name__ == "__main__":
    main()
