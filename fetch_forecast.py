# -*- coding: utf-8 -*-
"""기상청 API허브 단기예보(오늘~3일)·중기예보(4~10일)를 받아 data/forecast/YYYYMMDD/ 에 원본 JSON으로 저장.
- 환경변수 KMA_KEY : API허브 인증키 (GitHub 비밀값, weather.yml과 같은 키). 키는 출력·저장하지 않는다.
- 단기: getVilageFcst, 05시 발표, 동대문구 묶음이 걸친 격자 3곳 (scripts/kma_grid.py로 계산)
- 중기: getMidTa(서울 기온, 11B10101), getMidLandFcst(서울·인천·경기 육상, 11B00000), 06시 발표
한국시간 06:40 이후에 돌린다(weather.yml 처럼 Actions에서)."""
import datetime as dt, json, os, sys, time, urllib.error, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "data", "forecast")
BASE = "https://apihub.kma.go.kr/api/typ02/openApi"
GRIDS = [(61, 127), (61, 128), (62, 127)]
MID_TA_REG, MID_LAND_REG = "11B10101", "11B00000"


def log(m):
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + m
    print(line, flush=True)
    with open(os.path.join(OUT, "log.txt"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def call(path, params, key):
    q = dict(params, pageNo=1, numOfRows=1000, dataType="JSON", authKey=key)
    try:
        with urllib.request.urlopen(f"{BASE}/{path}?" + urllib.parse.urlencode(q), timeout=60) as r:
            b = r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read()[:300].decode('utf-8', errors='replace')!r}")
    try:
        j = json.loads(b)
    except ValueError:
        raise RuntimeError(f"JSON 아님: {b[:300]!r}")
    code = j.get("response", {}).get("header", {}).get("resultCode")
    if code != "00":
        raise RuntimeError(f"resultCode {code}: {j.get('response', {}).get('header')}")
    return j


def main():
    key = os.environ.get("KMA_KEY", "").strip()
    if not key:
        sys.exit("KMA_KEY 비밀값이 비어 있습니다.")
    os.makedirs(OUT, exist_ok=True)
    now = dt.datetime.utcnow() + dt.timedelta(hours=9)
    day = now.strftime("%Y%m%d")
    d = os.path.join(OUT, day); os.makedirs(d, exist_ok=True)
    jobs = [(f"vilage_{nx}_{ny}.json", "VilageFcstInfoService_2.0/getVilageFcst",
             dict(base_date=day, base_time="0500", nx=nx, ny=ny)) for nx, ny in GRIDS]
    jobs += [("midta.json", "MidFcstInfoService/getMidTa", dict(regId=MID_TA_REG, tmFc=day + "0600")),
             ("midland.json", "MidFcstInfoService/getMidLandFcst", dict(regId=MID_LAND_REG, tmFc=day + "0600"))]
    fail = 0
    for name, path, p in jobs:
        try:
            j = call(path, p, key)
            json.dump(j, open(os.path.join(d, name), "w", encoding="utf-8"), ensure_ascii=False)
            n = len(j["response"]["body"]["items"]["item"])
            log(f"{day} {name}: {n}개 항목")
        except Exception as e:
            fail += 1
            log(f"{day} {name}: 실패 {str(e)[:200]}")
        time.sleep(1)
    if fail == len(jobs):
        sys.exit("전부 실패 — 인증키 권한(단기·중기 예보 활용신청)이나 주소를 확인")


if __name__ == "__main__":
    main()
