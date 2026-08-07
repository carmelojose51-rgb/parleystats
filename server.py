#!/usr/bin/env python3
import json, os, math, time, urllib.parse, urllib.request
from datetime import date, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
TOKEN = os.environ.get('FOOTBALL_DATA_API_TOKEN')
API_FOOTBALL_KEY = os.environ.get('API_FOOTBALL_KEY')
BASE = 'https://api.football-data.org/v4'
AF_BASE = 'https://v3.football.api-sports.io'
def api(path, params=None):
    url=BASE+path
    if params: url+='?'+urllib.parse.urlencode(params)
    req=urllib.request.Request(url, headers={'X-Auth-Token':TOKEN or ''})
    with urllib.request.urlopen(req,timeout=20) as r: return json.load(r)
def af_api(path, params=None):
    url=AF_BASE+path
    if params: url+='?'+urllib.parse.urlencode(params)
    req=urllib.request.Request(url, headers={'x-apisports-key':API_FOOTBALL_KEY or ''})
    with urllib.request.urlopen(req,timeout=20) as r: return json.load(r)
AF_CACHE={}
AF_RESPONSE_CACHE={}
LIVE_CACHE={'at':0,'data':None}
# El endpoint global de Football-Data no siempre incluye los partidos que
# aparecen con estado LIVE en la consulta de cada competición. Consultamos
# las ligas activas más importantes y dejamos el resultado en caché breve.
LIVE_CODES=('PPL','FL1','ELC','BSA','PD','SA','DED','PL','BL1')

def af_api_cached(path, params=None):
    key=(path,tuple(sorted((params or {}).items())))
    if key in AF_RESPONSE_CACHE: return AF_RESPONSE_CACHE[key]
    data=af_api(path,params)
    if data.get('errors'):
        return data
    AF_RESPONSE_CACHE[key]=data
    return data

def af_team_id(name):
    key=('team',name)
    if key in AF_CACHE: return AF_CACHE[key]
    import unicodedata, re
    clean=unicodedata.normalize('NFKD',name or '').encode('ascii','ignore').decode()
    clean=re.sub(r'[^A-Za-z0-9 ]',' ',clean).replace(' FBPA','').replace(' FC','').strip()
    n=re.sub(r'[^a-z0-9]','',clean.lower())
    known={'gremio':130,'saopaulo':126,'alaves':542,'getafe':154,'realmadrid':541,'barcelona':529,'sevilla':536,'atleticodemadrid':530,'arsenal':42,'chelsea':49,'liverpool':40,'mancity':50}
    tid=next((v for k,v in known.items() if n==k or n.startswith(k)),None)
    if tid is None:
        try:
            rows=af_api_cached('/teams',{'search':clean}).get('response',[])
            tid=rows[0].get('team',{}).get('id') if rows else None
        except Exception:
            tid=None
    AF_CACHE[key]=tid
    return tid

def af_team_average(name):
    """Promedio real de córners y tarjetas en 3 partidos recientes de 2024.
    Se limita el número de consultas para respetar el plan gratuito."""
    key=('avg',name)
    if key in AF_CACHE: return AF_CACHE[key]
    tid=af_team_id(name)
    if not tid: return None
    try:
        rows=af_api_cached('/fixtures',{'team':tid,'season':2024}).get('response',[])
        rows=sorted([x for x in rows if x.get('fixture',{}).get('status',{}).get('short') in ('FT','AET','PEN')], key=lambda x:x.get('fixture',{}).get('date',''), reverse=True)[:3]
        totals=[]
        for row in rows:
            fid=row.get('fixture',{}).get('id')
            data=af_api_cached('/fixtures/statistics',{'fixture':fid})
            if data.get('errors'): continue
            corners=cards=0; has_corners=False; has_cards=False
            for team in data.get('response',[]):
                for item in team.get('statistics',[]):
                    typ=item.get('type'); val=item.get('value')
                    if isinstance(val,str):
                        try: val=float(val.replace('%',''))
                        except ValueError: val=None
                    if typ=='Corner Kicks' and isinstance(val,(int,float)):
                        corners+=val; has_corners=True
                    if typ in ('Yellow Cards','Red Cards') and isinstance(val,(int,float)):
                        cards+=val; has_cards=True
            if has_corners or has_cards: totals.append((corners if has_corners else None,cards if has_cards else None))
        if not totals: return None
        c=[x[0] for x in totals if x[0] is not None]; k=[x[1] for x in totals if x[1] is not None]
        result={'corners':round(sum(c)/len(c),1) if c else None,'cards':round(sum(k)/len(k),1) if k else None,'source':'API-Football · promedio 3 partidos'}
        AF_CACHE[key]=result
        return result
    except Exception:
        return None

def af_match_stats(home_name, away_name):
    h=af_team_average(home_name); a=af_team_average(away_name)
    if not h and not a: return None
    vals={}
    for field in ('corners','cards'):
        nums=[x[field] for x in (h,a) if x and x.get(field) is not None]
        if nums: vals[field]=round(sum(nums)/len(nums),1)
    vals['source']='API-Football · promedio histórico'
    return vals if any(k in vals for k in ('corners','cards')) else None

def live_data():
    global LIVE_CACHE
    now=time.time()
    if LIVE_CACHE['data'] is not None and now-LIVE_CACHE['at']<25:
        return LIVE_CACHE['data']
    start=date.today().isoformat(); end=(date.today()+timedelta(days=1)).isoformat()
    found={}; day_found={}
    # Football-Data devuelve algunos partidos como LIVE o FINISHED solo en
    # /competitions/{code}/matches, no en la consulta global de /matches.
    day_statuses=('SCHEDULED','LIVE','IN_PLAY','PAUSED','FINISHED')
    for code in LIVE_CODES:
        try:
            data=api('/competitions/%s/matches'%code,{'dateFrom':start,'dateTo':end,'limit':100})
            for m in data.get('matches',[]):
                if m.get('status') in day_statuses:
                    day_found[str(m.get('id'))]=m
                if m.get('status') in ('LIVE','IN_PLAY','PAUSED'):
                    found[str(m.get('id'))]=m
        except Exception:
            continue
    result={'matches':list(found.values()),'todayMatches':list(day_found.values()),'dateFrom':start,'dateTo':end,'source':'Football-Data.org · ligas en vivo'}
    LIVE_CACHE={'at':now,'data':result}
    return result

class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control','no-store, no-cache, must-revalidate, max-age=0')
        self.send_header('Pragma','no-cache')
        super().end_headers()

    def send_json(self,data,status=200):
        raw=json.dumps(data,ensure_ascii=False).encode(); self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(raw))); self.send_header('Access-Control-Allow-Origin','*'); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        try:
            p=urllib.parse.urlparse(self.path); q=urllib.parse.parse_qs(p.query)
            if p.path=='/api/competitions': self.send_json(api('/competitions')); return
            if p.path=='/api/teams': self.send_json(api('/competitions/%s/teams'%q['competition'][0])); return
            if p.path=='/api/matches':
                self.send_json(live_data()); return
            if p.path=='/api/upcoming':
                start=q.get('dateFrom',[date.today().isoformat()])[0]
                try: days=max(1,min(int(q.get('days',['7'])[0]),14))
                except (ValueError,TypeError): days=7
                try: start_date=date.fromisoformat(start)
                except ValueError: start_date=date.today(); start=start_date.isoformat()
                end=(start_date+timedelta(days=days-1)).isoformat()
                data=api('/matches',{'dateFrom':start,'dateTo':end,'status':'SCHEDULED','limit':100})
                data['dateFrom']=start; data['dateTo']=end; data['scope']='Todas las competiciones disponibles en Football-Data.org'
                self.send_json(data); return
            if p.path=='/api/today':
                start=q.get('date',[date.today().isoformat()])[0]
                data=api('/matches',{'dateFrom':start,'dateTo':start,'status':'SCHEDULED','limit':100})
                # Si un partido ya comenzó, deja de ser SCHEDULED y la
                # consulta general deja de devolverlo. Lo incluimos también
                # en los destacados de hoy, además de la pestaña En vivo.
                if start==date.today().isoformat():
                    day=live_data().get('todayMatches',[])
                    seen={str(m.get('id')) for m in data.get('matches',[])}
                    data.setdefault('matches',[]).extend(m for m in day if str(m.get('id')) not in seen)
                    data.setdefault('resultSet',{})['count']=len(data.get('matches',[]))
                data['dateFrom']=start; data['dateTo']=start; data['scope']='Partidos destacados del día'
                self.send_json(data); return
            if p.path=='/api/fixture':
                home=int(q['home'][0]); away=int(q['away'][0]); target=q.get('date',[None])[0]
                fixture=None
                if target:
                    data=api('/teams/%s/matches'%home,{'dateFrom':target,'dateTo':target,'limit':100})
                    for match in data.get('matches',[]):
                        if match.get('homeTeam',{}).get('id')==away or match.get('awayTeam',{}).get('id')==away:
                            fixture={'id':match.get('id'),'status':match.get('status'),'utcDate':match.get('utcDate'),'competition':match.get('competition',{}).get('name'),'score':match.get('score',{})}
                            break
                self.send_json({'fixture':fixture,'date':target}); return
            if p.path=='/api/analyze':
                home=int(q['home'][0]); away=int(q['away'][0]); target=q.get('date',[None])[0]; home_name=q.get('homeName',[''])[0]; away_name=q.get('awayName',[''])[0]
                # La fecha elegida identifica el partido a analizar; no debe
                # limitar el historial a esa fecha. Para un partido futuro,
                # usamos los últimos partidos terminados de ambos equipos.
                hist={'status':'FINISHED','limit':10}
                hm=api('/teams/%s/matches'%home,hist); am=api('/teams/%s/matches'%away,hist)
                history_season=None
                # Si la temporada actual aún no comenzó, usamos la anterior
                # para no fabricar estadísticas con valores de relleno.
                if not hm.get('matches') or not am.get('matches'):
                    try:
                        fallback_year=(int(target[:4])-1) if target else (date.today().year-1)
                        previous={'season':fallback_year,'status':'FINISHED','limit':10}
                        old_hm=api('/teams/%s/matches'%home,previous)
                        old_am=api('/teams/%s/matches'%away,previous)
                        if old_hm.get('matches') and old_am.get('matches'):
                            hm,am=old_hm,old_am
                            history_season=fallback_year
                    except (ValueError, TypeError):
                        pass
                fixture=None
                if target:
                    try:
                        fixture_data=api('/teams/%s/matches'%home,{'dateFrom':target,'dateTo':target,'limit':100})
                        for match in fixture_data.get('matches',[]):
                            if match.get('homeTeam',{}).get('id')==away or match.get('awayTeam',{}).get('id')==away:
                                fixture={'id':match.get('id'),'status':match.get('status'),'utcDate':match.get('utcDate'),'competition':match.get('competition',{}).get('name'),'score':match.get('score',{})}
                                break
                    except Exception:
                        fixture=None
                def stats(data,team):
                    gf=ga=wins=draws=losses=clean=failed=over15=over25=btts=first_half_goals=n=0
                    form=[]
                    for m in data.get('matches',[]):
                        sc=m.get('score',{}); ft=sc.get('fullTime',{}); hg=ft.get('home'); ag=ft.get('away')
                        if hg is None or ag is None: continue
                        n+=1; ish=m.get('homeTeam',{}).get('id')==team
                        team_gf=hg if ish else ag; team_ga=ag if ish else hg
                        gf+=team_gf; ga+=team_ga
                        if team_gf>team_ga: wins+=1; form.append('G')
                        elif team_gf==team_ga: draws+=1; form.append('E')
                        else: losses+=1; form.append('P')
                        clean+=team_ga==0; failed+=team_gf==0
                        over15+=(hg+ag)>1; over25+=(hg+ag)>2
                        btts+=(hg>0 and ag>0)
                        half=sc.get('halfTime',{}); first_half_goals+=(half.get('home') or 0)+(half.get('away') or 0)
                    return {'matches':n,'gf':gf/n if n else 1.2,'ga':ga/n if n else 1.2,'wins':wins,'draws':draws,'losses':losses,'cleanSheets':clean,'failedToScore':failed,'over15':round(over15*100/n,1) if n else None,'over25':round(over25*100/n,1) if n else None,'btts':round(btts*100/n,1) if n else None,'firstHalfGoals':round(first_half_goals/n,2) if n else None,'form':'-'.join(form[-5:])}
                hs,avs=stats(hm,home),stats(am,away)
                if hs['matches']==0 or avs['matches']==0:
                    self.send_json({'homeMatches':hm.get('matches',[]),'awayMatches':am.get('matches',[]),'engine':{'sampleSize':hs['matches']+avs['matches'],'dataAvailable':False,'historySeason':history_season,'date':target,'fixture':fixture,'historySeason':history_season,'method':'Poisson sobre promedios recientes'}}); return
                lx=max(.15,(hs['gf']+avs['ga'])/2); ax=max(.15,(avs['gf']+hs['ga'])/2)
                def pois(l,k): return math.exp(-l)*l**k/math.factorial(k)
                probs={(i,j):pois(lx,i)*pois(ax,j) for i in range(8) for j in range(8)}; total=sum(probs.values()); hp=sum(v for (i,j),v in probs.items() if i>j)/total; dp=sum(v for (i,j),v in probs.items() if i==j)/total; ap=sum(v for (i,j),v in probs.items() if i<j)/total; o15=1-sum(v for (i,j),v in probs.items() if i+j<=1)/total; o25=1-sum(v for (i,j),v in probs.items() if i+j<=2)/total; u25=1-o25; btts=sum(v for (i,j),v in probs.items() if i>0 and j>0)/total; ex=max(probs,key=probs.get)
                outcomes=[('Local',hp),('Empate',dp),('Visitante',ap)]; signal,signal_prob=max(outcomes,key=lambda x:x[1]); sample=hs['matches']+avs['matches']; confidence='Alta' if signal_prob>=.67 and sample>=8 else ('Media' if signal_prob>=.52 else 'Baja')
                home_rate=hs['wins']/hs['matches']; away_rate=avs['wins']/avs['matches']; reasons=[]
                if home_rate>away_rate+.15: reasons.append('El local llega con mejor tasa de victorias reciente.')
                elif away_rate>home_rate+.15: reasons.append('El visitante llega con mejor tasa de victorias reciente.')
                if lx>ax+.35: reasons.append('El modelo proyecta más goles para el equipo local.')
                elif ax>lx+.35: reasons.append('El modelo proyecta más goles para el equipo visitante.')
                if hs['ga']<avs['ga']-.35: reasons.append('El local viene defendiendo mejor.')
                elif avs['ga']<hs['ga']-.35: reasons.append('El visitante viene defendiendo mejor.')
                if not reasons: reasons.append('Los datos recientes muestran una tendencia equilibrada.')
                af_stats=af_match_stats(home_name,away_name)
                self.send_json({'homeMatches':hm.get('matches',[]),'awayMatches':am.get('matches',[]),'engine':{'sampleSize':hs['matches']+avs['matches'],'probabilities':{'home':round(hp*100,1),'draw':round(dp*100,1),'away':round(ap*100,1),'over1_5':round(o15*100,1),'over2_5':round(o25*100,1),'under2_5':round(u25*100,1),'btts':round(btts*100,1)},'expectedGoals':{'home':round(lx,2),'away':round(ax,2),'total':round(lx+ax,2)},'mostLikelyScore':f'{ex[0]}-{ex[1]}','summary':{'signal':signal,'probability':round(signal_prob*100,1),'confidence':confidence,'reasons':reasons[:3]},'corners':af_stats.get('corners') if af_stats else None,'cards':af_stats.get('cards') if af_stats else None,'statsSource':af_stats.get('source') if af_stats else None,'history':{'home':hs,'away':avs},'date':target,'fixture':fixture,'historySeason':history_season,'method':'Poisson sobre promedios recientes'}}); return
            return SimpleHTTPRequestHandler.do_GET(self)
        except Exception as e: self.send_json({'error':'No se pudo consultar Football-Data.org','detail':str(e)},502)
if __name__=='__main__':
    port=int(os.environ.get('PORT','10000')); print('ParleyStats en puerto',port); ThreadingHTTPServer(('0.0.0.0',port),Handler).serve_forever()
