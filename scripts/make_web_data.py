# -*- coding: utf-8 -*-
"""웹 데모 데이터: data/base/서울_가로수_묶음.csv + screen/forecast/forecast_*.json -> docs/bundles.json, docs/season.json
  python scripts/make_web_data.py
날씨가 서울 ASOS 1곳이라 같은 날짜엔 은행 묶음 전부 단계가 같다 -> 묶음별 예보 대신 날짜별 시즌 1줄만 싣고,
묶음별 차이(암나무 '피하기' / 성별 미상 '가능성')는 화면에서 은행_암·은행_미상으로 계산한다."""
import glob, json, os
import pandas as pd

d = pd.read_csv('data/base/서울_가로수_묶음.csv', encoding='utf-8-sig')
d['노선'] = d['노선'].fillna('(노선 없음)')
gu = sorted(d['자치구'].unique()); sp = d['수종'].value_counts().index.tolist(); ro = sorted(d['노선'].unique())
gi, si, ri = ({v: i for i, v in enumerate(x)} for x in (gu, sp, ro))
rows = []
for bid, g in d.groupby('묶음id'):
    rows.append([round(g['좌표(경도)'].mean(), 5), round(g['좌표(위도)'].mean(), 5), gi[g['자치구'].iloc[0]],
                 si[g['수종'].mode().iloc[0]], ri[g['노선'].mode().iloc[0]], len(g),
                 int((g['수종'] == '은행나무 암나무').sum()), int((g['수종'] == '은행나무').sum())])
os.makedirs('docs', exist_ok=True)
json.dump({'열': ['경도', '위도', '구', '수종', '노선', '그루수', '은행_암', '은행_미상'], '구': gu, '수종': sp, '노선': ro, '묶음': rows},
          open('docs/bundles.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))

days = []
for p in sorted(glob.glob('screen/forecast/forecast_*.json')):
    o = json.load(open(p, encoding='utf-8'))
    b = next(iter(o['묶음'].values()))
    days.append({'기준일': o['기준일'], '날짜': o['날짜'], '시즌': o['은행낙과_시즌'], '날씨': o['날씨'], '단계': b['단계'], '강도': b['강도']})
json.dump({'모드': '시즌 재생(관측 날씨)', '일': days}, open('docs/season.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
assert len(rows) == d['묶음id'].nunique() and days
print(len(rows), '묶음,', len(days), '일 ->', 'docs/')
