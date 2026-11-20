# -*- coding: utf-8 -*-
"""기상청 ASOS 일자료(공공데이터포털)를 station_map.csv의 관측소별로 받아 data/weather/asos_daily.csv 로 저장.
MINWON_KEYS(같은 계정 키) 중 첫 번째로 되는 키를 쓴다. 연도별로 1번씩 호출."""
import csv, datetime as dt, json, os, time, urllib.parse, urllib.request
from fetch import load_keys, ROOT
URL = "https://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList"
OUT = os.path.join(ROOT, "data", "weather", "asos_daily.csv")
LOG = os.path.join(ROOT, "data", "weather", "log.txt")
YEARS = list(range(2016, dt.date.today().year + 1))
COLS = ["stnId", "stnNm", "tm", "avgTa", "minTa", "maxTa", "sumRn", "maxWs", "avgWs", "avgRhm", "sumSsHr"]

def log(m):
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + m
    print(line, flush=True)
    open(LOG, "a", encoding="utf-8").write(line + "\n")

def get(key, stn, y):
    end = min(dt.date(y, 12, 31), dt.date.today() - dt.timedelta(days=1))
    p = {"serviceKey": key, "pageNo": 1, "numOfRows": 400, "dataType": "JSON", "dataCd": "ASOS",
         "dateCd": "DAY", "startDt": f"{y}0101", "endDt": end.strftime("%Y%m%d"), "stnIds": stn}
    with urllib.request.urlopen(URL + "?" + urllib.parse.urlencode(p), timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")

def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    keys = load_keys()
    stns = sorted({r["지점번호"] for r in csv.DictReader(open(os.path.join(ROOT, "station_map.csv"), encoding="utf-8")) if r["지점번호"]}, key=int)
    have = {}
    if os.path.exists(OUT):
        for r in csv.DictReader(open(OUT, encoding="utf-8-sig")):
            have.setdefault((r["stnId"], r["tm"][:4]), 0)
            have[(r["stnId"], r["tm"][:4])] += 1
    rows, ki = [], 0
    this_year = str(dt.date.today().year)
    for s in stns:
        for y in YEARS:
            if have.get((s, str(y)), 0) >= 365 and str(y) != this_year:
                continue
            for attempt in range(3):
                try:
                    text = get(keys[ki], s, y)
                    data = json.loads(text)
                    hdr = data["response"]["header"]
                    if hdr["resultCode"] != "00":
                        log(f"{s} {y}: {hdr}")
                        if hdr["resultCode"] in ("30", "31", "32", "33") and ki + 1 < len(keys):
                            ki += 1
                            continue
                        break
                    items = data["response"]["body"]["items"]["item"]
                    rows += [[it.get(c, "") for c in COLS] for it in items]
                    log(f"{s} {items[0].get('stnNm','')} {y}: {len(items)}일")
                    break
                except Exception as e:
                    log(f"{s} {y}: 실패 {type(e).__name__} {str(e)[:80]} {text[:120] if 'text' in dir() else ''}")
                    time.sleep(3)
            time.sleep(0.4)
    # 기존 + 새 자료 합치기 (같은 지점·날짜는 새 값으로)
    merged = {}
    if os.path.exists(OUT):
        for r in csv.DictReader(open(OUT, encoding="utf-8-sig")):
            merged[(r["stnId"], r["tm"])] = [r[c] for c in COLS]
    for r in rows:
        merged[(str(r[0]), r[2])] = r
    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f); w.writerow(COLS)
        for k in sorted(merged, key=lambda k: (int(k[0]), k[1])):
            w.writerow(merged[k])
    log(f"끝. {len(merged)}행 저장")

if __name__ == "__main__":
    main()
