#!/usr/bin/env python3
"""Proxy seguro para Football-Data.org. Nunca expone el token al navegador."""
import json, os, math, urllib.parse, urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

TOKEN = os.environ.get('FOOTBALL_DATA_API_TOKEN')
BASE = 'https://api.football-data.org/v4'

def api(path, params=None):
    url = BASE + path
    if params: url += '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'X-Auth-Token': TOKEN or ''})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)

class Handler(SimpleHTTPRequestHandler):
    def send_json(self, data, status=200):
        raw=json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(raw))); self.send_header('Access-Control-Allow-Origin','*'); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        try:
            p=urllib.parse.urlparse(self.path)
            q=urllib.parse.parse_qs(p.query)
            if p.path == '/api/competitions': self.send_json(api('/competitions')); return
            if p.path == '/api/teams': self.send_json(api('/competitions/%s/teams' % q['competition'][0])); return
            if p.path == '/api/matches': self.send_json(api('/matches', {'status':'LIVE'})); return
            if p.path == '/api/analyze':
                home=int(q['home'][0]); away=int(q['away'][0])
                # Motor inicial: forma reciente + ataque/defensa + Poisson.
                hm=api('/teams/%s/matches' % home, {'status':'FINISHED','limit':10})
                am=api('/teams/%s/matches' % away, {'status':'FINISHED','limit':10})
                def stats(data, team):
                    gf=ga=pts=0; n=0
                    for m in data.get('matches', []):
                        sc=m.get('score',{}).get('fullTime',{}); hg=sc.get('home'); ag=sc.get('away')
                        if hg is None or ag is None: continue
                        n+=1
                        if m.get('homeTeam',{}).get('id') == team: gf+=hg; ga+=ag; pts += 3 if hg>ag else 1 if hg==ag else 0
                        else: gf+=ag; ga+=hg; pts += 3 if ag>hg else 1 if hg==ag else 0
                    return {'matches':n,'gf':gf/n if n else 1.2,'ga':ga/n if n else 1.2,'points':pts/n if n else 1.0}
                hs,as_ = stats(hm,home),stats(am,away)
                # Evita falsa precisión: pondera datos de cada equipo por igual.
                lx=max(.15, (hs['gf'] + as_['ga'])/2); ax=max(.15, (as_['gf'] + hs['ga'])/2)
                def pois(l,k): return math.exp(-l)*l**k/math.factorial(k)
                probs={(i,j):pois(lx,i)*pois(ax,j) for i in range(8) for j in range(8)}
                total=sum(probs.values()); home_p=sum(v for (i,j),v in probs.items() if i>j)/total; draw_p=sum(v for (i,j),v in probs.items() if i==j)/total; away_p=sum(v for (i,j),v in probs.items() if i<j)/total
                over15=1-sum(v for (i,j),v in probs.items() if i+j<=1)/total
                btts=sum(v for (i,j),v in probs.items() if i>0 and j>0)/total
                exact=max(probs,key=probs.get)
                self.send_json({'home':home,'away':away,'homeMatches':hm.get('matches',[]),'awayMatches':am.get('matches',[]),'engine':{'sampleSize':hs['matches']+as_['matches'],'probabilities':{'home':round(home_p*100,1),'draw':round(draw_p*100,1),'away':round(away_p*100,1),'over1_5':round(over15*100,1),'btts':round(btts*100,1)},'expectedGoals':{'home':round(lx,2),'away':round(ax,2)},'mostLikelyScore':f'{exact[0]}-{exact[1]}','method':'Poisson sobre promedios recientes'}})
                return
            return SimpleHTTPRequestHandler.do_GET(self)
        except Exception as e: self.send_json({'error':'No se pudo consultar Football-Data.org','detail':str(e)},502)

if __name__ == '__main__':
    if not TOKEN: print('Configura FOOTBALL_DATA_API_TOKEN antes de iniciar el servidor.')
    print('ParleyStats en http://localhost:8080')
    ThreadingHTTPServer(('0.0.0.0',8080),Handler).serve_forever()
