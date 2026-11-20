import sys, pandas as pd, numpy as np
d=pd.read_csv(sys.argv[1])
d=d[d['수종']!='공분'].copy()
lat0=37.585
d['x']=(d['좌표(경도)']-127.05)*111320*np.cos(np.radians(lat0)); d['y']=(d['좌표(위도)']-lat0)*110540
d['그룹수종']=d['수종']
gid=0; out=[]
for (r,s),g in d.groupby(['노선','그룹수종']):
    p=g[['x','y']].values
    if len(p)>1:
        c=p-p.mean(0); u=np.linalg.svd(c,full_matrices=False)[2][0]; t=c@u
    else: t=np.zeros(1)
    g=g.assign(t=t).sort_values('t'); cur=[]; last=None
    for i,row in g.iterrows():
        if cur and (len(cur)>=8 or abs(row.t-last)>40):
            gid+=1; out+= [(j,gid) for j in cur]; cur=[]
        cur.append(i); last=row.t
    gid+=1; out+=[(j,gid) for j in cur]
m=dict(out); d['묶음id']=d.index.map(m)
sz=d.groupby('묶음id').size()
print("나무",len(d),"묶음",sz.size)
print(sz.value_counts().sort_index().to_string())
print("5~10그루 묶음 비율", round(((sz>=5)&(sz<=10)).mean()*100,1),"%  1~2그루",(sz<=2).sum())
f=d[d['수종']=='은행나무 암나무'].groupby('묶음id').size(); print("암나무 묶음",f.size)
d.drop(columns=['x','y','t'],errors='ignore').to_csv(sys.argv[2],index=False,encoding='utf-8-sig')
