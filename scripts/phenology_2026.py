# -*- coding: utf-8 -*-
"""2026 서울 개화(벚꽃·목련)·단풍(은행·단풍나무) 시기 예측 + 날짜별 날씨 -> docs/phen.json
  python scripts/phenology_2026.py
기준 날짜(앵커)
  벚꽃 개화   : 2/1부터 5℃ 적산온도, 임계값 = 2016~2025 서울 관측 개화일 적산값 평균 (한 해씩 빼고 검증)
  은행 단풍시작: 9/1부터 '기준온도-평균기온' 추위 누적, 기준온도 12~24℃ 중 한 해씩 빼고 오차가 가장 작은 값
  목련 개화   : 벚꽃 개화 + (국립수목원 전시원 백목련 개화시작 - 왕벚나무 개화시작) 중앙값, 2009~2025
  단풍나무 단풍: 은행 단풍시작 + (기상청 서울 단풍나무단풍시작 - 은행단풍시작) 중앙값, 1973~2025 (최근 10년 중앙값은 -13일이지만 2026 서울 시민관측에선 단풍나무·은행 절반 물듦이 11/3·11/4로 비슷해 장기값 사용)
단계 사이 간격: 국립수목원 전시원 관측(2009~2025) 중앙값. 단풍나무는 수목원 기록이 없어 은행 간격을 씀(가정).
출처: 국립수목원 식물계절관측 관측기록(공공누리 제2유형), 기상청 계절관측·지상관측."""
import glob, json
import numpy as np, pandas as pd

Y = 2026
# ---------- 서울 날씨 (ASOS 108) ----------
rows = []
for p in sorted(glob.glob('data/weather/kma_raw/*.txt')):
    for line in open(p, encoding='utf-8'):
        f = line.strip().split(',')
        if len(f) > 38 and f[1] == '108':
            rows.append((f[0], float(f[10]), float(f[13]), float(f[38])))
w = pd.DataFrame(rows, columns=['d', 'ta', 'tmin', 'rn']).drop_duplicates('d')
w.index = pd.to_datetime(w.pop('d'))
w = w.sort_index()
w.loc[w.ta <= -50, 'ta'] = np.nan; w.loc[w.tmin <= -50, 'tmin'] = np.nan; w.loc[w.rn < 0, 'rn'] = 0
h = w[(w.index.year >= 2016) & (w.index.year <= 2025)]
doy = h.groupby(h.index.day_of_year).mean()
clim = pd.concat([doy.iloc[-7:], doy, doy.iloc[:7]]).rolling(15, center=True).mean().iloc[7:-7]
idx = pd.date_range(f'{Y}-01-01', f'{Y}-12-31')
full = clim.reindex(idx.day_of_year).set_index(idx)
src = pd.Series('평년값', index=idx)
o = w.reindex(idx)
for c in ['ta', 'tmin', 'rn']:
    m = o[c].notna(); full.loc[m, c] = o.loc[m, c]
src[o.ta.notna()] = '관측'
ta = pd.concat([w.ta[w.index.year < Y], full.ta])

# ---------- 관측 기록 ----------
s = pd.read_csv('data/base/서울_계절관측_정리.csv', encoding='utf-8-sig')
for c in s.columns[1:]: s[c] = pd.to_datetime(s[c])
s = s.set_index('년도')


def first_dates(f, col, stages):
    d = pd.read_excel(f'나무/{f}.xlsx')
    d = d[d['세부관측'] == '전시원']; d['관측일자'] = pd.to_datetime(d['관측일자'])
    return {st: d[d[col] == st].groupby('연도')['관측일자'].min() for st in stages}


FL = ['꽃눈파열', '개화시작', '개화50%이상', '낙화90~100%']
LF = ['단풍시작20~30%', '단풍50%이상', '단풍90~100%', '낙엽90~100%']
cher, mag = first_dates('왕벚나무', '꽃', FL), first_dates('백목련', '꽃', FL)
gink = first_dates('은행나무', '잎', LF)
med = lambda a, b: int(round((a - b).dt.days.dropna().median()))
gap = lambda D, st: {k: med(D[k], D[st[1] if k == st[0] else st[0]]) * (-1 if k == st[0] else 1) for k in st}


def offsets(D, st, anchor):
    """anchor 단계 기준 각 단계까지 일수(중앙값)."""
    return {k: (0 if k == anchor else med(D[k], D[anchor])) for k in st}


# ---------- 벚꽃 개화 모델 ----------
def gdd(y): return (ta[f'{y}-02-01':f'{y}-06-01'] - 5).clip(lower=0).cumsum()


yrs = [y for y in range(2016, 2026) if pd.notna(s.loc[y, '벚꽃개화'])]
gv = {y: float(gdd(y)[s.loc[y, '벚꽃개화']]) for y in yrs}
err = []
for y in yrs:
    thr = np.mean([gv[k] for k in yrs if k != y]); g = gdd(y); err.append((g[g >= thr].index[0] - s.loc[y, '벚꽃개화']).days)
g = gdd(Y); cherry = g[g >= np.mean(list(gv.values()))].index[0]
cher_mae = float(np.abs(err).mean())


# ---------- 은행 단풍시작 모델 ----------
def cool(y, b): return (b - ta[f'{y}-09-01':f'{y}-12-31']).clip(lower=0).cumsum()


gy = [y for y in range(2016, 2026) if pd.notna(s.loc[y, '은행단풍시작'])]
best = None
for b in range(12, 25):
    cv = {y: float(cool(y, b)[s.loc[y, '은행단풍시작']]) for y in gy}
    e = []
    for y in gy:
        thr = np.mean([cv[k] for k in gy if k != y]); c = cool(y, b); e.append((c[c >= thr].index[0] - s.loc[y, '은행단풍시작']).days)
    if best is None or np.abs(e).mean() < best[1]: best = (b, float(np.abs(e).mean()), cv)
c = cool(Y, best[0]); ginkgo = c[c >= np.mean(list(best[2].values()))].index[0]

# ---------- 앵커 -> 단계 날짜 ----------
D = lambda t: t.strftime('%Y-%m-%d')
oc, om, og = offsets(cher, FL, '개화시작'), offsets(mag, FL, '개화시작'), offsets(gink, LF, '단풍시작20~30%')
mag_open = cherry + pd.Timedelta(days=med(mag['개화시작'], cher['개화시작']))
maple_start = ginkgo + pd.Timedelta(days=med(s['단풍나무단풍시작'], s['은행단풍시작']))
stages = lambda a, off: {k: D(a + pd.Timedelta(days=v)) for k, v in off.items()}
out = {
    '연도': Y,
    '개화': {'벚꽃': stages(cherry, oc), '목련': stages(mag_open, om)},
    '단풍': {'은행': stages(ginkgo, og), '단풍': stages(maple_start, og)},
    '근거': {'벚꽃개화_오차일(한해씩빼고,2016-2025)': round(cher_mae, 1),
           '은행단풍시작_오차일': round(best[1], 1), '은행단풍_기준온도': best[0],
           '단계간격_벚꽃': oc, '단계간격_목련': om, '단계간격_은행단풍(단풍나무도 같게 가정)': og,
           '목련-벚꽃_개화차': med(mag['개화시작'], cher['개화시작']),
           '단풍나무-은행_단풍시작차': med(s['단풍나무단풍시작'], s['은행단풍시작'])},
    '날씨': {'시작': D(idx[0]), '평균기온': [round(x, 1) for x in full.ta], '최저기온': [round(x, 1) for x in full.tmin],
           '강수mm': [round(x, 1) for x in full.rn], '출처': ['관' if x == '관측' else '평' for x in src]},
}
# 단계 순서가 날짜 순서와 맞는지 확인
for cat in ('개화', '단풍'):
    for sp, st in out[cat].items():
        v = list(st.values()); assert v == sorted(v), (sp, st)
json.dump(out, open('docs/phen.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print(json.dumps({k: out[k] for k in ('개화', '단풍', '근거')}, ensure_ascii=False, indent=1))
