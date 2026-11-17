# -*- coding: utf-8 -*-
"""data/raw/*.json 을 모아 data/민원_은행열매_일별.csv 하나로 만든다 (엑셀에서 바로 열림)."""
import csv, json, os
from fetch import load_regions, safe, code_for, RAW, ROOT

out = os.path.join(ROOT, "data", "민원_은행열매_일별.csv")
rows = []
for r in load_regions():
    for f in sorted(os.listdir(RAW)) if os.path.isdir(RAW) else []:
        if not f.startswith(safe(r["지역"]) + "_") or not f.endswith(".json"):
            continue
        year = f[:-5].rsplit("_", 1)[1]
        if not year.isdigit():
            continue
        with open(os.path.join(RAW, f), encoding="utf-8") as fp:
            data = json.load(fp)
        for d in data:
            lab = str(d.get("label", ""))
            rows.append([r["그룹"], r["지역"], code_for(r, int(year)), year,
                         f"{lab[:4]}-{lab[4:6]}-{lab[6:8]}", d.get("hits", 0)])
with open(out, "w", encoding="utf-8-sig", newline="") as fp:
    w = csv.writer(fp)
    w.writerow(["그룹", "지역", "기관코드", "연도", "날짜", "건수"])
    w.writerows(rows)
print(f"{out}: {len(rows)}행")
