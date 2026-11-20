# 2단계 은행 낙과 모델
#  1단계: 수분일 P = 벚꽃 개화일 + D일, 후보 구간 = P+140 ~ P+190
#  2단계: 구간 안 일별 민원 수 ~ Poisson( 익은 정도(수분 뒤 적산온도) + 비 + 바람 + 요일/공휴일 + 도시·연도 규모 )
import pandas as pd, numpy as np, csv, itertools, warnings
from sklearn.linear_model import PoissonRegressor
warnings.filterwarnings('ignore')
ta=pd.read_pickle('analysis/ta.pkl'); rn=pd.read_pickle('analysis/rn.pkl')
ws=pd.read_pickle('analysis/wsins.pkl'); tmin=pd.read_pickle('analysis/tmin.pkl')
comp=pd.read_pickle('analysis/complaints.pkl')
smap={r['도시']:int(r['지점번호']) for r in csv.DictReader(open('station_map.csv',encoding='utf-8')) if r['지점번호']}
obs_cherry=pd.read_csv('data/base/서울_계절관측_정리.csv',parse_dates=['벚꽃개화']).set_index('년도')['벚꽃개화']
YEARS=[2021,2022,2023,2024,2025]
HOL=set(pd.to_datetime(['2021-09-20','2021-09-21','2021-09-22','2021-10-03','2021-10-04','2021-10-09','2021-10-11',
 '2022-09-09','2022-09-10','2022-09-11','2022-09-12','2022-10-03','2022-10-09','2022-10-10',
 '2023-09-28','2023-09-29','2023-09-30','2023-10-02','2023-10-03','2023-10-09',
 '2024-09-16','2024-09-17','2024-09-18','2024-10-01','2024-10-03','2024-10-09',
 '2025-10-03','2025-10-05','2025-10-06','2025-10-07','2025-10-08','2025-10-09']))
# --- 벚꽃 개화: 서울은 관측값, 다른 도시는 서울에서 맞춘 적산온도(2/1부터 5℃ 기준)로 추정
def gdd(stn,y,start,base,end=None):
    s=ta[stn][pd.Timestamp(start):pd.Timestamp(end) if end else pd.Timestamp(y,12,31)]
    return np.maximum(s-base,0).cumsum()
cal=[float(gdd(108,y,f'{y}-02-01',5)[:obs_cherry[y]].iloc[-1]) for y in range(2016,2026)]
CH_THR=float(np.mean(cal))
def cherry(city,y):
    if city=='서울' and y in obs_cherry.index: return obs_cherry[y]
    g=gdd(smap[city],y,f'{y}-02-01',5); return g[g>=CH_THR].index[0]
# --- 자료 표 만들기
def table(D,cities,minN=15):
    rows=[]
    for city in cities:
        stn=smap[city]
        for y in YEARS:
            c=comp[comp.city==city].set_index('date')['n']
            P=cherry(city,y)+pd.Timedelta(days=D)
            days=pd.date_range(P+pd.Timedelta(days=140),P+pd.Timedelta(days=190))
            n=c.reindex(days,fill_value=0)
            if n.sum()<minN: continue
            g=gdd(stn,y,P,5)
            for d in days:
                rows.append(dict(city=city,year=y,date=d,n=int(n[d]),dap=(d-P).days,g=float(g[:d].iloc[-1]),
                    rain=float(np.nan_to_num(rn[stn].get(d,0))),rain1=float(np.nan_to_num(rn[stn].get(d-pd.Timedelta(days=1),0))),
                    wind=float(np.nan_to_num(ws[stn].get(d,np.nan),nan=np.nanmean(ws[stn]))),
                    cold=float(max(0,np.nan_to_num(tmin[stn].get(d-pd.Timedelta(days=1),np.nan),nan=15)-np.nan_to_num(tmin[stn].get(d,np.nan),nan=15))),
                    dow=d.dayofweek,hol=int(d in HOL)))
    return pd.DataFrame(rows)
def X_of(df,feat,cy_cols):
    X=pd.DataFrame(index=df.index)
    if 'ripe' in feat:
        z=(df.g-1800)/400; X['z']=z; X['z2']=z**2
    if 'dap' in feat:
        z=(df.dap-160)/15; X['d']=z; X['d2']=z**2
    if 'rain' in feat: X['lr']=np.log1p(df.rain); X['lr1']=np.log1p(df.rain1)
    if 'wind' in feat: X['w']=(df.wind-10)/5
    if 'cold' in feat: X['c']=df.cold/3
    for k in range(5,7): X[f'dow{k}']=(df.dow==k).astype(float)
    X['hol']=df.hol
    cy=pd.get_dummies(df.city+'_'+df.year.astype(str)).reindex(columns=cy_cols,fill_value=0).astype(float)
    return pd.concat([X,cy],axis=1)
def q_date(days,vals,q):
    c=np.cumsum(vals)/np.sum(vals); return days[int(np.argmax(c>=q))]
def evaluate(df,feat):
    res=[]
    for y in YEARS:
        tr,te=df[df.year!=y],df[df.year==y]
        if te.empty or tr.empty: continue
        cols=sorted(set(tr.city+'_'+tr.year.astype(str)))
        m=PoissonRegressor(alpha=1e-4,max_iter=3000).fit(X_of(tr,feat,cols),tr.n)
        for city,g in te.groupby('city'):
            Xt=X_of(g,feat,cols)  # 도시·연도 더미는 0 → 모양만 비교
            mu=m.predict(Xt).astype(float); days=g.date.values
            # 비교용: 날씨 없이 같은 요일·공휴일 효과만 쓴 모양은 별도 함수에서
            o10,o50,o90=[q_date(days,g.n.values,q) for q in (.1,.5,.9)]
            p10,p50,p90=[q_date(days,mu,q) for q in (.1,.5,.9)]
            res.append(dict(city=city,year=y,N=int(g.n.sum()),
                e10=(pd.Timestamp(p10)-pd.Timestamp(o10)).days,e50=(pd.Timestamp(p50)-pd.Timestamp(o50)).days,
                width=(pd.Timestamp(p90)-pd.Timestamp(p10)).days,
                hit=int(pd.Timestamp(p10)<=pd.Timestamp(o50)<=pd.Timestamp(p90))))
    return pd.DataFrame(res)
cities=[c for c in ['서울','대구','부산','대전','광주','인천','수원시','고양시']]
print('벚꽃 적산 기준값(2/1~, 5℃):',round(CH_THR))
summ=[]
for D in (10,15,20,25):
    df=table(D,cities)
    for feat in (['dap'],['ripe'],['ripe','rain'],['ripe','rain','wind','cold']):
        r=evaluate(df,feat)
        if r.empty: continue
        w=r.N  # 민원 많은 도시에 가중
        summ.append(dict(D=D,변수='+'.join(feat),사례=len(r),
            시작오차=round(np.average(abs(r.e10),weights=w),1),절정오차=round(np.average(abs(r.e50),weights=w),1),
            절정3일=round(np.average(abs(r.e50)<=3,weights=w)*100),절정7일=round(np.average(abs(r.e50)<=7,weights=w)*100),
            예보폭=round(np.average(r.width,weights=w),1),절정적중=round(np.average(r.hit,weights=w)*100)))
S=pd.DataFrame(summ); print(S.to_string(index=False)); S.to_csv('analysis/2단계모델_검증.csv',index=False,encoding='utf-8-sig')
