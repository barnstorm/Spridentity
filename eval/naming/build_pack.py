"""Build the pack an outside judge needs: numbered sprite pages and a table of candidate names.

usage: python eval/naming/build_pack.py

Reads   eval/naming/methods.json            which names each method gave every asset
        examples/<sheet>/assets/*.png       the sprites, as cut by spridentity
Writes  eval/naming/pages/<sheet>_<n>.png   the sprites, enlarged, each under its id
        eval/naming/names.csv               sheet, id, size, and the names under letters A-D
        eval/naming/verdicts_template.csv   the table the judge fills in

The letters hide which method produced which name; key.json says which is which.
Do not give key.json or verdicts_claude.csv to the judge.
"""
import csv
import json
from pathlib import Path

from PIL import Image, ImageDraw

here = Path(__file__).parent
root = here.parent.parent
key = json.loads((here / "key.json").read_text(encoding="utf-8"))  # letter -> method
methods = json.loads((here / "methods.json").read_text(encoding="utf-8"))  # sheet -> id -> method -> name
letters = sorted(key)
COLS, ROWS, CW, CH = 6, 8, 170, 150
(here / "pages").mkdir(exist_ok=True)

rows = []
for sheet, assets in methods.items():
    files = {p.name[:5]: p for p in (root / "examples" / sheet / "assets").glob("*.png")}
    ids = sorted(assets)
    for page in range(0, len(ids), COLS * ROWS):
        part = ids[page:page + COLS * ROWS]
        img = Image.new("RGB", (COLS * CW, -(-len(part) // COLS) * CH), (255, 255, 255))
        d = ImageDraw.Draw(img)
        for n, aid in enumerate(part):
            x, y = n % COLS * CW, n // COLS * CH
            im = Image.open(files[aid]).convert("RGBA")
            k = max(1, min(120 // im.width, 120 // im.height))
            im = im.resize((im.width * k, im.height * k), Image.NEAREST)
            im.thumbnail((120, 120), Image.NEAREST)
            back = Image.new("RGBA", im.size, (196, 212, 240, 255))  # pale blue = transparent
            back.alpha_composite(im)
            img.paste(back.convert("RGB"), (x + (CW - im.width) // 2, y + 18))
            d.text((x + 6, y + 3), aid, fill=(0, 0, 0))
            d.rectangle([x, y, x + CW - 1, y + CH - 1], outline=(215, 215, 215))
        name = f"{sheet}_{page // (COLS * ROWS) + 1}.png"
        img.save(here / "pages" / name)
        for aid in part:
            w, h = Image.open(files[aid]).size
            rows.append([sheet, aid, name, f"{w}x{h}"] + [assets[aid][key[L]] for L in letters])

with open(here / "names.csv", "w", newline="", encoding="utf-8") as f:
    wr = csv.writer(f)
    wr.writerow(["sheet", "id", "page", "size"] + letters)
    wr.writerows(rows)
with open(here / "verdicts_template.csv", "w", newline="", encoding="utf-8") as f:
    wr = csv.writer(f)
    wr.writerow(["sheet", "id", "what_it_is"] + letters)
    wr.writerows([r[0], r[1], ""] + [""] * len(letters) for r in rows)
print(len(rows), "assets,", len(list((here / "pages").glob("*.png"))), "pages")
