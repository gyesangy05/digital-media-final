# 2026년 서울 은행 낙과: 2021~2025 민원으로 학습한 2단계 모델로 예측 → 국립수목원 시민과학 관측과 비교
#   python analysis/validate_2026.py <Kna_2026하반기.xlsx>
import sys, pandas as pd, numpy as np
src=open('analysis/two_stage.py',encoding='utf-8').read().split("cities=[c for c")[0]
exec(src)  # gdd, cherry, table, X_of, q_date, CH_THR 등 재사용
HOL.update(pd.to_datetime(['2026-09-24','2026-09-25','2026-09-26','2026-10-03','2026-10-05','2026-10-09']))
D,FEAT=20,['ripe','rain','wind','cold']
cities=['서울','대구','부산','대전','광주','인천','수원시','고양시']
tr=table(D,cities); cols=sorted(set(tr.city+'_'+tr.year.astype(str)))
m=PoissonRegressor(alpha=1e-4,max_iter=3000).fit(X_of(tr,FEAT,cols),tr.n)
# 2026 서울: 벚꽃 개화는 적산온도로 추정(2026 관측값 미보유)
stn=108; g=gdd(stn,2026,'2026-02-01',5); bloom=g[g>=CH_THR].index[0]
P=bloom+pd.Timedelta(days=D); days=pd.date_range(P+pd.Timedelta(days=140),P+pd.Timedelta(days=190))
gp=gdd(stn,2026,P,5)
rows=[dict(city='서울',year=2026,date=d,n=0,dap=(d-P).days,g=float(gp[:d].iloc[-1]),
  rain=float(np.nan_to_num(rn[stn].get(d,0))),rain1=float(np.nan_to_num(rn[stn].get(d-pd.Timedelta(days=1),0))),
  wind=float(np.nan_to_num(ws[stn].get(d,np.nan),nan=np.nanmean(ws[stn]))),
  cold=float(max(0,np.nan_to_num(tmin[stn].get(d-pd.Timedelta(days=1),np.nan),nan=15)-np.nan_to_num(tmin[stn].get(d,np.nan),nan=15))),
  dow=d.dayofweek,hol=int(d in HOL)) for d in days]
te=pd.DataFrame(rows); mu=m.predict(X_of(te,FEAT,cols)); te['mu']=mu
# 요일·공휴일(신고 행동) 효과를 뺀 '낙과 자체' 곡선도 계산
te2=te.assign(dow=2,hol=0); te['mu_tree']=m.predict(X_of(te2,FEAT,cols))
q=lambda v,p: days[int(np.argmax(np.cumsum(v)/np.sum(v)>=p))]
print('벚꽃 개화 추정',bloom.date(),'| 수분일',P.date(),'| 후보 구간',days[0].date(),'~',days[-1].date())
for k in ('mu','mu_tree'):
    print(k,'예측 10%',q(te[k].values,.1).date(),'절정(50%)',q(te[k].values,.5).date(),'90%',q(te[k].values,.9).date(),
          '| 최대일',days[int(np.argmax(te[k]))].date())
# 시민과학 관측
k=pd.read_excel(sys.argv[1]); k['d']=pd.to_datetime(k['관측일자']).dt.normalize()
s=k[(k['시도']=='서울특별시')&(k['종명']=='은행나무')&(k['열매']!='잘 모르겠음')]
s=s[s.d>='2026-08-15']; s['fall']=(s['열매']=='열매가 익어 떨어짐').astype(int)
f=s[s.fall==1].d
print('\n시민 관측(서울 은행, 잘 모르겠음 제외)',len(s),'건, 떨어짐',len(f),'건')
print('떨어짐 관측 10%',f.quantile(.1).date(),'50%',f.quantile(.5).date(),'90%',f.quantile(.9).date(),'첫 관측',f.min().date())
wk=s.groupby(s.d.dt.to_period('W')).agg(관측=('fall','size'),떨어짐=('fall','sum')); wk['비율%']=(wk.떨어짐/wk.관측*100).round()
te['wk']=te.date.dt.to_period('W'); wk=wk.join(te.groupby('wk')[['mu','mu_tree']].sum().round(1),how='outer')
print(wk.loc['2026-09':'2026-11'].to_string())
te.drop(columns='wk').to_csv('analysis/2026_서울_예측.csv',index=False,encoding='utf-8-sig')
