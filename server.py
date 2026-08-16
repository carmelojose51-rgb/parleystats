#!/usr/bin/env python3
import json, os, math, time, threading, urllib.parse, urllib.request, urllib.error
from datetime import date, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
TOKEN = os.environ.get('FOOTBALL_DATA_API_TOKEN')
ALLOWED_ORIGINS = {x.strip() for x in os.environ.get('ALLOWED_ORIGINS', 'https://carmelojose51-rgb.github.io,http://localhost:8080,http://127.0.0.1:8080').split(',') if x.strip()}
RATE_LIMITS = {'/api/analyze': 12, '/api/fixture': 60, '/api/teams': 60, '/api/competitions': 30, '/api/upcoming': 30, '/api/today': 30, '/api/matches': 60}
RATE_WINDOW = {}
RATE_LOCK = threading.Lock()
BASE = 'https://api.football-data.org/v4'
FD_CACHE={}
def fd_cache_ttl(path, params):
    params=params or {}
    if path=='/competitions' or path.endswith('/teams'):
        return 900
    if '/matches' in path:
        if params.get('status')=='FINISHED' or 'season' in params:
            return 600
        if 'dateFrom' in params or 'dateTo' in params:
            return 45
        return 30
    return 300

def api(path, params=None):
    params=params or {}; key=(path,tuple(sorted(params.items()))); now=time.time(); cached=FD_CACHE.get(key); ttl=fd_cache_ttl(path,params)
    if cached and now-cached[0]<ttl: return cached[1]
    url=BASE+path
    if params: url+='?'+urllib.parse.urlencode(params)
    req=urllib.request.Request(url, headers={'X-Auth-Token':TOKEN or ''})
    try:
        with urllib.request.urlopen(req,timeout=10) as r: data=json.load(r)
        FD_CACHE[key]=(now,data)
        return data
    except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError):
        # Si el proveedor limita temporalmente las consultas, reutilizamos el
        # último dato válido en vez de dejar toda la aplicación en error.
        if cached: return cached[1]
        raise
LIVE_CACHE={'at':0,'data':None}
LIVE_REFRESH_LOCK=threading.Lock()
def refresh_live_async():
    # Actualiza partidos en segundo plano después de despertar Render.
    if not LIVE_REFRESH_LOCK.acquire(blocking=False): return
    def run():
        try: live_data()
        finally: LIVE_REFRESH_LOCK.release()
    threading.Thread(target=run,daemon=True).start()

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
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','strict-origin-when-cross-origin')
        self.send_header('Permissions-Policy','camera=(), microphone=(), geolocation=()')
        super().end_headers()

    def client_key(self):
        # Render puede poner la IP original en X-Forwarded-For. Solo se usa
        # para limitar abusos; no se guarda en disco ni se devuelve al cliente.
        return (self.headers.get('X-Forwarded-For','').split(',')[0].strip() or self.client_address[0])[:80]

    def rate_allowed(self,path):
        limit=RATE_LIMITS.get(path)
        if not limit: return True
        now=time.time(); key=(self.client_key(),path)
        with RATE_LOCK:
            hits=[t for t in RATE_WINDOW.get(key,[]) if now-t<60]
            if len(hits)>=limit:
                RATE_WINDOW[key]=hits
                return False
            hits.append(now); RATE_WINDOW[key]=hits
            # Limpieza pequeña para que la memoria no crezca sin límite.
            if len(RATE_WINDOW)>2000:
                for k in list(RATE_WINDOW)[:500]: RATE_WINDOW.pop(k,None)
        return True

    def send_json(self,data,status=200):
        raw=json.dumps(data,ensure_ascii=False).encode(); self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(raw)))
        origin=self.headers.get('Origin')
        if origin in ALLOWED_ORIGINS:
            self.send_header('Access-Control-Allow-Origin',origin); self.send_header('Vary','Origin')
        self.end_headers(); self.wfile.write(raw)

    def do_OPTIONS(self):
        origin=self.headers.get('Origin')
        self.send_response(204)
        if origin in ALLOWED_ORIGINS:
            self.send_header('Access-Control-Allow-Origin',origin); self.send_header('Vary','Origin')
        self.send_header('Access-Control-Allow-Methods','GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers','Content-Type')
        self.end_headers()

    def do_GET(self):
        try:
            p=urllib.parse.urlparse(self.path); q=urllib.parse.parse_qs(p.query)
            if p.path.startswith('/api/') and not self.rate_allowed(p.path):
                self.send_json({'error':'Límite temporal de consultas alcanzado. Intenta nuevamente en un minuto.'},429); return
            if p.path=='/api/competitions': self.send_json(api('/competitions')); return
            if p.path=='/api/teams':
                competition=q.get('competition',[''])[0]
                if not competition.isdigit(): self.send_json({'error':'Competición no válida.'},400); return
                self.send_json(api('/competitions/%s/teams'%competition)); return
            if p.path=='/api/matches':
                # En una instancia recién despertada no esperamos las consultas
                # de todas las ligas: respondemos rápido y actualizamos en segundo plano.
                now=time.time()
                if LIVE_CACHE['data'] is None or now-LIVE_CACHE['at']>=25:
                    refresh_live_async()
                    self.send_json(LIVE_CACHE['data'] or {'matches':[],'loading':True,'source':'Football-Data.org'}); return
                self.send_json(LIVE_CACHE['data']); return
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
                try:
                    data=api('/matches',{'dateFrom':start,'dateTo':start,'limit':100})
                    if data.get('errorCode'): raise RuntimeError('all-day query unavailable')
                except Exception:
                    # Algunas cuentas de Football-Data solo permiten la
                    # consulta de programados; usamos ese resultado como
                    # respaldo y añadimos los partidos en vivo aparte.
                    try:
                        data=api('/matches',{'dateFrom':start,'dateTo':start,'status':'SCHEDULED','limit':100})
                    except Exception:
                        data={'matches':[],'resultSet':{'count':0},'filters':{'dateFrom':start,'dateTo':start},'degraded':True}
                # Si un partido ya comenzó, deja de ser SCHEDULED y la
                # consulta general deja de devolverlo. Lo incluimos también
                # en los destacados de hoy, además de la pestaña En vivo.
                if start==date.today().isoformat():
                    # Los partidos programados se entregan de inmediato.
                    # La búsqueda adicional de partidos en vivo se actualiza
                    # en segundo plano para que una instancia dormida no deje
                    # la pantalla cargando durante minutos.
                    if LIVE_CACHE['data'] is None or time.time()-LIVE_CACHE['at']>=25:
                        refresh_live_async()
                        day=[]
                    else:
                        day=LIVE_CACHE['data'].get('todayMatches',[])
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
                # Si un equipo tiene menos de 10 partidos terminados en la
                # temporada actual, completamos su muestra con la temporada
                # anterior. Se hace por equipo, no solo cuando ambos están
                # cortos, para que todos los análisis tengan una muestra útil.
                try:
                    fallback_year=(int(target[:4])-1) if target else (date.today().year-1)
                    previous={'season':fallback_year,'status':'FINISHED','limit':10}
                    def complete_history(team_id,current):
                        rows=list(current.get('matches') or [])
                        if len(rows)>=10:return current,False
                        old=api('/teams/%s/matches'%team_id,previous)
                        seen={str(x.get('id')) for x in rows}
                        for match in old.get('matches') or []:
                            if str(match.get('id')) not in seen:
                                rows.append(match);seen.add(str(match.get('id')))
                        rows.sort(key=lambda x:str(x.get('utcDate') or ''),reverse=True)
                        result=dict(current);result['matches']=rows[:10]
                        return result,len(rows)>len(current.get('matches') or [])
                    hm,used_h=complete_history(home,hm)
                    am,used_a=complete_history(away,am)
                    if used_h or used_a:history_season=f'Actual + {fallback_year}'
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
                self.send_json({'homeMatches':hm.get('matches',[]),'awayMatches':am.get('matches',[]),'engine':{'sampleSize':hs['matches']+avs['matches'],'probabilities':{'home':round(hp*100,1),'draw':round(dp*100,1),'away':round(ap*100,1),'over1_5':round(o15*100,1),'over2_5':round(o25*100,1),'under2_5':round(u25*100,1),'btts':round(btts*100,1)},'expectedGoals':{'home':round(lx,2),'away':round(ax,2),'total':round(lx+ax,2)},'mostLikelyScore':f'{ex[0]}-{ex[1]}','summary':{'signal':signal,'probability':round(signal_prob*100,1),'confidence':confidence,'reasons':reasons[:3]},'history':{'home':hs,'away':avs},'date':target,'fixture':fixture,'historySeason':history_season,'method':'Poisson sobre promedios recientes'}}); return
            return SimpleHTTPRequestHandler.do_GET(self)
        except Exception as e:
            print('Request error:', repr(e))
            self.send_json({'error':'No se pudo completar la consulta. Intenta nuevamente.'},502)
if __name__=='__main__':
    port=int(os.environ.get('PORT','10000')); print('ParleyStats en puerto',port); ThreadingHTTPServer(('0.0.0.0',port),Handler).serve_forever()
