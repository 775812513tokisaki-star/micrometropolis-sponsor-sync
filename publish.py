"""Build the VRChat public roster. No raw player names, supporter IDs, codes or API responses are logged."""
import base64, gzip, hashlib, json, os, re, time
from pathlib import Path
from urllib import request, error

PLANS={'9bd0b6c6e5a111f1bab552540025c377':1,'9abb0d86e5a111f18d3d52540025c377':2,
       '99a7751ae5a111f195cf5254001e7c00':3,'9633e170e5a111f18eeb5254001e7c00':4}
PREFIX='# WorldSponsors v2'
MAX_ROWS=4096

def account_key(value):
    return hashlib.sha256(('MicroMetropolis/Afdian/v2|'+value).encode()).hexdigest()

def operator_state(env):
    manifest=json.loads(env['MM_INDEX'])
    n=manifest['n']
    if not isinstance(n,int) or not 1<=n<=16:raise ValueError('Invalid configuration manifest')
    encoded=''.join(env['MM_PART_'+str(i)] for i in range(n))
    if hashlib.sha256(encoded.encode()).hexdigest()!=manifest['sha']:raise ValueError('Incomplete configuration update; retaining previous deployment')
    raw=gzip.decompress(base64.b64decode(encoded,validate=True))
    if len(raw)>2_000_000:raise ValueError('Configuration exceeds supported size')
    state=json.loads(raw)
    if state.get('schema')!=2:raise ValueError('Unsupported operator schema')
    return state

def post(route,values,uid,token):
    params=json.dumps(values,ensure_ascii=False,separators=(',',':'))
    for origin in ('https://ifdian.net','https://afdian.com','https://ifdian.net'):
        ts=int(time.time())
        sign=hashlib.md5(f'{token}params{params}ts{ts}user_id{uid}'.encode()).hexdigest()
        payload=json.dumps({'user_id':uid,'params':params,'ts':ts,'sign':sign}).encode()
        req=request.Request(origin+'/api/open/'+route,data=payload,headers={'Content-Type':'application/json','User-Agent':'MicroMetropolis-Sponsor-Sync/2'})
        try:
            with request.urlopen(req,timeout=18) as resp: result=json.load(resp)
        except (OSError,ValueError):
            time.sleep(.5);continue
        if result.get('ec')!=200:
            raise RuntimeError('Afdian returned ec='+str(result.get('ec')))
        return result['data']
    raise RuntimeError('Afdian transport unavailable; retaining previous deployment')

def members(uid,token):
    seen=set();result=[];page=1
    while True:
        data=post('query-sponsor',{'page':page},uid,token)
        rows=data['list'];pages=int(data['total_page']);total=int(data['total_count'])
        if not isinstance(rows,list) or min(pages,total)<0 or pages>10000:raise ValueError('Invalid pagination')
        for row in rows:
            aid=row['user']['user_id']
            if not aid or aid in seen:raise ValueError('Sponsor page changed during sync')
            seen.add(aid);result.append(row)
        if page>=pages:break
        page+=1
    if len(seen)!=total:raise ValueError('Incomplete sponsor pagination')
    return result

def make_rows(state,people,now):
    grants=set()
    def include(key,tier,end,alias):
        if not isinstance(key,str) or re.fullmatch('[0-9a-f]{64}',key) is None:raise ValueError('Invalid player digest')
        if type(tier)!=int or not 1<=tier<=4 or type(end)!=int or end<0 or end>9223372036854775807:raise ValueError('Invalid grant')
        if not isinstance(alias,str) or len(alias.encode('utf-16le'))>128 or any(ord(c)<32 or c in '\x7f\u2028\u2029' for c in alias):raise ValueError('Invalid display alias')
        if end==0 or end>now:grants.add((key,tier,end,alias))
    for row in state['manual']:include(*row)
    bindings=state['links']
    for person in people:
        link=bindings.get(account_key(person['user']['user_id']))
        if link is None:continue
        for plan in (person.get('sponsor_plans') or [])+[person.get('current_plan') or {}]:
            tier=PLANS.get(plan.get('plan_id'))
            if tier is None:continue
            until=int(plan.get('expire_time') or 0)
            if until>now:include(link[0],tier,until,link[1])
    if len(grants)>MAX_ROWS:raise ValueError('Roster exceeds the world row limit')
    return ['\t'.join(map(str,row)) for row in sorted(grants)]

def feed(rows,revision):
    result='\n'.join([f'{PREFIX}\t{revision}\t{len(rows)}',*rows,'# end',''])
    if len(result.encode('utf-16le'))//2>524288:raise ValueError('Roster exceeds world payload limit')
    return result

def previous(url):
    # Check current public artifact on cache miss too. A failed fetch must not revoke anything.
    try:
        req=request.Request(url+'?verify='+str(time.time_ns()),headers={'Cache-Control':'no-cache'})
        with request.urlopen(req,timeout=12) as resp:s=resp.read(1_200_000).decode()
        lines=s.rstrip('\n').split('\n');fmt,revision,n=lines[0].split('\t')
        if fmt==PREFIX and lines[-1]=='# end' and len(lines)-2==int(n):return int(revision),lines[1:-1]
    except (OSError,ValueError,IndexError):pass
    return 0,None

def main():
    env=os.environ;state=operator_state(env)
    grants=make_rows(state,members(env['AF_USER_ID'],env['AF_TOKEN']),int(time.time()))
    old,existing=previous(env['PUBLIC_ROSTER_URL']);changed=existing!=grants
    path=Path('site');path.mkdir(exist_ok=True)
    if changed:
        (path/'roster.txt').write_text(feed(grants,max(time.time_ns()//1_000_000,old+1)),encoding='utf8')
        (path/'.nojekyll').touch()
    with open(env['GITHUB_OUTPUT'],'a') as f:print('changed='+str(changed).lower(),file=f)
    print('Public roster rows:',len(grants),'Publication needed:',changed)
if __name__=='__main__':main()

