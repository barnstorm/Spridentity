"""Score a judge's verdicts, and compare two judges.

usage: python eval/naming/score.py VERDICTS.csv [OTHER_VERDICTS.csv]

A verdicts file has the columns  sheet, id, what_it_is, then one column per letter in key.json.
Each lettered cell is yes, partial or no. Put "unclear" in what_it_is (and leave the
letters empty) when the sprite cannot be identified, is a fragment, or is several
things merged; those rows are left out of the scores. Rows left blank are not counted.
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

here = Path(__file__).parent
key = json.loads((here / "key.json").read_text(encoding="utf-8"))
letters = sorted(key)
VAL = {"yes": 1.0, "y": 1.0, "1": 1.0, "partial": 0.5, "p": 0.5, "0.5": 0.5, "no": 0.0, "n": 0.0, "0": 0.0}


def load(path):
    out = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            what = (r.get("what_it_is") or "").strip().lower()
            cells = [(r.get(L) or "").strip().lower() for L in letters]
            if what.startswith("unclear") or not all(c in VAL for c in cells):
                continue
            out[(r["sheet"].strip(), r["id"].strip())] = [VAL[c] for c in cells]
    return out


def table(v, title):
    per = defaultdict(lambda: [0, [0.0] * len(letters), [0] * len(letters), 0])
    for (sheet, _), vals in v.items():
        for k in (sheet, "TOTAL"):
            p = per[k]
            p[0] += 1
            p[3] += any(x == 1.0 for x in vals)
            for i, x in enumerate(vals):
                p[1][i] += x
                p[2][i] += x == 1.0
    print(f"\n{title}: strict = yes only; lenient = partial counts half")
    print(f"{'sheet':<12}{'judged':>7}" + "".join(f"{key[L]:>22}" for L in letters) + f"{'any right':>11}")
    for k in sorted(per, key=lambda s: (s == "TOTAL", s)):
        n, soft, hard, anyr = per[k]
        print(f"{k:<12}{n:>7}" + "".join(f"{hard[i]:>12} ({soft[i]:>5.1f})  " for i in range(len(letters)))
              + f"{anyr:>9}")
    n, soft, hard, anyr = per["TOTAL"]
    if n:
        print(f"{'share':<12}{'':>7}" + "".join(f"{hard[i] / n:>12.0%} ({soft[i] / n:>5.0%})  "
                                                 for i in range(len(letters))) + f"{anyr / n:>9.0%}")


a = load(sys.argv[1])
table(a, Path(sys.argv[1]).name)
if len(sys.argv) > 2:
    b = load(sys.argv[2])
    table(b, Path(sys.argv[2]).name)
    both = sorted(set(a) & set(b))
    print(f"\nagreement on the {len(both)} assets both judged (same yes / not-yes call):")
    for i, L in enumerate(letters):
        same = sum((a[k][i] == 1.0) == (b[k][i] == 1.0) for k in both)
        print(f"  {key[L]:<24}{same}/{len(both)}" + (f"  ({same / len(both):.0%})" if both else ""))
    only_a, only_b = len(set(a) - set(b)), len(set(b) - set(a))
    print(f"  judged by only the first: {only_a}; by only the second: {only_b}")
