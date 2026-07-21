import json, math, os
from collections import defaultdict
from datetime import datetime

ledger = r'C:\Users\krist\AppData\Local\hermes\cache\session-artifact-ledger.jsonl'
out = r'C:\Users\krist\Desktop\OpenJarvis\docs\session-semantic-graph.html'

items=[]
with open(ledger,'r',encoding='utf-8') as f:
    for line in f:
        s=line.strip()
        if not s: continue
        obj=json.loads(s)
        ts=obj.get('ts','')
        try:
            obj['_dt']=datetime.fromisoformat(ts.replace('Z','+00:00')).replace(tzinfo=None)
        except Exception:
            obj['_dt']=datetime(2000,1,1)
        items.append(obj)
items.sort(key=lambda a:a['_dt'])

by_date=defaultdict(list)
for it in items:
    by_date[it['_dt'].date().isoformat()].append(it)
dates=sorted(by_date)
min_d=datetime.strptime(dates[0],'%Y-%m-%d').date()
max_d=datetime.strptime(dates[-1],'%Y-%m-%d').date()
span=max((max_d-min_d).days,1)
rings=6
ring_for_date={d: 1+int((datetime.strptime(d,'%Y-%m-%d').date()-min_d).days/max(span/rings,1)) for d in dates}
R=500;r0=110;gap=55
pos=[]
for d,nodes in by_date.items():
    ring=ring_for_date[d]
    step=360/max(len(nodes),1)
    off=hash(d)%360
    for i,nd in enumerate(nodes):
        a=math.radians((off+i*step)%360-90)
        aid=nd.get('artifact_id') or ''
        j=hash(aid)%18
        r=r0+(ring-1)*gap+j
        x=R+r*math.cos(a)
        y=R+r*math.sin(a)
        pos.append((nd,x,y,ring,d))

edges=[]
by_ses=defaultdict(list)
for nd,x,y,ring,d in pos:
    by_ses[nd.get('session_id')].append((x,y))
for sid,arr in by_ses.items():
    if len(arr)==2:
        edges.append((arr[0][0],arr[0][1],arr[1][0],arr[1][1]))
    elif len(arr)>2:
        for i in range(len(arr)-1):
            edges.append((arr[i][0],arr[i][1],arr[i+1][0],arr[i+1][1]))

c={
  'session_dump':'#4cc9f0','terminal':'#f72585','checkpoint':'#7209b7',
  'delegation':'#3a0ca3','root_scan':'#4361ee',
  'blueprint':'#4cc9f0','manifest':'#f72585','interconnections':'#7209b7','arms-registry':'#3a0ca3','env-bridge':'#4361ee'
}

def shaped(cx,cy,kind,r):
    kind=kind or 'circle'
    if kind=='diamond':
        h=r*1.5
        return f'M {cx},{cy-h} L {cx+h},{cy} L {cx},{cy+h} L {cx-h},{cy} Z'
    return f'M {cx-r},{cy-r} a {r},{r} 0 1,0 {r*2},0 a {r},{r} 0 1,0 -{r*2},0'

nodes_json = []
node_pos = {}
for nd,x,y,ring,d in pos:
    nid = nd['artifact_id']
    node_pos[nid] = (x,y)
    nodes_json.append({
        'id':nid,
        'type':nd.get('artifact_type'),
        'ts':nd.get('ts'),
        'sid':nd.get('session_id'),
        'tags':nd.get('tags') or [],
        'cluster':nd.get('cluster') or [],
        'intent':(nd.get('intent') or '')[:140]
    })

data = {'nodes': nodes_json, 'pos': node_pos, 'edges': edges, 'dates': dates}

html=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>OpenJarvis Session Semantic Graph</title><style>
body{{margin:0;background:#0b0d17;color:#e2e8f0;font-family:Inter,system-ui,Segoe UI,Arial,sans-serif}}
#wrap{{position:relative;width:100vw;height:100vh;overflow:hidden}}
#svg{{position:absolute;inset:0}}
.panel{{position:absolute;background:rgba(15,23,42,.55);border:1px solid #1f2a44;border-radius:12px;padding:10px 12px;backdrop-filter:blur(6px)}}
#info{{top:12px;left:12px}} h1{{margin:0 0 6px;font-size:16px}} p{{margin:2px 0;font-size:12px;color:#a5b4c8}}
#legend{{top:12px;right:12px}} .swatch{{display:flex;align-items:center;gap:8px;font-size:12px;margin:3px 0}}.swatch .c{{width:12px;height:12px;border-radius:3px}}
#scrubber{{bottom:14px;left:50%;transform:translateX(-50%);width:min(780px,92vw);display:flex;gap:10px;align-items:center}}
#scrubber input[type=range]{{flex:1}}
.node-group{{cursor:pointer}}.edge{{stroke:#334155;stroke-width:1;stroke-opacity:.35}}
.textlbl{{font-size:10px;fill:#cbd5e1;pointer-events:none}}
</style></head><body>
<div id="wrap">
  <div class="panel" id="info"><h1>OpenJarvis Session Semantic Graph</h1><p>Inner ring = oldest, outer ring = newest.</p><p>Drag the slider left to reveal art over time. Click a node for session context.</p><p id="stats"></p></div>
  <div class="panel" id="legend">
'''
for k,v in c.items():
    html+=f'<div class="swatch"><div class="c" style="background:{v}"></div>{k}</div>\n'
html+='</div>\n<svg id="svg" viewBox="0 0 1000 1000" preserveAspectRatio="xMidYMid meet"></svg>\n'
html+='<div class="panel" id="scrubber"><span>Oldest</span><input id="range" type="range" min="0" max="1" step="0.0005" value="1"><span>Newest</span><span id="dateLabel"></span></div>\n'
html+='<script>'
html+='const D='+json.dumps(data)+';\n'
html+='const SVG_NS="http://www.w3.org/2000/svg";\nconst colors='+json.dumps(c)+';\n'
html+='const svg=document.getElementById("svg");\n'
html+='const layers={edges:svgEl("g"),rings:svgEl("g"),nodes:svgEl("g"),labels:svgEl("g")};\n'
html+='Object.values(layers).forEach(el=>svg.appendChild(el));\n'
html+='function svgEl(tag,a){const e=document.createElementNS(SVG_NS,tag);for(const[k,v] of Object.entries(a||{}))e.setAttribute(k,v);return e;}\n'
# ring helpers
for rr in [r0+i*gap for i in range(rings+1)]:
    html+=f'layers.rings.appendChild(svgEl("circle",{{cx:500,cy:500,r:{rr},fill:"none",stroke:"#1f2a44","stroke-width":1,"stroke-dasharray":"3 8"}}));\n'
html+='function makeShape(type){if(["checkpoint","delegation","root_scan","arms-registry","env-bridge"].includes(type)){return function(cx,cy,R){return `M ${cx},${cy-R} L ${cx+R},${cy} L ${cx},${cy+R} L ${cx-R},${cy} Z`;}}return function(cx,cy,R){return `M ${cx-R},${cy-R} a ${R},${R} 0 1,0 ${R*2},0 a ${R},${R} 0 1,0 -${R*2},0`;}}\n'
html+='const shapeCache={};\nfunction getShape(type){if(!shapeCache[type]) shapeCache[type]=makeShape(type);return shapeCache[type];}\n'
html+='function draw(untilIndex){layers.edges.innerHTML="";layers.nodes.innerHTML="";layers.labels.innerHTML="";const keepIds=new Set();\nconst limit=untilIndex==null?D.nodes.length:untilIndex+1;for(let i=0;i<limit&&i<D.nodes.length;i++){keepIds.add(D.nodes[i].id);}\n'
html+='function addNode(n){const p=D.pos[n.id];if(!p)return;const[x,y]=p;const col=colors[n.type]||"#94a3b8";const R=["root_scan"].includes(n.type)?14:10;const g=svgEl("g",{transform:`translate(${x},${y})`});const sh=getShape(n.type)(0,0,R);g.appendChild(svgEl("path",{d:sh,fill:col,stroke:"#0b0d17","stroke-width":1.5,class:"node"}));const t=svgEl("text",{x:0,y:R+13,"text-anchor":"middle",fill:"#cbd5e1","font-size":"9px",class:"textlbl"});t.textContent=(n.tags&&n.tags[0]?n.tags[0]:n.type||"")+" "+(n.ts?n.ts.slice(5,10):"");g.appendChild(t);g.onclick=()=>alert(["ID",""+n.id,"time",""+n.ts,"session",""+n.sid,"type",""+n.type,"tags",(n.tags||[]).join(", "),"cluster",(n.cluster||[]).join(", "),"intent",(n.intent||"")].join("\\n"));g.onmouseenter=function(){this.firstChild.setAttribute("stroke","#fff");};g.onmouseleave=function(){this.firstChild.setAttribute("stroke","#0b0d17");};layers.nodes.appendChild(g);}\n'
html+='D.nodes.forEach(addNode);\n'
html+='D.edges.forEach(([x1,y1,x2,y2])=>{layers.edges.appendChild(svgEl("line",{x1,y1,x2,y2,class:"edge"}));});\n'
html+='document.getElementById("stats").textContent="Nodes: "+limit+" | Edges: "+D.edges.length;\n'
html+='}\n'
html+='const slider=document.getElementById("range");const dateLabel=document.getElementById("dateLabel");const tsArr=D.nodes.map(n=>n.ts).filter(Boolean);\n'
html+='function nthDate(v){const idx=Math.min(Math.floor(v*Math.max(tsArr.length-1,0)),tsArr.length-1);return tsArr[idx]?tsArr[idx].slice(0,10):"";}\n'
html+='slider.addEventListener("input",e=>{const v=parseFloat(e.target.value);const cut=Math.floor(v*D.nodes.length);draw(cut);dateLabel.textContent=nthDate(v);});\n'
html+='draw();slider.dispatchEvent(new Event("input"));\n'
html+='</script></div></body></html>\n'

os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out,'w',encoding='utf-8') as f:
    f.write(html)
print('wrote',out,'size',os.path.getsize(out))
