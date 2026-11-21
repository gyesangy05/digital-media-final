# -*- coding: utf-8 -*-
"""묶음별 은행 낙과 예보 데이터 만들기 -> screen/forecast/forecast_YYYYMMDD.json
  python scripts/make_forecast.py --date 2026-11-21 --mode fcst      # 실제 운영: data/forecast/의 단기·중기 예보 사용
  python scripts/make_forecast.py --from 2026-09-01 --to 2026-11-20 --mode obs   # 시즌 재생(시뮬레이션): 7일은 실제 관측으로
먼저 python analysis/build.py 로 analysis/*.pkl 을 만들어 둔다.

날씨: 기준일 전날까지 = 관측(서울 ASOS 108), 기준일~+7일 = 예보(fcst) 또는 관측(obs), 그 뒤 = 평년값(2016~2025 같은 날짜 ±7일 평균)
단계(팀 결정 2026-11-21):
  본격   = 2단계 모델(민원 학습) 예측 곡선의 10%~90% 구간(80% 범위) — 민원·불편이 몰리는 시기
  시작   = 본격 시작 7일 전부터
  마무리 = 본격 끝 다음날부터 30일 — 바닥에 열매가 남는 기간. 30일은 2026 서울 시민과학 관측
           ('열매가 익어 떨어짐' 90% 시점 11/13)과 모델 90% 시점(10/14)의 차이로 정한 가정(1년치)
강도   = 본격 기간 안 일별 예측 낙과량 / 시즌 최대 (0~1), 요일·공휴일(신고 행동) 효과는 뺌
피하기 = 본격·마무리 때 암나무 묶음 '피하기', 성별 미상만 있는 묶음 '가능성'"""
import argparse, glob, json, os, re, sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kma_grid import to_grid
exec(open('analysis/two_stage.py', encoding='utf-8').read().split("cities=[c for c")[0])  # 모델 함수·자료 재사용

STN, D_POLL, FEAT = 108, 20, ['ripe', 'rain', 'wind', 'cold']
START_LEAD, TAIL = 7, 30
GUST_RATIO = 1.77  # 서울 ASOS 2016~2026: 최대순간풍속 / 최대풍속 중앙값 (예보 풍속 -> 순간풍속 환산)
OUT = 'screen/forecast'

# ---------- 모델 학습(2021~2025 민원, 8개 도시) ----------
_tr = table(D_POLL, ['서울', '대구', '부산', '대전', '광주', '인천', '수원시', '고양시'])
_cols = sorted(set(_tr.city + '_' + _tr.year.astype(str)))
MODEL = PoissonRegressor(alpha=1e-4, max_iter=3000).fit(X_of(_tr, FEAT, _cols), _tr.n)

# ---------- 날씨 ----------
OBS = pd.DataFrame({'ta': ta[STN], 'tmin': tmin[STN], 'rn': rn[STN], 'ws': ws[STN]})
_h = OBS[(OBS.index.year >= 2016) & (OBS.index.year <= 2025)]
_doy = _h.groupby(_h.index.dayofyear).mean()
CLIM = pd.concat([_doy.iloc[-7:], _doy, _doy.iloc[:7]]).rolling(15, center=True).mean().iloc[7:-7]
_wet = _h[_h.rn >= 0.1]; WET_MM = _wet.groupby(_wet.index.month).rn.mean()  # 비 오는 날 평균 강수량(월별)


def parse_pcp(s):
    s = str(s)
    if '없음' in s: return 0.0
    if '미만' in s: return 0.5
    nums = [float(x) for x in re.findall(r'[\d.]+', s)]
    return float(np.mean(nums)) if nums else 0.0


def load_fcst(day, grid=(61, 127)):
    """data/forecast/YYYYMMDD/ -> 날짜별 dict(ta, tmin, rn, ws)."""
    d = f"data/forecast/{day:%Y%m%d}"; out = {}
    p = f"{d}/vilage_{grid[0]}_{grid[1]}.json"
    if os.path.exists(p):
        it = pd.DataFrame(json.load(open(p, encoding='utf-8'))['response']['body']['items']['item'])
        for date, g in it.groupby('fcstDate'):
            v = lambda c: g[g.category == c].fcstValue
            tmp = pd.to_numeric(v('TMP'), errors='coerce')
            tmn, tmx = pd.to_numeric(v('TMN'), errors='coerce'), pd.to_numeric(v('TMX'), errors='coerce')
            wsd = pd.to_numeric(v('WSD'), errors='coerce')
            rec = {'ta': tmp.mean() if len(tmp) >= 20 else (tmn.mean() + tmx.mean()) / 2 if len(tmn) and len(tmx) else np.nan,
                   'tmin': tmn.mean() if len(tmn) else tmp.min(), 'rn': sum(parse_pcp(x) for x in v('PCP')),
                   'ws': wsd.max() * GUST_RATIO if len(wsd) else np.nan}
            out[pd.Timestamp(date)] = {k: x for k, x in rec.items() if pd.notna(x)}
    pt, pl = f"{d}/midta.json", f"{d}/midland.json"
    if os.path.exists(pt):
        t = json.load(open(pt, encoding='utf-8'))['response']['body']['items']['item'][0]
        l = json.load(open(pl, encoding='utf-8'))['response']['body']['items']['item'][0] if os.path.exists(pl) else {}
        for n in range(3, 11):
            date = pd.Timestamp(day) + pd.Timedelta(days=n)
            if date in out or f'taMin{n}' not in t: continue
            rec = {'ta': (float(t[f'taMin{n}']) + float(t[f'taMax{n}'])) / 2, 'tmin': float(t[f'taMin{n}'])}
            pop = [float(l[k]) for k in (f'rnSt{n}Am', f'rnSt{n}Pm', f'rnSt{n}') if k in l]
            if pop: rec['rn'] = WET_MM.get(date.month, 3.0) if max(pop) >= 60 else 0.0
            out[date] = rec
    return out


def weather(day, mode, grid=(61, 127)):
    """기준일 day에 '알 수 있었던' 날씨로 그해 1/1~12/31 일별 표를 만든다."""
    idx = pd.date_range(f'{day.year}-01-01', f'{day.year}-12-31')
    w = pd.DataFrame(index=idx, columns=['ta', 'tmin', 'rn', 'ws', '출처'], dtype=object)
    clim = CLIM.reindex(idx.dayofyear).set_index(idx)
    fc = load_fcst(day, grid) if mode == 'fcst' else {}
    for d in idx:
        src = clim.loc[d].to_dict(); tag = '평년값'
        if d < day:
            o = OBS.loc[d].to_dict() if d in OBS.index else {}
            src.update({k: x for k, x in o.items() if pd.notna(x)}); tag = '관측'
        elif d <= day + pd.Timedelta(days=7):
            if mode == 'obs' and d in OBS.index and pd.notna(OBS.loc[d, 'ta']):
                src.update({k: x for k, x in OBS.loc[d].to_dict().items() if pd.notna(x)}); tag = '관측(재생)'
            elif d in fc:
                src.update(fc[d]); tag = '예보'
        w.loc[d] = [src['ta'], src['tmin'], src['rn'], src['ws'], tag]
    for c in ['ta', 'tmin', 'rn', 'ws']: w[c] = w[c].astype(float)
    return w


# ---------- 낙과 곡선과 단계 ----------
def season(day, mode, grid=(61, 127)):
    w = weather(day, mode, grid); y = day.year
    if y in obs_cherry.index: bloom = obs_cherry[y]
    else:
        g = np.maximum(w.ta[f'{y}-02-01':] - 5, 0).cumsum(); bloom = g[g >= CH_THR].index[0]
    P = bloom + pd.Timedelta(days=D_POLL)
    days = pd.date_range(P + pd.Timedelta(days=140), P + pd.Timedelta(days=190))
    gp = np.maximum(w.ta[P:] - 5, 0).cumsum()
    one = pd.Timedelta(days=1)
    rows = [dict(city='서울', year=y, date=d, n=0, dap=(d - P).days, g=float(gp[d]), rain=w.rn[d], rain1=w.rn[d - one],
                 wind=w.ws[d], cold=max(0.0, w.tmin[d - one] - w.tmin[d]), dow=2, hol=0) for d in days]
    mu = MODEL.predict(X_of(pd.DataFrame(rows), FEAT, _cols))
    c = np.cumsum(mu) / mu.sum()
    q10, q90 = days[int(np.argmax(c >= .1))], days[int(np.argmax(c >= .9))]
    inten = pd.Series(mu / mu[(days >= q10) & (days <= q90)].max(), index=days).clip(upper=1)
    return dict(bloom=bloom, P=P, q10=q10, q90=q90, start=q10 - pd.Timedelta(days=START_LEAD),
                end=q90 + pd.Timedelta(days=TAIL), inten=inten, w=w, mu=pd.Series(mu, index=days), gp=gp)


def stage(s, d):
    if d < s['start']: return '없음'
    if d < s['q10']: return '시작'
    if d <= s['q90']: return '본격'
    if d <= s['end']: return '마무리'
    return '끝'


def build(day, mode, bundles):
    grids = sorted({b['grid'] for b in bundles})
    S = {g: season(day, mode, g) for g in grids}
    days = [day + pd.Timedelta(days=i) for i in range(8)]
    s0 = S[(61, 127)] if (61, 127) in S else S[grids[0]]
    out = {'기준일': f'{day:%Y-%m-%d}', '모드': mode, '날짜': [f'{d:%m-%d}' for d in days],
           '은행낙과_시즌': {'벚꽃개화': f"{s0['bloom']:%Y-%m-%d}", '수분일': f"{s0['P']:%Y-%m-%d}",
                       '시작': f"{s0['start']:%Y-%m-%d}", '본격': [f"{s0['q10']:%Y-%m-%d}", f"{s0['q90']:%Y-%m-%d}"],
                       '마무리끝': f"{s0['end']:%Y-%m-%d}"},
           '날씨': [{'날짜': f'{d:%m-%d}', '평균기온': round(s0['w'].ta[d], 1), '최저기온': round(s0['w'].tmin[d], 1),
                   '강수mm': round(s0['w'].rn[d], 1), '순간풍속': round(s0['w'].ws[d], 1), '출처': s0['w'].출처[d]} for d in days],
           '묶음': {}}
    for b in bundles:
        s = S[b['grid']]; st = [stage(s, d) for d in days]
        lvl = '피하기' if b['암'] else '가능성'
        out['묶음'][str(b['id'])] = {
            '단계': st,
            '강도': [round(float(s['inten'].get(d, 0)), 2) if x == '본격' else None for x, d in zip(st, days)],
            '피하기': [lvl if x in ('본격', '마무리') else '' for x in st],
            '확실도': '암나무' if b['암'] else '성별 미상'}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date'); ap.add_argument('--from', dest='frm'); ap.add_argument('--to')
    ap.add_argument('--mode', choices=['fcst', 'obs'], default='fcst')
    a = ap.parse_args()
    gj = json.load(open('screen/trees_bundles.geojson', encoding='utf-8'))
    bundles = [dict(id=f['properties']['묶음id'], 암=f['properties']['은행_암'] > 0,
                    grid=to_grid(f['geometry']['coordinates'][1], f['geometry']['coordinates'][0]))
               for f in gj['features'] if f['properties']['은행_암'] + f['properties']['은행_미상'] > 0]
    dates = [pd.Timestamp(a.date)] if a.date else list(pd.date_range(a.frm, a.to))
    os.makedirs(OUT, exist_ok=True); timeline = []
    for day in dates:
        o = build(day, a.mode, bundles)
        json.dump(o, open(f'{OUT}/forecast_{day:%Y%m%d}.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
        any_b = next(iter(o['묶음'].values()))
        timeline.append(dict(날짜=o['기준일'], 단계=any_b['단계'][0], 강도=any_b['강도'][0], 본격=o['은행낙과_시즌']['본격'],
                             날씨출처=o['날씨'][0]['출처']))
        print(o['기준일'], any_b['단계'][0], o['은행낙과_시즌']['본격'], '| 7일:', ' '.join(any_b['단계']))
    if len(dates) > 1:
        json.dump(timeline, open(f'{OUT}/season_{dates[0]:%Y%m%d}_{dates[-1]:%Y%m%d}.json', 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
    print(len(bundles), '은행 묶음 ×', len(dates), '일 ->', OUT)


if __name__ == '__main__':
    main()
