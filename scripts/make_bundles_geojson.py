"""묶음별 중심점 GeoJSON 생성: data/base/동대문구_가로수_묶음.csv -> screen/trees_bundles.geojson"""
import json, sys
import pandas as pd

src = sys.argv[1] if len(sys.argv) > 1 else "data/base/동대문구_가로수_묶음.csv"
dst = sys.argv[2] if len(sys.argv) > 2 else "screen/trees_bundles.geojson"
d = pd.read_csv(src, encoding="utf-8-sig")
feats = []
for bid, g in d.groupby("묶음id"):
    sp = g["수종"].mode().iloc[0]
    feats.append({
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [round(g["좌표(경도)"].mean(), 7), round(g["좌표(위도)"].mean(), 7)]},
        "properties": {
            "묶음id": int(bid),
            "노선": g["노선"].mode().iloc[0],
            "수종": sp,
            "그루수": int(len(g)),
            "은행_암": int((g["수종"] == "은행나무 암나무").sum()),
            "은행_미상": int((g["수종"] == "은행나무").sum()),
        },
    })
feats.sort(key=lambda f: f["properties"]["묶음id"])
with open(dst, "w", encoding="utf-8") as f:
    json.dump({"type": "FeatureCollection", "features": feats}, f, ensure_ascii=False, separators=(",", ":"))
print(len(feats), "묶음 ->", dst)
