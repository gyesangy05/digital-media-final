# 기상 원본 -> 지점별 일평균기온 표, 민원 -> 도시별 일별 건수
import glob, csv, json, os, collections, datetime as dt
import pandas as pd
import sys; sys.path.insert(0, '.')
import fetch
rows=[]
for p in sorted(glob.glob('data/weather/kma_raw/*.txt')):
    for line in open(p,encoding='utf-8'):
        f=line.strip().split(',')
        if len(f)<14: continue
        rows.append((f[0],int(f[1]),float(f[10]),float(f[11]),float(f[13]),float(f[38])))
w=pd.DataFrame(rows,columns=['date','stn','ta','tmax','tmin','rn'])
w['date']=pd.to_datetime(w['date'])
for c in ['ta','tmax','tmin']: w.loc[w[c]<=-50,c]=float('nan')
w.loc[w['rn']<0,'rn']=0
w=w.drop_duplicates(['stn','date'])
ta=w.pivot(index='date',columns='stn',values='ta').sort_index()
ta=ta.reindex(pd.date_range(ta.index.min(),ta.index.max())).interpolate(limit=5)
ta.to_pickle('analysis/ta.pkl')
w.pivot(index='date',columns='stn',values='rn').to_pickle('analysis/rn.pkl')
print('기온표',ta.shape, '결측비율', round(float(ta.isna().mean().mean()),4))
# 민원 도시별 일별
def city(r):
    g,n=r['그룹'],r['지역']
    return g if g in('서울','부산','대구','인천','광주','대전','울산') else n
cnt=collections.defaultdict(int)
for r in fetch.load_regions():
    for y in fetch.YEARS:
        p=f"data/raw/{fetch.safe(r['지역'])}_{y}.json"
        if os.path.exists(p):
            for d in json.load(open(p)):
                cnt[(city(r),str(d['label'])[:8])]+=int(d['hits'])
for k in ('20240816','20240817','20240818'): cnt[('전국',k)]=0
c=pd.Series(cnt); c.index=pd.MultiIndex.from_tuples(c.index,names=['city','date'])
c=c.reset_index(); c.columns=['city','date','n']; c['date']=pd.to_datetime(c['date'])
c.to_pickle('analysis/complaints.pkl'); print('민원 도시',c['city'].nunique(),'행',len(c))
