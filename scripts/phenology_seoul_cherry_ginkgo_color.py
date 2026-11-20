import sys, pandas as pd, numpy as np
w=pd.read_csv(sys.argv[1],parse_dates=['일시']); s=pd.read_csv(sys.argv[2],parse_dates=['벚꽃개화','은행단풍시작'])
def gdd_series(y,base=5,start='02-01'):
    b=w[(w['일시']>=f'{y}-{start}')&(w['일시']<f'{y}-06-01')].copy(); b['g']=(b['평균기온(°C)']-base).clip(lower=0).cumsum(); return b
yrs=[y for y in range(2016,2026) if pd.notna(s.loc[s['년도']==y,'벚꽃개화']).any()]
obs={y:s.loc[s['년도']==y,'벚꽃개화'].iloc[0] for y in yrs}
g={y:float(gdd_series(y).set_index('일시').loc[obs[y],'g']) for y in yrs}
errs=[]
for y in yrs:
    thr=np.mean([g[k] for k in yrs if k!=y])
    b=gdd_series(y); pred=b.loc[b['g']>=thr,'일시'].min()
    errs.append((pred-obs[y]).days)
errs=np.array(errs); print("벚꽃 개화, 한 해씩 빼고 맞춘 오차(일):",errs.tolist()); print("평균절대오차",round(np.abs(errs).mean(),1),"RMSE",round(np.sqrt((errs**2).mean()),1),"최대",np.abs(errs).max(),"7일 이내 비율",f"{(np.abs(errs)<=7).mean()*100:.0f}%")
# ginkgo coloring: simple chill accumulation from Sep1 base 15C, LOO
def cool(y,base):
    a=w[(w['일시']>=f'{y}-09-01')&(w['일시']<=f'{y}-12-31')].copy(); a['c']=(base-a['평균기온(°C)']).clip(lower=0).cumsum(); return a
gy=[y for y in range(2016,2026) if pd.notna(s.loc[s['년도']==y,'은행단풍시작']).any()]
go={y:s.loc[s['년도']==y,'은행단풍시작'].iloc[0] for y in gy}
best=None
for base in [12,13,14,15,16,17,18,19,20]:
    c={y:float(cool(y,base).set_index('일시').loc[go[y],'c']) for y in gy}
    e=[]
    for y in gy:
        thr=np.mean([c[k] for k in gy if k!=y]); a=cool(y,base); p=a.loc[a['c']>=thr,'일시'].min(); e.append((p-go[y]).days)
    e=np.array(e); m=np.abs(e).mean()
    if best is None or m<best[1]: best=(base,m,e)
print("은행 단풍(추위 누적, 기준",best[0],"℃) 오차:",best[2].tolist(),"평균절대오차",round(best[1],1),"7일 이내",f"{(np.abs(best[2])<=7).mean()*100:.0f}%")
