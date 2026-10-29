#!/usr/bin/env python3
import json, os, math, time, threading, urllib.parse, urllib.request, urllib.error
from datetime import date, timedelta, datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from concurrent.futures import ThreadPoolExecutor, as_completed
TOKEN = os.environ.get('FOOTBALL_DATA_API_TOKEN')
ALLOWED_ORIGINS = {x.strip() for x in os.environ.get('ALLOWED_ORIGINS', 'https://carmelojose51-rgb.github.io,http://localhost:8080,http://127.0.0.1:8080').split(',') if x.strip()}
RATE_LIMITS = {'/api/analyze': 12, '/api/fixture': 60, '/api/teams': 60, '/api/competitions': 30, '/api/upcoming': 30, '/api/today': 30, '/api/matches': 60}
RATE_WINDOW = {}
RATE_LOCK = threading.Lock()
BASE = 'https://api.football-data.org/v4'
FD_CACHE={}
GOAL_BASE='https://api.goal-api.com/v1'
GOAL_TOKEN=os.environ.get('GOAL_API_KEY','').strip()
GOAL_LEAGUES={
    'cmr77dvv600aprx06o7y7lnfu':{'apiId':'120','name':'Liga BetPlay','country':'Colombia'},
    'cmr77dvtc0093rx0667jirsnv':{'apiId':'44','name':'Liga Profesional Argentina','country':'Argentina'},
    'cmr77dvsv008srx06mier6t7r':{'apiId':'235','name':'Liga MX','country':'Mexico'},
    'cmr77dvtx009krx06tw1t8obh':{'apiId':'332','name':'MLS','country':'Estados Unidos'},
    'cmr77dw9g00gvrx06jlglb47m':{'apiId':'63','name':'Jupiler Pro League','country':'Bélgica'},
    'cmr77dx7h00rvrx060kholaxg':{'apiId':'209','name':'J1 League','country':'Japón'},
    'cmr77dw0q00eprx06rqew3m48':{'apiId':'322','name':'Süper Lig','country':'Turquía'},
    'cmr77dx9n00t7rx06xn1yyux7':{'apiId':'38','name':'Girabola','country':'Angola'},
    'cmr77dwa300hcrx06k4a5z7z4':{'apiId':'124','name':'HNL','country':'Croatia'},
    'cmr77dw8j00ghrx06n38ittl6':{'apiId':'263','name':'I Liga','country':'Poland'},
    'cmr77dxa700terx06zygnd5xe':{'apiId':'495','name':'Iraqi League','country':'Iraq'},
    'cmr77dx7h00rwrx06amhce4w6':{'apiId':'212','name':'J2 League','country':'Japan'},
    'cmr77dx7h00rxrx061056aesh':{'apiId':'601','name':'J3 League','country':'Japan'},
    'cmr77dvsf008lrx06l2d31exu':{'apiId':'219','name':'K League 1','country':'Korea Republic'},
    'cmr77dvsf008orx064ksccykp':{'apiId':'217','name':'K3 League','country':'Korea Republic'},
    'cmr77dxae00tgrx06wansed1u':{'apiId':'160','name':'Kakkonen','country':'Finland'},
    'cmr77dvqg007frx06bkwepdbh':{'apiId':'167','name':'National 1','country':'France'},
    'cmr77dx2t00q2rx06gam3mjad':{'apiId':'228','name':'National Division','country':'Luxembourg'},
    'cmr77dvks005srx0690qr2qya':{'apiId':'151','name':'National League','country':'England'},
    'cmr77dwdf00j0rx06fq8i1i8a':{'apiId':'324','name':'Persha Liga','country':'Ukraine'},
    'cmr77dwp200mrrx06bg1xzttm':{'apiId':'195','name':'Persian Gulf Pro League','country':'Iran'},
    'cmr77dx9300szrx06xqoqq57b':{'apiId':'200','name':'Premier Division','country':'Republic of Ireland'},
    'cmr49zld10004p407pro8z6up':{'apiId':'177','name':'Premier League','country':'Ghana'},
    'cmr77dwca00ikrx06cf0v2gih':{'apiId':'61','name':'Premier League','country':'Belarus'},
    'cmr77dvit0052rx06pj7safds':{'apiId':'307','name':'Allsvenskan','country':'Sweden'},
    'cmr77dwp200mprx0641skuthc':{'apiId':'196','name':'Azadegan League','country':'Iran'},
    'cmr77dwhd00kgrx06s7jzkv71':{'apiId':'192','name':'Besta deild','country':'Iceland'},
    'cmr77dw7800g9rx06v6a4zya0':{'apiId':'239','name':'Botola Pro','country':'Morocco'},
    'cmr77dvjm005brx062i1cpb4k':{'apiId':'56','name':'Bundesliga','country':'Austria'},
    'cmr77dwd000irrx06go0ax033':{'apiId':'141','name':'Premier League','country':'Egypt'},
    'cmr77dwjp00kwrx06plbjknnn':{'apiId':'214','name':'Premier League','country':'Kazakhstan'},
    'cmr77dxg200vmrx06xqb9o9dx':{'apiId':'550','name':'Premier League','country':'Rwanda'},
    'cmr77dxg800vorx064qptijld':{'apiId':'555','name':'Premier League','country':'Uganda'},
    'cmr77dxgg00vqrx06ufcdpoei':{'apiId':'556','name':'Premier League','country':'Ethiopia'},
    'cmr77dwuo00nqrx06v4rpsuzk':{'apiId':'251','name':'Premiership','country':'Northern Ireland'},
    'cmr77dxi400w7rx06lxedeerx':{'apiId':'70','name':'Premijer Liga','country':'Bosnia and Herzegovina and Herzegovina'},
    'cmr77dwpr00mwrx063m9vbhjq':{'apiId':'57','name':'Premyer Liqa','country':'Azerbaijan'},
    'cmr77dvtd0096rx06pa3n61ep':{'apiId':'40','name':'Prim B Metro','country':'Argentina'},
    'cmr77dwca00ilrx06jmjey2ig':{'apiId':'62','name':'1. Division','country':'Belarus'},
    'cmr77dwj200korx0664b8h5mq':{'apiId':'130','name':'1. Division','country':'Cyprus'},
    'cmr77dw0q00eqrx06ekzy1wgb':{'apiId':'319','name':'1. Lig','country':'Turkey'},
    'cmr77dvyx00eirx06a7ydr2z0':{'apiId':'523','name':'1. Liga Promotion','country':'Switzerland'},
    'cmr77dw6e00g4rx066l7qly13':{'apiId':'296','name':'1. SNL','country':'Slovenia'},
    'cmr77dw5l00fyrx064o73i0dp':{'apiId':'293','name':'1. liga','country':'Slovakia'},
    'cmr77dwby00idrx06o72wh203':{'apiId':'530','name':'1st Division','country':'South Africa'},
    'cmr77dwl600l9rx06k6u4zx60':{'apiId':'32','name':'1st Division','country':'Albania'},
    'cmr77dwli00lfrx06n4jjveg8':{'apiId':'71','name':'1st League','country':'Bosnia and Herzegovina'},
    'cmr77dwgp00k5rx06ngnyuofo':{'apiId':'227','name':'A Lyga','country':'Lithuania'},
    'cmr77dvr4007orx06xi4ehckz':{'apiId':'363','name':'2. Division','country':'Norway'},
    'cmr77dw1z00ezrx06to1e7l5e':{'apiId':'136','name':'2. Division','country':'Denmark'},
    'cmr77dwj200kprx06pf3v3g9j':{'apiId':'129','name':'2. Division','country':'Cyprus'},
    'cmr77dvjm005crx06q7yo5093':{'apiId':'53','name':'2. Liga','country':'Austria'},
    'cmr77dw6e00g5rx06ai7a4owy':{'apiId':'294','name':'2. SNL','country':'Slovenia'},
    'cmr77dw5m00fzrx06o9ws0wqz':{'apiId':'420','name':'2. liga','country':'Slovakia'},
    'cmr77dvgm0005rx06zza2b9mt':{'apiId':'176','name':'3. Liga','country':'Germany'},
    'cmr77dw9200gmrx06o9tqq555':{'apiId':'134','name':'Czech Liga','country':'Czech Republic'},
    'cmr77dvw600bbrx06rmb6ee0h':{'apiId':'277','name':'Division 1','country':'Saudi Arabia'},
    'cmr77dwy000omrx06iy4p4c3t':{'apiId':'256','name':'Division Intermedia','country':'Paraguay'},
    'cmr77dwy000onrx06oqbv0dbl':{'apiId':'255','name':'Division Profesional','country':'Paraguay'},
    'cmr77dwdf00izrx06k9r7w272':{'apiId':'327','name':'Druha Liga','country':'Ukraine'},
    'cmr77dvyx00egrx06pta3wmnc':{'apiId':'308','name':'Super League','country':'Switzerland'},
    'cmr77dx4f00qnrx063ai480br':{'apiId':'335','name':'Super League','country':'Uzbekistan'},
    'cmr77dx9b00t3rx06r8k9c374':{'apiId':'7543','name':'Super League','country':'Kenya'},
    'cmr77dxjj00wprx06nwoi6iti':{'apiId':'342','name':'Super League','country':'Zambia'},
    'cmr77dwfb00jmrx06oapyzogf':{'apiId':'178','name':'Super League 1','country':'Greece'},
    'cmr77dwfu00jsrx06lzqv6ouq':{'apiId':'288','name':'Super Liga','country':'Serbia'},
    'cmr77dvit0057rx06s7xypict':{'apiId':'305','name':'Superettan','country':'Sweden'},
    'cmr77dw1z00exrx062x6co26u':{'apiId':'135','name':'Superliga','country':'Denmark'},
    'cmr77dwl600ldrx06r1iqjfy6':{'apiId':'31','name':'Superliga','country':'Albania'},
    'cmr77dwae00hjrx061fdxl3eb':{'apiId':'194','name':'Liga 1','country':'Indonesia'},
    'cmr77dwar00horx06biku04et':{'apiId':'272','name':'Liga I','country':'Romania'},
    'cmr77dwbd00i2rx06ts2f2tor':{'apiId':'201','name':'Liga Leumit','country':'Israel'},
    'cmr77dxay00tvrx068w5v6fip':{'apiId':'182','name':'Liga Nacional','country':'Guatemala'},
    'cmr77dwb200hvrx06199fst9o':{'apiId':'140','name':'Liga Pro','country':'Ecuador'},
    'cmr77dwvj00o3rx06nmp4s8pg':{'apiId':'122','name':'Liga de Ascenso','country':'Costa Rica'},
    'cmr77dvsv008vrx0662qxeebf':{'apiId':'236','name':'Liga de Expansión MX','country':'Mexico'},
    'cmr77dwbc00i0rx06adepi1hb':{'apiId':'202','name':'Ligat Ha\'al','country':'Israel'},
    'cmr77dxbb00u0rx06vqu9f3rk':{'apiId':'551','name':'Ligi kuu Bara','country':'Tanzania'},
    'cmr77dx0200p5rx066psribbn':{'apiId':'34','name':'Ligue 1','country':'Algeria'},
    'cmr77dx4200qhrx069ia9gdbp':{'apiId':'317','name':'Ligue 1','country':'Tunisia'},
    'cmr77dxbp00u4rx069v76fl73':{'apiId':'417','name':'Ligue 1','country':'Congo DR'},
    'cmr77dxc700uarx06ui7ayv2e':{'apiId':'554','name':'Ligue 1','country':'Burkina Faso'},
    'cmr77dvtx009mrx067ag18o0g':{'apiId':'7097','name':'MLS Next Pro','country':'USA'},
    'cmr77dx1r00porx06tvpfwl68':{'apiId':'156','name':'Meistriliiga','country':'Estonia'},
    'cmr77dwbn00i7rx06ll8ra8w3':{'apiId':'191','name':'NB I','country':'Hungary'},
    'cmr77dxdp00urrx06pmkuqz1e':{'apiId':'248','name':'NPFL','country':'Nigeria'},
    'cmr77dwgb00jxrx067wx4esvl':{'apiId':'314','name':'Thai League 1','country':'Thailand'},
    'cmr77dvtd009erx06h8rn5zru':{'apiId':'39','name':'Torneo Federal A','country':'Argentina'},
    'cmr77dvtd009hrx06bys03xaz':{'apiId':'7096','name':'Torneo Proyección','country':'Argentina'},
    'cmr77dvrh0083rx061hkptk8k':{'apiId':'584','name':'Tweede Divisie','country':'Netherlands'},
    'cmr77dvtx009wrx06v051zw0d':{'apiId':'330','name':'USL Championship','country':'USA'},
    'cmr77dwk900l2rx06i99xreez':{'apiId':'223','name':'Virsliga','country':'Latvia'},
    'cmr77dvua00a4rx061d2jre7p':{'apiId':'344','name':'Premier League','country':'Russia'},
    'cmr77dwdf00ixrx06z6havnxo':{'apiId':'325','name':'Premier League','country':'Ukraine'},
    'cmr77dwe100j5rx064jkxo63c':{'apiId':'279','name':'Premiership','country':'Scotland'},
    'cmr77dw8j00girx06rxwz4kx7':{'apiId':'261','name':'II Liga','country':'Poland'},
    'cmr77dvsf008mrx06w9kcdv5a':{'apiId':'218','name':'K League 2','country':'Korea Republic'},
    'cmr77dvkr005lrx061tywzotk':{'apiId':'154','name':'League One','country':'England'},
    'cmr77dvkr005mrx06iayzvq2w':{'apiId':'145','name':'League Two','country':'England'},
    'cmr77dvun00akrx06n1h7f19s':{'apiId':'699','name':'Liga 3','country':'Portugal'},
    'cmr77dwar00hrrx06khykfdwd':{'apiId':'271','name':'Liga II','country':'Romania'},
    'cmr77dvqg007drx06q6y56j5u':{'apiId':'164','name':'Ligue 2','country':'France'},
    'cmr77dx4200qirx06cwddzkjp':{'apiId':'316','name':'Ligue 2','country':'Tunisia'},
    'cmr77dwbn00i9rx06526cm2s7':{'apiId':'188','name':'NB II','country':'Hungary'},
    'cmr77dvks005xrx065y7bx5oh':{'apiId':'593','name':'Premier League 2','country':'England'},
    'cmr77dwd000iurx06wwusub10':{'apiId':'701','name':'Second Division A','country':'Egypt'},
    'cmr77dvun00afrx064ci6r3pk':{'apiId':'267','name':'Segunda Liga','country':'Portugal'},
    'cmr77dvww00bgrx06cb9fmnv0':{'apiId':'75','name':'Serie B','country':'Brazil'},
    'cmr77dvxw00earx06esy4oem6':{'apiId':'79','name':'Serie C','country':'Brazil'},
    'cmr77dwfb00jqrx06qci3nyj2':{'apiId':'439','name':'Super League 2','country':'Greece'},
    'cmr77dwgb00k2rx06b3vu93ne':{'apiId':'602','name':'Thai League 2','country':'Thailand'},
    'cmr77dwqp00myrx069ta1zgd7':{'apiId':'276','name':'Campionato','country':'San Marino'},
    'cmr77dw9g00gwrx06o5ldgzbc':{'apiId':'65','name':'Challenger Pro League','country':'Belgium'},
    'cmr77dwu700nhrx06tim1qnw5':{'apiId':'549','name':'Championnat National','country':'Benin'},
    'cmr77dwun00nlrx062m7s5adr':{'apiId':'250','name':'Championship','country':'Northern Ireland'},
    'cmr77dvlv0067rx06potai161':{'apiId':'118','name':'Chinese Super League','country':'China PR'},
    'cmr77dw7800garx06afr5or3k':{'apiId':'241','name':'Botola 2','country':'Morocco'},
    'cmr77dvlv0068rx0671n8gduz':{'apiId':'117','name':'China League One','country':'China PR'},
    'cmr77dx6300r8rx06q7izzmnr':{'apiId':'169','name':'Erovnuli Liga 2','country':'Georgia'},
    'cmr77dvrh007yrx06tn0odxar':{'apiId':'245','name':'Eerste Divisie','country':'Netherlands'},
    'cmr77dw8j00gerx06xvshbkow':{'apiId':'259','name':'Ekstraklasa','country':'Poland'},
    'cmr77dvr3007lrx061vsn0yjt':{'apiId':'253','name':'Eliteserien','country':'Norway'},
    'cmr77dx6300r7rx06cupwh420':{'apiId':'170','name':'Erovnuli Liga','country':'Georgia'},
    'cmr77dvit0056rx06kaf7kyjd':{'apiId':'366','name':'Ettan','country':'Sweden'},
    'cmr77dx9b00t1rx06yrhxo12z':{'apiId':'216','name':'FKF Premier League','country':'Kenya'},
    'cmr77dw9200gsrx06wxmagx8o':{'apiId':'133','name':'FNL','country':'Czech Republic'},
    'cmr77dvua00a6rx0646k487gf':{'apiId':'274','name':'First League','country':'Russia'},
    'cmr77dw9r00h6rx06fol99vnt':{'apiId':'111','name':'First League','country':'Bulgaria'},
    'cmr77dx3200q5rx061z6mf2q2':{'apiId':'230','name':'First League','country':'North Macedonia'},
    'cmr77dwa300herx0612xycox0':{'apiId':'127','name':'First NL','country':'Croatia'},
    'cmr77dvgm0001rx060h6ivt4p':{'apiId':'171','name':'2. Bundesliga','country':'Germany'},
    'cmr77dvnt006orx06io7l06lv':{'apiId':'301','name':'Segunda División','country':'Spain'},
    'cmr77dvpd006zrx06dmggkel8':{'apiId':'206','name':'Serie B','country':'Italy'},
    'cmr77dvv600asrx06y051mw74':{'apiId':'517','name':'Primera B','country':'Colombia'},
    'cmr77dvvi00axrx06sjsji50a':{'apiId':'116','name':'Primera B','country':'Chile'},
    'cmr77dvtd0098rx06ocrb4lit':{'apiId':'42','name':'Primera C','country':'Argentina'},
    'cmr77dxig00wbrx06ivt8vmh0':{'apiId':'142','name':'Primera Division','country':'El Salvador'},
    'cmr77dvvh00avrx06jb5gtua7':{'apiId':'115','name':'Primera División','country':'Chile'},
    'cmr77dvvu00b1rx06plolocbg':{'apiId':'257','name':'Primera División','country':'Peru'},
    'cmr77dwvj00o4rx06obpfwwsh':{'apiId':'121','name':'Primera División','country':'Costa Rica'},
    'cmr77dww100obrx06s4u95lak':{'apiId':'69','name':'Primera División','country':'Bolivia'},
    'cmr77dwyu00ourx06onlk5cms':{'apiId':'333','name':'Primera División','country':'Uruguay'},
    'cmr77dwzc00ozrx067jdulclt':{'apiId':'337','name':'Primera División','country':'Venezuela'},
    'cmr77dvtd009arx06r01ub8mw':{'apiId':'41','name':'Primera Nacional','country':'Argentina'},
    'cmr77dwfu00jurx06dfj7qssu':{'apiId':'287','name':'Prva Liga','country':'Serbia'},
    'cmr77dvw600b9rx06euixf818':{'apiId':'278','name':'Saudi League','country':'Saudi Arabia'},
    'cmr77dw9r00h8rx0694urkuie':{'apiId':'109','name':'Second League','country':'Bulgaria'},
    'cmr77dx3200q6rx06fcpcukwd':{'apiId':'229','name':'Second League','country':'North Macedonia'},
    'cmr77dvua00a8rx06s1sytscc':{'apiId':'273','name':'Second League B','country':'Russia'},
}
GOAL_LEAGUE_ID='cmr77dvv600aprx06o7y7lnfu'
GOAL_LEAGUE_API_ID='120'
GOAL_LEAGUE_LABEL='Liga BetPlay (GOAL API)'
GOAL_DAILY_RESERVE=200
GOAL_LOCAL_BUDGET=800
GOAL_CACHE={}
GOAL_LOCK=threading.RLock()
GOAL_QUOTA={'date':None,'used':0,'remaining':None,'reset':None,'known':False}

def goal_cache_ttl(path,params):
    if path=='/leagues':return 21600
    if path.endswith('/teams'):return 21600
    if '/teams/' in path and path.endswith('/fixtures'):return 180
    if '/leagues/' in path and path.endswith('/fixtures'):return 300
    if path.startswith('/fixtures/'):return 300
    return 300

def goal_api(path,params=None,force=False):
    if not GOAL_TOKEN:raise RuntimeError('GOAL API no está configurada')
    params=params or {}; key=(path,tuple(sorted((str(k),str(v)) for k,v in params.items())))
    now=time.time()
    # Reservamos cuota y consultamos caché bajo lock, pero jamás retenemos el
    # lock durante I/O de red: así las consultas independientes sí corren juntas.
    with GOAL_LOCK:
        reset_at=GOAL_QUOTA.get('reset')
        if reset_at and now>=reset_at:
            GOAL_QUOTA.update(date=datetime.fromtimestamp(reset_at,timezone.utc).date().isoformat(),used=0,remaining=None,reset=None,known=False)
        cached=GOAL_CACHE.get(key); ttl=goal_cache_ttl(path,params)
        if cached and now-cached[0]<ttl:return cached[1]
        if GOAL_QUOTA['known'] and (GOAL_QUOTA['used']>=GOAL_LOCAL_BUDGET or (GOAL_QUOTA['remaining'] is not None and GOAL_QUOTA['remaining']<=GOAL_DAILY_RESERVE)):
            raise RuntimeError('GOAL API alcanzó el umbral preventivo de consultas diarias; se conserva la cuota restante')
        GOAL_QUOTA['used']+=1
    url=GOAL_BASE+path
    if params:url+='?'+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={'Authorization':'Bearer '+GOAL_TOKEN,'Accept':'application/json','User-Agent':'ParleyStats/1.0'})
    try:
        with urllib.request.urlopen(req,timeout=15) as r:
            data=json.load(r); remaining=r.headers.get('X-RateLimit-Remaining'); reset=r.headers.get('X-RateLimit-Reset')
        if not data.get('success',True):raise RuntimeError(data.get('message') or 'GOAL API request failed')
        with GOAL_LOCK:
            if remaining is not None:GOAL_QUOTA['remaining']=int(remaining); GOAL_QUOTA['known']=True
            if reset is not None:GOAL_QUOTA['reset']=int(reset); GOAL_QUOTA['date']=datetime.fromtimestamp(int(reset),timezone.utc).date().isoformat()
            GOAL_CACHE[key]=(time.time(),data)
        return data
    except Exception:
        # Conservatively retain the request in the local budget: uncertain responses may count.
        raise

def goal_prefix(value):return str(value or '').startswith('goal:')
def goal_raw(value):return str(value or '')[5:] if goal_prefix(value) else str(value or '')
def goal_normalize_match(m):
    status=str(m.get('matchStatus') or '').upper()
    if status in ('AFTER_PEN','AFTER_EXTRA_TIME','AET','PEN'):status='FINISHED'
    def score(v):
        try:return int(v) if v is not None and str(v).strip()!='' else None
        except (ValueError,TypeError):return None
    hg=score(m.get('homeTeamFtScore')); ag=score(m.get('awayTeamFtScore'))
    hh=score(m.get('homeTeamHalftimeScore')); ah=score(m.get('awayTeamHalftimeScore'))
    home=m.get('homeTeam') or {}; away=m.get('awayTeam') or {}
    league_id=str(m.get('leagueId') or GOAL_LEAGUE_ID); league=GOAL_LEAGUES.get(league_id,{})
    hid='goal:'+str(m.get('homeTeamId') or home.get('id') or '')
    aid='goal:'+str(m.get('awayTeamId') or away.get('id') or '')
    dt=m.get('kickoffUtc') or (str(m.get('matchDate',''))+'T'+str(m.get('matchTime','00:00'))+':00Z')
    label=league.get('name') or m.get('leagueName') or 'Liga'
    return {'id':m.get('id'),'status':status,'utcDate':dt,'homeTeam':{'id':hid,'name':m.get('homeTeamName') or home.get('name') or 'Local','crest':m.get('teamHomeBadge') or home.get('badge') or ''},'awayTeam':{'id':aid,'name':m.get('awayTeamName') or away.get('name') or 'Visitante','crest':m.get('teamAwayBadge') or away.get('badge') or ''},'competition':{'id':'goal:'+league_id,'code':'goal:'+str(league.get('apiId') or ''),'name':label,'area':{'name':league.get('country') or m.get('countryName') or ''}},'area':{'name':league.get('country') or m.get('countryName') or ''},'score':{'winner':None,'duration':'REGULAR','fullTime':{'home':hg,'away':ag},'halfTime':{'home':hh,'away':ah}},'minute':m.get('matchElapsed'),'source':'GOAL API'}

def goal_competitions():
    rows=[]
    for league_id,meta in GOAL_LEAGUES.items():
        rows.append({'id':'goal:'+league_id,'code':'goal:'+meta['apiId'],'name':meta['name']+' (GOAL API)','type':'LEAGUE','area':{'name':meta['country']},'currentSeason':{'startDate':'2021-01-01','endDate':None,'currentMatchday':None},'source':'GOAL API'})
    return {'competitions':rows}

def goal_teams(league_id):
    data=goal_api('/leagues/'+league_id+'/teams').get('data',[])
    return {'teams':[{'id':'goal:'+str(t.get('id')),'name':t.get('name') or 'Equipo','crest':t.get('badge') or ''} for t in data if t.get('id') and t.get('name')]}

def goal_team_matches(team_id,league_id,limit=100,offset=0,force=False):
    data=goal_api('/teams/'+urllib.parse.quote(goal_raw(team_id),safe='')+'/fixtures',{'limit':limit,'offset':offset},force=force)
    return [m for m in data.get('data',[]) if str(m.get('leagueId'))==str(league_id)]

def goal_recent_history(team_id, league_id, opponent_id=None, target=None):
    rows=[]; offset=0
    while len(rows)<10 and offset<500:
        page=goal_team_matches(team_id,league_id,100,offset)
        if not page:break
        for m in page:
            if str(m.get('leagueId'))!=str(league_id):continue
            if m.get('matchStatus')!='FINISHED':continue
            if m.get('homeTeamFtScore') is None or m.get('awayTeamFtScore') is None:continue
            if target and colombia_local_date(m.get('kickoffUtc')) and colombia_local_date(m.get('kickoffUtc'))>=target:continue
            rows.append(m)
        offset+=100
        if len(page)<100:break
    rows.sort(key=lambda m:str(m.get('kickoffUtc') or ''),reverse=True)
    return [goal_normalize_match(m) for m in rows[:10]]

def goal_find_fixture(home_id,away_id,target,league_id,force=False):
    page=goal_api('/leagues/'+league_id+'/fixtures',{'limit':100,'offset':0},force=force).get('data',[])
    for m in page:
        if str(m.get('leagueId'))!=str(league_id):continue
        if str(m.get('homeTeamId'))!=goal_raw(home_id) or str(m.get('awayTeamId'))!=goal_raw(away_id):continue
        dt=m.get('kickoffUtc') or (str(m.get('matchDate',''))+'T00:00:00Z')
        if target and colombia_local_date(dt)!=target:continue
        return goal_normalize_match(m)
    return None

def goal_analysis(home_id,away_id,target,league_id):
    label=GOAL_LEAGUES[league_id]['name']
    fixture=goal_find_fixture(home_id,away_id,target,league_id) if target else None
    hm=goal_recent_history(home_id,league_id,target=target); am=goal_recent_history(away_id,league_id,target=target)
    def stats(matches,team):
        gf=ga=wins=draws=losses=clean=failed=over15=over25=btts=ht_goals=ht_over=0; form=[]; n=0
        for m in matches:
            ft=m.get('score',{}).get('fullTime',{}); hg=ft.get('home'); ag=ft.get('away')
            if hg is None or ag is None:continue
            n+=1; is_home=m.get('homeTeam',{}).get('id')==team; scored,conceded=(hg,ag) if is_home else (ag,hg)
            gf+=scored;ga+=conceded
            if scored>conceded:wins+=1;form.append('G')
            elif scored==conceded:draws+=1;form.append('E')
            else:losses+=1;form.append('P')
            clean+=conceded==0;failed+=scored==0;over15+=(hg+ag)>1;over25+=(hg+ag)>2;btts+=(hg>0 and ag>0)
            half=m.get('score',{}).get('halfTime',{}); total=(half.get('home') or 0)+(half.get('away') or 0);ht_goals+=total;ht_over+=total>0
        return {'matches':n,'gf':gf/n if n else 0,'ga':ga/n if n else 0,'wins':wins,'draws':draws,'losses':losses,'cleanSheets':clean,'failedToScore':failed,'over15':round(over15*100/n,1) if n else None,'over25':round(over25*100/n,1) if n else None,'btts':round(btts*100/n,1) if n else None,'firstHalfGoals':round(ht_goals/n,2) if n else None,'firstHalfOver05':round(ht_over*100/n,1) if n else None,'form':'-'.join(form[-5:])}
    hs=stats(hm,home_id); avs=stats(am,away_id)
    if hs['matches']<10 or avs['matches']<10:
        return {'homeMatches':hm,'awayMatches':am,'engine':{'sampleSize':hs['matches']+avs['matches'],'dataAvailable':False,'date':target,'fixture':fixture,'method':f'Poisson sobre los últimos 10 partidos de {label}'}}
    lx=max(.15,(hs['gf']+avs['ga'])/2); ax=max(.15,(avs['gf']+hs['ga'])/2)
    def pois(l,k):return math.exp(-l)*l**k/math.factorial(k)
    probs={(i,j):pois(lx,i)*pois(ax,j) for i in range(8) for j in range(8)}; total=sum(probs.values())
    hp=sum(v for (i,j),v in probs.items() if i>j)/total; dp=sum(v for (i,j),v in probs.items() if i==j)/total; ap=sum(v for (i,j),v in probs.items() if i<j)/total
    o15=1-sum(v for (i,j),v in probs.items() if i+j<=1)/total; o25=1-sum(v for (i,j),v in probs.items() if i+j<=2)/total; u25=1-o25; btts=sum(v for (i,j),v in probs.items() if i>0 and j>0)/total
    hscores=1-math.exp(-lx); ascores=1-math.exp(-ax); ht05=((hs['firstHalfOver05'] or 0)+(avs['firstHalfOver05'] or 0))/200; ex=max(probs,key=probs.get)
    outcomes=[('Local',hp),('Empate',dp),('Visitante',ap)]; signal,sp=max(outcomes,key=lambda z:z[1]); sample=hs['matches']+avs['matches']; confidence='Alta' if sp>=.67 and sample>=8 else ('Media' if sp>=.52 else 'Baja')
    reasons=[]; hr=hs['wins']/hs['matches']; ar=avs['wins']/avs['matches']
    if hr>ar+.15:reasons.append(f'El local llega con mejor tasa de victorias reciente en {label}.')
    elif ar>hr+.15:reasons.append(f'El visitante llega con mejor tasa de victorias reciente en {label}.')
    if lx>ax+.35:reasons.append('El modelo proyecta más goles para el equipo local.')
    elif ax>lx+.35:reasons.append('El modelo proyecta más goles para el equipo visitante.')
    if hs['ga']<avs['ga']-.35:reasons.append('El local viene defendiendo mejor.')
    elif avs['ga']<hs['ga']-.35:reasons.append('El visitante viene defendiendo mejor.')
    if not reasons:reasons.append(f'Los datos recientes de {label} muestran una tendencia equilibrada.')
    return {'homeMatches':hm,'awayMatches':am,'engine':{'sampleSize':sample,'probabilities':{'home':round(hp*100,1),'draw':round(dp*100,1),'away':round(ap*100,1),'over1_5':round(o15*100,1),'over2_5':round(o25*100,1),'under2_5':round(u25*100,1),'btts':round(btts*100,1),'over0_5_ht':round(ht05*100,1),'home_scores':round(hscores*100,1),'away_scores':round(ascores*100,1),'double_1x':round((hp+dp)*100,1),'double_x2':round((dp+ap)*100,1),'double_12':round((hp+ap)*100,1)},'expectedGoals':{'home':round(lx,2),'away':round(ax,2),'total':round(lx+ax,2)},'mostLikelyScore':f'{ex[0]}-{ex[1]}','summary':{'signal':signal,'probability':round(sp*100,1),'confidence':confidence,'reasons':reasons[:3]},'history':{'home':hs,'away':avs},'date':target,'fixture':fixture,'method':f'Poisson · últimos 10 partidos finalizados de {label}','source':f'GOAL API · {label}'}}
COLOMBIA_TZ=timezone(timedelta(hours=-5))

def colombia_local_date(utc_value):
    if not utc_value:return None
    try:
        value=str(utc_value)
        if value.endswith('Z'):value=value[:-1]+'+00:00'
        dt=datetime.fromisoformat(value)
        if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(COLOMBIA_TZ).date().isoformat()
    except (ValueError,TypeError):
        return None
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

def api(path, params=None, force=False):
    params=params or {}; key=(path,tuple(sorted(params.items()))); now=time.time(); cached=FD_CACHE.get(key); ttl=fd_cache_ttl(path,params)
    if force: cached=None
    if cached and now-cached[0]<ttl: return cached[1]
    url=BASE+path
    if params: url+='?'+urllib.parse.urlencode(params)
    req=urllib.request.Request(url, headers={'X-Auth-Token':TOKEN or ''})
    last_error=None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req,timeout=12) as r: data=json.load(r)
            FD_CACHE[key]=(time.time(),data)
            return data
        except (urllib.error.HTTPError,urllib.error.URLError,TimeoutError) as exc:
            last_error=exc
            if attempt<2: time.sleep(1.5*(attempt+1))
    # Si el proveedor limita temporalmente las consultas, reutilizamos el
    # último dato válido en vez de dejar toda la aplicación en error.
    if cached: return cached[1]
    raise last_error
LIVE_CACHE={'at':0,'data':None}
LIVE_REFRESH_LOCK=threading.Lock()
def refresh_live_async():
    # Actualiza partidos en segundo plano después de despertar Render.
    if not LIVE_REFRESH_LOCK.acquire(blocking=False): return
    def run():
        try: live_data()
        finally: LIVE_REFRESH_LOCK.release()
    threading.Thread(target=run,daemon=True).start()

def live_data(force=False):
    global LIVE_CACHE
    now=time.time()
    if not force and LIVE_CACHE['data'] is not None and now-LIVE_CACHE['at']<25:
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
            if p.path=='/api/competitions':
                data=api('/competitions'); comps=data.get('competitions',[]); comps.extend(goal_competitions()['competitions']); data['competitions']=comps; self.send_json(data); return
            if p.path=='/api/goal-quota':
                self.send_json({'source':'GOAL API','limit':1000,'remaining':GOAL_QUOTA.get('remaining'),'appRequests':GOAL_QUOTA.get('used',0),'reserve':GOAL_DAILY_RESERVE,'enabled':bool(GOAL_TOKEN),'quotaKnown':GOAL_QUOTA.get('known',False),'resetsAt':GOAL_QUOTA.get('reset')}); return
            if p.path=='/api/teams':
                competition=q.get('competition',[''])[0]
                if goal_prefix(competition):
                    league_id=goal_raw(competition)
                    if league_id not in GOAL_LEAGUES:self.send_json({'error':'Liga GOAL no habilitada.'},400); return
                    self.send_json(goal_teams(league_id)); return
                if not competition.isdigit(): self.send_json({'error':'Competición no válida.'},400); return
                self.send_json(api('/competitions/%s/teams'%competition)); return
            if p.path=='/api/matches':
                if q.get('refresh',['0'])[0]=='1':
                    self.send_json(live_data(force=True)); return
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
                # Pedimos hasta el día UTC posterior al último día de Colombia;
                # luego filtramos por fecha local para no perder encuentros nocturnos.
                query_end=(start_date+timedelta(days=days+1)).isoformat()
                # La consulta global a veces devuelve muy pocos partidos.
                # Recorremos las ligas que la cuenta tiene disponibles y
                # unimos sus resultados sin duplicados.
                merged={}
                # La consulta global suele devolver partidos de varias
                # competiciones en una sola llamada; la usamos primero para
                # no perder encuentros cuando el proveedor limita consultas
                # consecutivas por competición.
                try:
                    global_data=api('/matches',{'dateFrom':start,'dateTo':query_end,'limit':100})
                    for m in global_data.get('matches',[]):
                        if m.get('status') in ('SCHEDULED','TIMED'):
                            merged[str(m.get('id'))]=m
                except Exception:
                    pass
                if not merged:
                    # Si la consulta global no está disponible, consulta las
                    # competiciones en paralelo: serialmente podía tardar minutos.
                    try:
                        comps=api('/competitions').get('competitions',[])
                        def fetch_fd_comp(comp):
                            code=comp.get('code') or comp.get('id')
                            if not code:return []
                            try:
                                part=api('/competitions/%s/matches'%code,{'dateFrom':start,'dateTo':query_end,'limit':100})
                                return [m for m in part.get('matches',[]) if m.get('status') in ('SCHEDULED','TIMED')]
                            except Exception:return []
                        with ThreadPoolExecutor(max_workers=8) as pool:
                            for future in as_completed([pool.submit(fetch_fd_comp,comp) for comp in comps]):
                                for m in future.result():merged[str(m.get('id'))]=m
                    except Exception:
                        merged={}
                local_tz=timezone(timedelta(hours=-5))
                def in_requested_local_range(m):
                    try:
                        dt=datetime.fromisoformat(str(m.get('utcDate','')).replace('Z','+00:00'))
                        if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
                        local_date=dt.astimezone(local_tz).date().isoformat()
                        return start<=local_date<=end
                    except Exception:
                        match_date=str(m.get('utcDate',''))[:10]
                        return start<=match_date<=end
                merged={k:m for k,m in merged.items() if in_requested_local_range(m)}
                if merged:
                    data={'matches':list(merged.values()),'resultSet':{'count':len(merged)}}
                else:
                    fallback=api('/matches',{'dateFrom':start,'dateTo':query_end,'limit':100})
                    data=dict(fallback)
                    data['matches']=[m for m in fallback.get('matches',[]) if m.get('status') in ('SCHEDULED','TIMED') and in_requested_local_range(m)]
                # Consultamos GOAL por día, no una vez por cada una de las
                # 149 ligas. Paginamos el día completo y filtramos IDs exactos
                # para conservar todos los partidos de las ligas habilitadas.
                # Las páginas van en serie para que la cuota reportada se actualice
                # antes de solicitar otra y nunca se consuma la reserva preventiva.
                goal_incomplete=False
                enabled_goal_ids=set(GOAL_LEAGUES)
                utc_days=[(start_date+timedelta(days=i)).isoformat() for i in range(days+1)]
                def fetch_goal_date(day):
                    found=[]; offset=0; total=None
                    while total is None or offset<total:
                        try:
                            page=goal_api('/fixtures/date/'+day,{'limit':100,'offset':offset})
                        except Exception:
                            return None
                        rows=page.get('data',[])
                        for gm in rows:
                            league_id=str(gm.get('leagueId') or '')
                            if league_id not in enabled_goal_ids:continue
                            normalized=goal_normalize_match(gm)
                            if normalized['status'] not in ('SCHEDULED','TIMED','LIVE','IN_PLAY','PAUSED'):continue
                            local=colombia_local_date(normalized.get('utcDate'))
                            if local and start<=local<=end:found.append(('goal:'+str(gm.get('id')),normalized))
                        pagination=page.get('pagination') or {}
                        try:total=int(pagination.get('total',len(rows)))
                        except (ValueError,TypeError):total=len(rows)
                        if not rows or len(rows)<100:break
                        offset+=len(rows)
                    return found
                for goal_day in utc_days:
                    result=fetch_goal_date(goal_day)
                    if result is None:
                        goal_incomplete=True
                        continue
                    for match_id,normalized in result:merged[match_id]=normalized
                data={'matches':list(merged.values()),'resultSet':{'count':len(merged)},'dateFrom':start,'dateTo':end,'scope':'Ligas disponibles · Football-Data.org y GOAL API'}
                if goal_incomplete:data['goalWarning']='GOAL API no está disponible o alcanzó la reserva preventiva; algunos encuentros de esas ligas podrían faltar.'
                self.send_json(data); return
            if p.path=='/api/today':
                start=q.get('date',[date.today().isoformat()])[0]
                try:
                    end=(date.fromisoformat(start)+timedelta(days=1)).isoformat()
                except ValueError:
                    start=date.today().isoformat(); end=(date.today()+timedelta(days=1)).isoformat()
                try:
                    data=api('/matches',{'dateFrom':start,'dateTo':end,'limit':100},force=q.get('refresh',['0'])[0]=='1')
                    if data.get('errorCode') or not isinstance(data.get('matches'),list) or not data.get('matches'): raise RuntimeError('all-day query unavailable')
                except Exception:
                    # Algunas cuentas de Football-Data solo permiten la
                    # consulta de programados; usamos ese resultado como
                    # respaldo y añadimos los partidos en vivo aparte.
                    try:
                        data=api('/matches',{'dateFrom':start,'dateTo':end,'status':'SCHEDULED','limit':100})
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
                try:
                    existing={str(m.get('id')) for m in data.get('matches',[])}
                    for league_id in GOAL_LEAGUES:
                        gd=goal_api('/leagues/'+league_id+'/fixtures',{'limit':100,'offset':0}).get('data',[])
                        for gm in gd:
                            if str(gm.get('leagueId'))!=league_id:continue
                            normalized=goal_normalize_match(gm)
                            if normalized.get('status') not in ('SCHEDULED','TIMED','LIVE','IN_PLAY','PAUSED','FINISHED'):continue
                            if colombia_local_date(normalized.get('utcDate'))!=start:continue
                            key=str(normalized.get('id'))
                            if key not in existing:data.setdefault('matches',[]).append(normalized);existing.add(key)
                except Exception:pass
                data['dateFrom']=start; data['dateTo']=end; data['scope']='Partidos destacados · Football-Data.org y GOAL API'
                self.send_json(data); return
            if p.path=='/api/fixture':
                raw_home=q.get('home',[''])[0]; raw_away=q.get('away',[''])[0]; target=q.get('date',[None])[0]
                competition=str(q.get('competition',[''])[0] or '')
                if goal_prefix(competition):
                    league_id=goal_raw(competition)
                    if league_id not in GOAL_LEAGUES or not (goal_prefix(raw_home) and goal_prefix(raw_away)):
                        self.send_json({'fixture':None,'date':target,'source':'GOAL API'}); return
                    fixture=goal_find_fixture(raw_home,raw_away,target,league_id,force=q.get('refresh',['0'])[0]=='1')
                    self.send_json({'fixture':fixture,'date':target,'source':'GOAL API'}); return
                home=int(raw_home); away=int(raw_away)
                competition_id=str(q.get('competition',[''])[0] or '')
                force_refresh=q.get('refresh',['0'])[0]=='1'
                fixture=None
                if target:
                    target_date=date.fromisoformat(target)
                    query_end=(target_date+timedelta(days=1)).isoformat()
                    params={'dateFrom':target,'dateTo':query_end,'limit':100}
                    data=api('/teams/%s/matches'%home,params,force=force_refresh)
                    for match in data.get('matches',[]):
                        mh=match.get('homeTeam',{}).get('id'); ma=match.get('awayTeam',{}).get('id')
                        if mh!=home or ma!=away:continue
                        if colombia_local_date(match.get('utcDate'))!=target:continue
                        comp=match.get('competition') or {}
                        if competition_id and competition_id not in (str(comp.get('id','')),str(comp.get('code',''))):continue
                        fixture={'id':match.get('id'),'status':match.get('status'),'utcDate':match.get('utcDate'),'competition':comp.get('name'),'score':match.get('score',{})}
                        break
                self.send_json({'fixture':fixture,'date':target}); return
            if p.path=='/api/analyze':
                raw_home=q.get('home',[''])[0]; raw_away=q.get('away',[''])[0]; target=q.get('date',[None])[0]; competition_id=str(q.get('competition',[''])[0] or '')
                if goal_prefix(competition_id):
                    league_id=goal_raw(competition_id)
                    if league_id not in GOAL_LEAGUES or not (goal_prefix(raw_home) and goal_prefix(raw_away)):
                        self.send_json({'error':'Los equipos no corresponden a la liga seleccionada.'},400); return
                    self.send_json(goal_analysis(raw_home,raw_away,target,league_id)); return
                home=int(raw_home); away=int(raw_away); home_name=q.get('homeName',[''])[0]; away_name=q.get('awayName',[''])[0]
                # La fecha elegida identifica el partido a analizar; no debe
                # limitar el historial a esa fecha. Para un partido futuro,
                # usamos los últimos partidos terminados de ambos equipos.
                hist={'status':'FINISHED','limit':100}
                hm=api('/teams/%s/matches'%home,hist); am=api('/teams/%s/matches'%away,hist)
                # Keep the analysis specific to the selected competition.
                def only_competition(data):
                    if not competition_id:return data
                    rows=[m for m in (data.get('matches') or []) if str((m.get('competition') or {}).get('id',''))==competition_id or str((m.get('competition') or {}).get('code',''))==competition_id]
                    result=dict(data);result['matches']=rows[:10];return result
                hm=only_competition(hm); am=only_competition(am)
                history_season=None
                # Si un equipo tiene menos de 10 partidos terminados en la
                # temporada actual, completamos su muestra con la temporada
                # anterior. Se hace por equipo, no solo cuando ambos están
                # cortos, para que todos los análisis tengan una muestra útil.
                try:
                    fallback_year=(int(target[:4])-1) if target else (date.today().year-1)
                    previous={'season':fallback_year,'status':'FINISHED','limit':100}
                    def complete_history(team_id,current):
                        rows=list(current.get('matches') or [])
                        if len(rows)>=10:return current,False
                        old=only_competition(api('/teams/%s/matches'%team_id,previous))
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
                    gf=ga=wins=draws=losses=clean=failed=over15=over25=btts=first_half_goals=first_half_over05=n=0
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
                        half=sc.get('halfTime',{}); first_half_goals+=(half.get('home') or 0)+(half.get('away') or 0); first_half_over05+=((half.get('home') or 0)+(half.get('away') or 0))>0
                    return {'matches':n,'gf':gf/n if n else 1.2,'ga':ga/n if n else 1.2,'wins':wins,'draws':draws,'losses':losses,'cleanSheets':clean,'failedToScore':failed,'over15':round(over15*100/n,1) if n else None,'over25':round(over25*100/n,1) if n else None,'btts':round(btts*100/n,1) if n else None,'firstHalfGoals':round(first_half_goals/n,2) if n else None,'firstHalfOver05':round(first_half_over05*100/n,1) if n else None,'form':'-'.join(form[-5:])}
                hs,avs=stats(hm,home),stats(am,away)
                if hs['matches']==0 or avs['matches']==0:
                    self.send_json({'homeMatches':hm.get('matches',[]),'awayMatches':am.get('matches',[]),'engine':{'sampleSize':hs['matches']+avs['matches'],'dataAvailable':False,'historySeason':history_season,'date':target,'fixture':fixture,'historySeason':history_season,'method':'Poisson sobre promedios recientes'}}); return
                lx=max(.15,(hs['gf']+avs['ga'])/2); ax=max(.15,(avs['gf']+hs['ga'])/2)
                def pois(l,k): return math.exp(-l)*l**k/math.factorial(k)
                probs={(i,j):pois(lx,i)*pois(ax,j) for i in range(8) for j in range(8)}; total=sum(probs.values()); hp=sum(v for (i,j),v in probs.items() if i>j)/total; dp=sum(v for (i,j),v in probs.items() if i==j)/total; ap=sum(v for (i,j),v in probs.items() if i<j)/total; o15=1-sum(v for (i,j),v in probs.items() if i+j<=1)/total; o25=1-sum(v for (i,j),v in probs.items() if i+j<=2)/total; u25=1-o25; btts=sum(v for (i,j),v in probs.items() if i>0 and j>0)/total; home_scores=1-math.exp(-lx); away_scores=1-math.exp(-ax); ht05=((hs['firstHalfOver05'] or 0)+(avs['firstHalfOver05'] or 0))/200; ex=max(probs,key=probs.get)
                outcomes=[('Local',hp),('Empate',dp),('Visitante',ap)]; signal,signal_prob=max(outcomes,key=lambda x:x[1]); sample=hs['matches']+avs['matches']; confidence='Alta' if signal_prob>=.67 and sample>=8 else ('Media' if signal_prob>=.52 else 'Baja')
                home_rate=hs['wins']/hs['matches']; away_rate=avs['wins']/avs['matches']; reasons=[]
                if home_rate>away_rate+.15: reasons.append('El local llega con mejor tasa de victorias reciente.')
                elif away_rate>home_rate+.15: reasons.append('El visitante llega con mejor tasa de victorias reciente.')
                if lx>ax+.35: reasons.append('El modelo proyecta más goles para el equipo local.')
                elif ax>lx+.35: reasons.append('El modelo proyecta más goles para el equipo visitante.')
                if hs['ga']<avs['ga']-.35: reasons.append('El local viene defendiendo mejor.')
                elif avs['ga']<hs['ga']-.35: reasons.append('El visitante viene defendiendo mejor.')
                if not reasons: reasons.append('Los datos recientes muestran una tendencia equilibrada.')
                self.send_json({'homeMatches':hm.get('matches',[]),'awayMatches':am.get('matches',[]),'engine':{'sampleSize':hs['matches']+avs['matches'],'probabilities':{'home':round(hp*100,1),'draw':round(dp*100,1),'away':round(ap*100,1),'over1_5':round(o15*100,1),'over2_5':round(o25*100,1),'under2_5':round(u25*100,1),'btts':round(btts*100,1),'over0_5_ht':round(ht05*100,1),'home_scores':round(home_scores*100,1),'away_scores':round(away_scores*100,1),'double_1x':round((hp+dp)*100,1),'double_x2':round((dp+ap)*100,1),'double_12':round((hp+ap)*100,1)},'expectedGoals':{'home':round(lx,2),'away':round(ax,2),'total':round(lx+ax,2)},'mostLikelyScore':f'{ex[0]}-{ex[1]}','summary':{'signal':signal,'probability':round(signal_prob*100,1),'confidence':confidence,'reasons':reasons[:3]},'history':{'home':hs,'away':avs},'date':target,'fixture':fixture,'historySeason':history_season,'method':'Poisson sobre promedios recientes'}}); return
            return SimpleHTTPRequestHandler.do_GET(self)
        except Exception as e:
            print('Request error:', repr(e))
            self.send_json({'error':'No se pudo completar la consulta. Intenta nuevamente.'},502)
if __name__=='__main__':
    port=int(os.environ.get('PORT','10000')); print('ParleyStats en puerto',port); ThreadingHTTPServer(('0.0.0.0',port),Handler).serve_forever()
