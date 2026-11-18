# -*- coding: utf-8 -*-
"""
국민권익위원회 민원빅데이터 API_2022 - 키워드 트렌드(일별)로
지역별 '은행 열매' 민원 건수를 받는다. GitHub Actions에서 실행.

환경변수
  MINWON_KEYS : 인증키(Decoding). 여러 개면 줄바꿈이나 쉼표로 구분.
  MODE        : test 또는 run (기본 run)
  MAX_MINUTES : 이번 실행에서 쓸 최대 시간(분). 기본 300
  CALLS_PER_KEY : 이번 실행에서 키 하나당 최대 호출 수. 기본 48

규칙
  - 같은 키는 호출 사이 310초 이상 쉰다 (연속 호출 제한 회피).
  - 키가 여러 개면 번갈아 쓴다.
  - 결과는 data/raw/<지역>_<연도>.json 에 저장, 이미 있으면 건너뜀.
  - 인증키는 어디에도 출력·저장하지 않는다.
"""
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, "data", "raw")
LOG = os.path.join(ROOT, "data", "log.txt")
URL = "https://apis.data.go.kr/1140100/minAnalsInfoView5/minTimeSeriseView5"

KEYWORD = "은행 열매"
YEARS = [2024, 2023, 2025, 2022, 2021]
GAP = 310  # 같은 키 호출 간격(초)

MODE = os.environ.get("MODE", "run").strip() or "run"
MAX_MIN = float(os.environ.get("MAX_MINUTES", "300"))
CALLS_PER_KEY = int(os.environ.get("CALLS_PER_KEY", "48"))


def log(msg):
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + msg
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_keys():
    raw = os.environ.get("MINWON_KEYS", "")
    keys = []
    for part in re.split(r"[\n,;]+", raw):
        part = part.strip().strip('"').strip("'")
        if "=" in part and not part.endswith("="):
            part = part.split("=", 1)[1].strip()
        if "%" in part:
            part = urllib.parse.unquote(part)
        if part and part not in keys:
            keys.append(part)
    if not keys:
        sys.exit("MINWON_KEYS 비밀값이 비어 있습니다.")
    return keys


def load_regions():
    rows = []
    with open(os.path.join(ROOT, "regions.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def code_for(region, year):
    old, start = region.get("옛코드", ""), region.get("새코드시작연도", "")
    if old and start and year < int(start):
        return old
    return region["코드"]


def safe(name):
    return re.sub(r"[^\w가-힣]+", "_", name).strip("_")


def call(key, year, code, d0="0815000000", d1="1130235959"):
    params = {
        "serviceKey": key,
        "period": "DAILY",
        "sortBy": "NAME",
        "sortOrder": "true",
        "target": "pttn,saeol,dfpt",
        "dateFrom": f"{year}{d0}",
        "dateTo": f"{year}{d1}",
        "searchword": KEYWORD,
        "dataType": "json",
    }
    if code:
        params["mainSubCode"] = code
    url = URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")[:500]


def classify(text):
    t = text[:600]
    if "연속" in t or "잠시 제한" in t:
        return "throttle"
    if "LIMITED_NUMBER" in t:
        return "daily_limit"
    if "NOT_REGISTERED" in t or "ACCESS_DENIED" in t or "SERVICE_KEY" in t:
        return "key_error"
    if t.lstrip().startswith("["):
        return "ok"
    if "ERROR" in t or '"code":500' in t.replace(" ", ""):
        return "error"
    return "unknown"


def jobs(regions):
    if MODE == "test" and os.environ.get("TEST_PICKS", "").strip():
        want = {}
        for it in os.environ["TEST_PICKS"].split(","):
            if ":" in it:
                n, y = it.rsplit(":", 1)
                want.setdefault(n.strip(), []).append(int(y))
        return [(r, y) for r in regions for y in want.get(r["지역"], [])]
    if MODE == "test":
        pick = {"전국": 2024, "서울 동대문구": 2024, "수원 장안구": 2024, "춘천시": 2022,
                "고양 일산서구": 2024, "광주 북구": 2024}  # 키 6개를 한 번씩 쓰도록 6개
        return [(r, pick[r["지역"]]) for r in regions if r["지역"] in pick]
    out = []
    for r in regions:
        for y in YEARS:
            start = r.get("새코드시작연도", "")
            if start and not r.get("옛코드") and y < int(start):
                continue  # 그해에는 없던 기관 (예: 2024년에 다시 생긴 부천 구)
            out.append((r, y))
    return out



PARTS_DIR = os.path.join(ROOT, "data", "parts")
SLOW_DIR = os.path.join(ROOT, "data", "timeout")
SLOW_YEARS = {2022, 2023}  # 서버 시간 초과가 몰린 연도: 처음부터 조각으로 받음
# 조각 기간 (낙과 시작을 보는 데 필요한 8/15~10/31만, 15일 단위)
CHUNKS = [("0815000000", "0831235959"), ("0901000000", "0915235959"), ("0916000000", "0930235959"),
          ("1001000000", "1015235959"), ("1016000000", "1031235959")]


def part_path(r, y, d0):
    return os.path.join(PARTS_DIR, f"{safe(r['지역'])}_{y}_{d0[:4]}.json")


def slow_mark(r, y):
    return os.path.join(SLOW_DIR, f"{safe(r['지역'])}_{y}")


def build_units(regions):
    units = []  # (r, y, d0, d1, out, is_part)
    for r, y in jobs(regions):
        out = os.path.join(RAW, f"{safe(r['지역'])}_{y}.json")
        nod = out.replace(os.sep + "raw" + os.sep, os.sep + "nodata" + os.sep)
        if MODE != "test" and (os.path.exists(out) or os.path.exists(nod)):
            continue
        if MODE != "test" and (y in SLOW_YEARS or os.path.exists(slow_mark(r, y))):
            for d0, d1 in CHUNKS:
                pp = part_path(r, y, d0)
                if not os.path.exists(pp):
                    units.append((r, y, d0, d1, pp, True))
        else:
            units.append((r, y, "0815000000", "1130235959", out, False))
    return units


def merge_parts(regions):
    n = 0
    for r, y in jobs(regions):
        out = os.path.join(RAW, f"{safe(r['지역'])}_{y}.json")
        nod = out.replace(os.sep + "raw" + os.sep, os.sep + "nodata" + os.sep)
        if os.path.exists(out) or os.path.exists(nod):
            continue
        pps = [part_path(r, y, d0) for d0, _ in CHUNKS]
        if not all(os.path.exists(p) for p in pps):
            continue
        merged = []
        for p in pps:
            with open(p, encoding="utf-8") as f:
                merged += json.load(f)
        target = out if merged else nod
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False)
        n += 1
    if n:
        log(f"조각을 합쳐 완성한 지역·연도: {n}개")


def main():
    for d in (RAW, PARTS_DIR, SLOW_DIR):
        os.makedirs(d, exist_ok=True)
    keys = load_keys()
    regions = load_regions()
    merge_parts(regions)
    units = build_units(regions)
    log(f"모드={MODE} 키={len(keys)}개 남은호출단위={len(units)}개")

    last_used = [0.0] * len(keys)
    used = [0] * len(keys)
    dead = [False] * len(keys)
    start = time.time()
    i = 0
    while i < len(units):
        if (time.time() - start) / 60 > MAX_MIN:
            log("시간 한도 도달. 다음 실행에서 이어서 받습니다.")
            break
        alive = [k for k in range(len(keys)) if not dead[k] and used[k] < CALLS_PER_KEY]
        if not alive:
            log("이번 실행에서 쓸 수 있는 키 호출을 모두 썼습니다.")
            break
        k = min(alive, key=lambda x: last_used[x])
        wait = GAP - (time.time() - last_used[k])
        if wait > 0:
            time.sleep(wait)
        r, y, d0, d1, out, is_part = units[i]
        code = code_for(r, y)
        last_used[k] = time.time()
        used[k] += 1
        tag = f"[{r['지역']} {y} {d0[:4]}~{d1[:4]} 코드={code or '-'} 키#{k+1}]"
        try:
            status, text = call(keys[k], y, code, d0, d1)
        except Exception as e:
            log(f"{tag} 접속 실패: {type(e).__name__} {e}")
            i += 1
            continue
        kind = classify(text)
        if kind == "ok":
            data = json.loads(text)
            total = sum(int(d.get("hits", 0) or 0) for d in data)
            if not data and not is_part:
                nod = out.replace(os.sep + "raw" + os.sep, os.sep + "nodata" + os.sep)
                os.makedirs(os.path.dirname(nod), exist_ok=True)
                open(nod, "w", encoding="utf-8").write("[]")
                log(f"{tag} 민원 0건(빈 목록)")
            else:
                with open(out, "w", encoding="utf-8") as f:
                    f.write(text)
                log(f"{tag} 저장: {len(data)}일, 합계 {total}건")
            i += 1
        elif kind == "throttle":
            log(f"{tag} 연속 호출 제한. 이 키는 잠시 쉼.")
        elif kind == "daily_limit":
            dead[k] = True
            log(f"{tag} 이 키의 오늘 한도 소진.")
        elif kind == "key_error":
            dead[k] = True
            log(f"{tag} 키 오류(등록 안 됨/권한 없음): {text[:120]!r}")
        elif status == 504 or "TIMEOUT" in text[:300]:
            if not is_part:
                open(slow_mark(r, y), "w").write("")
                for c0, c1 in CHUNKS:  # 이번 실행 뒤쪽에 조각 단위로 추가
                    units.append((r, y, c0, c1, part_path(r, y, c0), True))
                log(f"{tag} 서버 시간 초과 -> 15일 조각으로 다시 받음")
            else:
                log(f"{tag} 조각도 시간 초과. 다음 실행에서 다시 시도")
            i += 1
        else:
            log(f"{tag} 오류 응답(HTTP {status}): {text[:200]!r}")
            i += 1
    merge_parts(regions)
    allj = jobs(regions)
    done = sum(os.path.exists(os.path.join(RAW, f"{safe(r['지역'])}_{y}.json")) for r, y in allj)
    nd = sum(os.path.exists(os.path.join(ROOT, "data", "nodata", f"{safe(r['지역'])}_{y}.json")) for r, y in allj)
    log(f"이번 실행 끝. 완료 {done + nd}개(민원 있음 {done}, 0건 {nd}) / 전체 {len(allj)}개")


if __name__ == "__main__":
    main()
