import pandas as pd, numpy as np, csv, itertools
ta=pd.read_pickle('analysis/ta.pkl'); c=pd.read_pickle('analysis/complaints.pkl')
smap={r['도시']:int(r['지점번호']) for r in csv.DictReader(open('station_map.csv',encoding='utf-8')) if r['지점번호']}
YEARS=[2021,2022,2023,2024,2025]
def onset(city,y,q):
    s=c[(c.city==city)&(c.date>=f'{y}-08-15')&(c.date<=f'{y}-10-31')].set_index('date')['n']
    s=s.reindex(pd.date_range(f'{y}-08-15',f'{y}-10-31'),fill_value=0)
    tot=s.sum()
    if tot==0: return None,0
    return int(s.index[(s.cumsum()>=q*tot).values.argmax()].dayofyear), int(tot)
def build(q,minN):
    obs=[]
    for city,stn in smap.items():
        if stn not in ta.columns: continue
        for y in YEARS:
            d,n=onset(city,y,q)
            if d and n>=minN: obs.append((city,stn,y,d,n))
    return obs
def cum(stn,y,base,sm):
    s=ta[stn][f'{y}-{sm:02d}-01':f'{y}-11-30']
    return np.maximum(s-base,0).cumsum()
def pred(stn,y,base,sm,F):
    cc=cum(stn,y,base,sm); h=cc[cc>=F]
    return h.index[0].dayofyear if len(h) else np.nan
def F_at(stn,y,d,base,sm):
    cc=cum(stn,y,base,sm); dd=pd.Timestamp(y,1,1)+pd.Timedelta(days=d-1)
    return cc[:dd].iloc[-1]
def evaluate(obs,base,sm,fold):  # fold: 'year' or 'city'
    errs=[]
    Fs={(o[0],o[2]):F_at(o[1],o[2],o[3],base,sm) for o in obs}
    for o in obs:
        key=o[2] if fold=='year' else o[0]
        train=[x for x in obs if (x[2] if fold=='year' else x[0])!=key]
        if len(train)<3: continue
        w=np.array([x[4] for x in train],float)
        F=np.average([Fs[(x[0],x[2])] for x in train],weights=w)
        errs.append(pred(o[1],o[2],base,sm,F)-o[3])
    return np.array(errs)
def baseline(obs,fold):
    e=[]
    for o in obs:
        key=o[2] if fold=='year' else o[0]
        tr=[x for x in obs if (x[2] if fold=='year' else x[0])!=key]
        e.append(np.average([x[3] for x in tr],weights=[x[4] for x in tr])-o[3])
    return np.array(e)
out=[]
for q in (0.1,0.25,0.5):
    for minN in (15,30):
        obs=build(q,minN)
        if len(obs)<8: continue
        best=None
        for base,sm in itertools.product([0,5,10,15],[1,3,4,5,6]):
            e=evaluate(obs,base,sm,'year')
            m=np.nanmean(np.abs(e))
            if best is None or m<best[0]: best=(m,base,sm)
        m,base,sm=best
        ey=evaluate(obs,base,sm,'year'); ec=evaluate(obs,base,sm,'city')
        by=baseline(obs,'year'); bc=baseline(obs,'city')
        out.append([q,minN,len(obs),len({o[0] for o in obs}),base,sm,
                    round(np.nanmean(np.abs(ey)),1),round(np.mean(np.abs(ey)<=3)*100),
                    round(np.nanmean(np.abs(ec)),1),round(np.mean(np.abs(ec)<=3)*100),
                    round(np.mean(np.abs(by)),1),round(np.mean(np.abs(bc)),1)])
cols=['누적비율','최소건수','사례수','도시수','기준온도','시작월','연도제외MAE','±3일%','도시제외MAE','±3일%(도시)','평년MAE(연도)','평년MAE(도시)']
df=pd.DataFrame(out,columns=cols); print(df.to_string(index=False))
df.to_csv('analysis/모델검증.csv',index=False,encoding='utf-8-sig')
