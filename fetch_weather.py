# -*- coding: utf-8 -*-
"""기상청 API허브 지상관측 일자료(kma_sfcdd.php)를 날짜별로 받는다.
stn=0 이면 하루 한 번 호출로 전국 모든 관측소가 나온다.
- 환경변수 KMA_KEY : API허브 인증키 (GitHub 비밀값)
- 원본 줄은 data/weather/kma_raw/YYYY.txt 에 쌓고, 받은 날짜는 done.txt 에 기록 (이어받기)
- 첫 실행에서 help=1 결과를 data/weather/kma_help.txt 에 저장 (열 이름 확인용)
인증키는 출력·저장하지 않는다."""
import datetime as dt, os, sys, time, urllib.error, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
W = os.path.join(ROOT, "data", "weather")
RAW = os.path.join(W, "kma_raw")
DONE = os.path.join(W, "done.txt")
LOG = os.path.join(W, "log.txt")
URL = "https://apihub.kma.go.kr/api/typ01/url/kma_sfcdd.php"
START = dt.date(2016, 1, 1)
MAX_CALLS = int(os.environ.get("MAX_CALLS", "4500"))


def log(m):
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + m
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def get(key, day, help_=False):
    p = {"tm": day.strftime("%Y%m%d"), "stn": "0", "authKey": key}
    if help_:
        p["help"] = "1"
    try:
        with urllib.request.urlopen(URL + "?" + urllib.parse.urlencode(p), timeout=60) as r:
            b = r.read()
    except urllib.error.HTTPError as e:
        body = e.read()[:400].decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body!r}")
    for enc in ("utf-8", "euc-kr"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            pass
    return b.decode("utf-8", errors="replace")


def main():
    key = os.environ.get("KMA_KEY", "").strip()
    if not key:
        sys.exit("KMA_KEY 비밀값이 비어 있습니다.")
    os.makedirs(RAW, exist_ok=True)
    helpf = os.path.join(W, "kma_help.txt")
    if not os.path.exists(helpf):
        try:
            t = get(key, dt.date(2024, 9, 1), help_=True)
            open(helpf, "w", encoding="utf-8").write(t)
            log(f"help 저장 ({len(t)}글자)")
        except Exception as e:
            log(f"help 실패: {e}")
            sys.exit(1)
    done = set(open(DONE, encoding="utf-8").read().split()) if os.path.exists(DONE) else set()
    yday = dt.date.today() - dt.timedelta(days=1)
    day, calls, saved = START, 0, 0
    while day <= yday and calls < MAX_CALLS:
        s = day.strftime("%Y%m%d")
        if s in done:
            day += dt.timedelta(days=1)
            continue
        try:
            t = get(key, day)
            calls += 1
        except Exception as e:
            log(f"{s}: 실패 {type(e).__name__} {str(e)[:100]}")
            calls += 1
            time.sleep(5)
            day += dt.timedelta(days=1)
            continue
        lines = [l for l in t.splitlines() if l.strip() and not l.startswith("#")]
        if not lines:
            log(f"{s}: 자료 없음 -> {t[:200]!r}")
            if "인증" in t or "auth" in t.lower() or "key" in t.lower():
                sys.exit("인증키 문제로 멈춤")
        else:
            with open(os.path.join(RAW, f"{day.year}.txt"), "a", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            with open(DONE, "a", encoding="utf-8") as f:
                f.write(s + "\n")
            saved += 1
            if saved % 100 == 1:
                log(f"{s}: {len(lines)}개 관측소")
        time.sleep(0.15)
        day += dt.timedelta(days=1)
    log(f"끝. 이번에 {saved}일 저장, 호출 {calls}번")


if __name__ == "__main__":
    main()
