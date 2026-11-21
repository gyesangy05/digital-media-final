# -*- coding: utf-8 -*-
"""모델 설명 탭 데이터 -> docs/model.json
  python analysis/build.py   (analysis/*.pkl 먼저)
  python scripts/make_model_data.py
담는 것: 은행 낙과 — 기준일별 예측 곡선(시즌 재생 8/25~11/20), 계수, 검증, 2026 날씨 / 묶음 — 예시 노선의 나무와 묶음 크기 분포"""
import json, os, sys
import numpy as np, pandas as pd

sys.path.insert(0, 'scripts')
import make_forecast as mf  # 모델 학습까지 같이 됨

D = lambda t: f'{t:%Y-%m-%d}'
r3 = lambda a: [round(float(x), 3) for x in a]

# ---------- 은행 낙과: 기준일마다 그날 알 수 있던 날씨로 다시 계산한 곡선 ----------
days = pd.date_range('2026-08-25', '2026-11-20')
curves = []
for d in days:
    s = mf.season(d, 'obs')
    mu = s['mu'] / s['mu'].max()
    curves.append({'기준일': D(d), '첫날': D(s['mu'].index[0]), '곡선': r3(mu), '본격': [D(s['q10']), D(s['q90'])], '시작': D(s['start']), '끝': D(s['end'])})
last = mf.season(days[-1], 'obs')
w = last['w']['2026-08-01':'2026-11-30']
names = {'z': '익은 정도(적산온도, 400℃·일당)', 'z2': '익은 정도²(너무 익으면 줄어듦)', 'lr': '당일 비 log(1+mm)', 'lr1': '전날 비 log(1+mm)',
         'w': '순간최대풍속(5m/s당)', 'c': '최저기온 하강(3℃당)', 'dow5': '토요일', 'dow6': '일요일', 'hol': '공휴일'}
cols = mf.X_of(pd.DataFrame([dict(city='서울', year=2026, date=days[0], n=0, dap=150, g=1800, rain=0, rain1=0, wind=10, cold=0, dow=2, hol=0)]),
               mf.FEAT, mf._cols).columns
coef = {names[k]: round(float(np.exp(v)), 2) for k, v in zip(cols, mf.MODEL.coef_) if k in names}
v = pd.read_csv('analysis/2단계모델_검증.csv', encoding='utf-8-sig')
v = v[(v.D == 20) & (v.변수 == 'ripe+rain+wind+cold')].iloc[0]
fall = {'벚꽃개화': D(last['bloom']), '수분일': D(last['P']), '재생': curves, '계수_배수': coef,
        '검증': {'사례(도시×연도)': int(v.사례), '절정오차일': float(v.절정오차), '절정±3일%': int(v.절정3일), '절정±7일%': int(v.절정7일),
               '80%폭일': float(v.예보폭), '실제절정이폭안%': int(v.절정적중)},
        '날씨': {'첫날': D(w.index[0]), '평균기온': r3(w.ta), '강수mm': r3(w.rn), '순간풍속': r3(w.ws), '출처': [x[:2] for x in w.출처]},
        '적산': {'첫날': D(last['P']), '값': [round(float(x)) for x in last['gp']['2026-08-01':'2026-11-30']], '값첫날': '2026-08-01'}}

# ---------- 묶음 예시: 서울시립대로(동대문구) 나무 하나하나와 묶음 ----------
t = pd.read_csv('data/base/서울_가로수_묶음.csv', encoding='utf-8-sig')
ex = t[(t.자치구 == '동대문구') & (t.노선 == '서울시립대로')]
sz = t.groupby('묶음id').size()
bund = {'예시노선': '동대문구 서울시립대로', '나무': [[round(a, 6), round(b, 6), c, int(i)] for a, b, c, i in
                                          zip(ex['좌표(경도)'], ex['좌표(위도)'], ex['수종'], ex['묶음id'])],
        '그루수': int(len(t)), '묶음수': int(sz.size), '크기분포': {int(k): int(n) for k, n in sz.value_counts().sort_index().items()},
        '암나무묶음': int(t[t.수종 == '은행나무 암나무'].묶음id.nunique()),
        '은행묶음': int(t[t.수종.str.startswith('은행나무')].묶음id.nunique())}
json.dump({'낙과': fall, '묶음': bund}, open('docs/model.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
assert len(curves) == len(days) and len(bund['나무']) > 10
print('낙과 곡선', len(curves), '일 / 계수', coef, '/ 예시 나무', len(bund['나무']), '->', 'docs/model.json', os.path.getsize('docs/model.json'), 'B')
