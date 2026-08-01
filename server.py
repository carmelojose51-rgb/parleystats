#!/usr/bin/env python3
import json, os, math, urllib.parse, urllib.request
from datetime import date, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
TOKEN = os.environ.get('FOOTBALL_DATA_API_TOKEN')
BASE = 'https://api.football-data.org/v4'
def api(path, params=None):
    url=BASE+path
    if params: url+='?'+urllib.parse.urlencode(params)
    req=urllib.request.Request(url, headers={'X-Auth-Token':TOKEN or ''})
    with urllib.request.urlopen(req,timeout=20) as r: return json.load(r)
class Handler(SimpleHTTPRequestHandler):
    def send_json(self,data,status=200):
        raw=json.dumps(data,ensure_ascii=False).encode(); self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(raw))); self.send_header('Access-Control-Allow-Origin','*'); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        try:
            p=urllib.parse.urlparse(self.path); q=urllib.parse.parse_qs(p.query)
            if p.path=='/api/competitions': self.send_json(api('/competitions')); return
            if p.path=='/api/teams': self.send_json(api('/competitions/%s/teams'%q['competition'][0])); return
            if p.path=='/api/matches': self.send_json(api('/matches',{'status':'LIVE'})); return
            if p.path=='/api/analyze':
                home=int(q['home'][0]); away=int(q['away'][0]); target=q.get('date',[None])[0]
                # La fecha elegida identifica el partido a analizar; no debe
                # limitar el historial a esa fecha. Para un partido futuro,
                # usamos los últimos partidos terminados de ambos equipos.
                hist={'status':'FINISHED','limit':10}
                hm=api('/teams/%s/matches'%home,hist); am=api('/teams/%s/matches'%away,hist)
                fixture=None
                if target:
                    try:
                        fixture_data=api('/teams/%s/matches'%home,{'dateFrom':target,'dateTo':target,'limit':100})
                        for match in fixture_data.get('matches',[]):
                            if match.get('homeTeam',{}).get('id')==away or match.get('awayTeam',{}).get('id')==away:
                                fixture={'id':match.get('id'),'status':match.get('status'),'utcDate':match.get('utcDate'),'competition':match.get('competition',{}).get('name')}
                                break
                    except Exception:
                        fixture=None
                def stats(data,team):
                    gf=ga=pts=n=0
                    for m in data.get('matches',[]):
                        sc=m.get('score',{}).get('fullTime',{}); hg=sc.get('home'); ag=sc.get('away')
                        if hg is None or ag is None: continue
                        n+=1; ish=m.get('homeTeam',{}).get('id')==team; gf+=hg if ish else ag; ga+=ag if ish else hg; pts+=3 if (hg>ag if ish else ag>hg) else 1 if hg==ag else 0
                    return {'matches':n,'gf':gf/n if n else 1.2,'ga':ga/n if n else 1.2}
                hs,avs=stats(hm,home),stats(am,away); lx=max(.15,(hs['gf']+avs['ga'])/2); ax=max(.15,(avs['gf']+hs['ga'])/2)
                def pois(l,k): return math.exp(-l)*l**k/math.factorial(k)
                probs={(i,j):pois(lx,i)*pois(ax,j) for i in range(8) for j in range(8)}; total=sum(probs.values()); hp=sum(v for (i,j),v in probs.items() if i>j)/total; dp=sum(v for (i,j),v in probs.items() if i==j)/total; ap=sum(v for (i,j),v in probs.items() if i<j)/total; o15=1-sum(v for (i,j),v in probs.items() if i+j<=1)/total; btts=sum(v for (i,j),v in probs.items() if i>0 and j>0)/total; ex=max(probs,key=probs.get)
                self.send_json({'homeMatches':hm.get('matches',[]),'awayMatches':am.get('matches',[]),'engine':{'sampleSize':hs['matches']+avs['matches'],'probabilities':{'home':round(hp*100,1),'draw':round(dp*100,1),'away':round(ap*100,1),'over1_5':round(o15*100,1),'btts':round(btts*100,1)},'expectedGoals':{'home':round(lx,2),'away':round(ax,2)},'mostLikelyScore':f'{ex[0]}-{ex[1]}','date':target,'fixture':fixture,'method':'Poisson sobre promedios recientes'}}); return
            return SimpleHTTPRequestHandler.do_GET(self)
        except Exception as e: self.send_json({'error':'No se pudo consultar Football-Data.org','detail':str(e)},502)
if __name__=='__main__':
    port=int(os.environ.get('PORT','10000')); print('ParleyStats en puerto',port); ThreadingHTTPServer(('0.0.0.0',port),Handler).serve_forever()
