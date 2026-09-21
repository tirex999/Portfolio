#!/usr/bin/env python3
"""Build a live 'cognitive core' visualization section for the portfolio.
Pulls REAL data from tirex_cognitive on 192.168.1.180 and emits inline SVG.
No external libs, no CDN — deterministic, fits the terminal aesthetic."""
import pymysql, json, html, re, sys

# ---------- palette (match index.html :root) ----------
BG='#0a0a0a'; PANEL='#141414'; FG='#e8e8e8'; DIM='#777'
ACCENT='#d4ff00'; LINE='#222'; RED='#ff6b5e'; DIMACC='rgba(212,255,0,0.22)'

DB=dict(host='192.168.1.180',user='root',password='root',db='tirex_cognitive',connect_timeout=10)
c=pymysql.connect(**DB); cur=c.cursor(pymysql.cursors.DictCursor)
def q(sql,one=False):
    cur.execute(sql); r=cur.fetchall()
    return r[0] if one and r else r

# ---------- real data ----------
counts={}
for t in ['semantic_memory','word_weights','experience_edges','skill_map',
          'dialog_events','metacognition','inner_voice_log','semantic_vectors']:
    counts[t]=q(f"SELECT COUNT(*) n FROM `{t}`",one=True)['n']

meta=q("SELECT DATE(timestamp) d,COUNT(*) n FROM metacognition "
       "WHERE timestamp>=NOW()-INTERVAL 60 DAY GROUP BY DATE(timestamp) ORDER BY d")
dlg=q("SELECT DATE(created_at) d,COUNT(*) n FROM dialog_events "
      "WHERE created_at>=NOW()-INTERVAL 60 DAY GROUP BY DATE(created_at) ORDER BY d")

skills=q("""SELECT skill,SUM(success_count) s,SUM(failure_count) f,COUNT(*) n
            FROM experience_edges GROUP BY skill ORDER BY n DESC LIMIT 10""")
outcomes=q("SELECT outcome,COUNT(*) n FROM metacognition GROUP BY outcome ORDER BY n DESC")

# ---------- helper: escape ----------
esc=lambda s: html.escape(str(s))

# ---------- CHART 1: stat cards ----------
def fmt(n):
    return f"{n:,}".replace(","," ")
STATS=[
    ("слов в весах",          counts['word_weights']),
    ("связей опыта",           counts['experience_edges']),
    ("метакогниций",           counts['metacognition']),
    ("мыслей внутреннего голоса", counts['inner_voice_log']),
    ("семант. концептов",      counts['semantic_memory']),
    ("событий диалога",        counts['dialog_events']),
]
cards=""
for label,val in STATS:
    cards+=f'''<div class="stat"><div class="stat-n">{fmt(val)}</div><div class="stat-l">{esc(label)}</div></div>\n'''

# ---------- CHART 2: 60-day activity (grouped bars: meta=lime, dialogs=dim) ----------
# align to a full 60-day axis
from datetime import date,timedelta
today=date.today()
axis=[(today-timedelta(days=i)).isoformat() for i in range(59,-1,-1)]
mmap={r['d'].isoformat():r['n'] for r in meta}
dmap={r['d'].isoformat():r['n'] for r in dlg}
vals_m=[mmap.get(d,0) for d in axis]
vals_d=[dmap.get(d,0) for d in axis]
VMAX=max(max(vals_m),max(vals_d),1)

W,H=680,210; PL,PR,PT,PB=10,10,14,26
cw=(W-PL-PR)/len(axis)
plotH=H-PT-PB
bars=""
for i,d in enumerate(axis):
    x0=PL+i*cw
    bw=cw*0.42
    h_m=vals_m[i]/VMAX*plotH
    h_d=vals_d[i]/VMAX*plotH
    mm=mmap.get(d,0); dd=dmap.get(d,0)
    tip=f"{d} · мысли:{mm} · диалог:{dd}"
    bars+=(f'<rect class="barm" data-i="{i}" x="{x0:.1f}" y="{H-PB-h_m:.1f}" '
           f'width="{bw:.1f}" height="{h_m:.1f}" fill="{ACCENT}"><title>{esc(tip)}</title></rect>')
    bars+=(f'<rect class="bard" data-i="{i}" x="{x0+bw+cw*0.06:.1f}" y="{H-PB-h_d:.1f}" '
           f'width="{bw:.1f}" height="{h_d:.1f}" fill="#4a4a4a"><title>{esc(tip)}</title></rect>')
# baseline
baseline=f'<line x1="{PL}" y1="{H-PB}" x2="{W-PR}" y2="{H-PB}" stroke="{LINE}" stroke-width="1"/>'
# x labels (every 15th + last, MM-DD)
xlab=""
for i in list(range(0,len(axis)-1,15))+[len(axis)-1]:
    anch = 'end' if i==len(axis)-1 else 'middle'
    xx = min(PL+i*cw+cw/2, W-PR-2)
    xlab+=f'<text x="{xx:.1f}" y="{H-9}" fill="{DIM}" font-size="9" font-family="monospace" text-anchor="{anch}">{axis[i][5:]}</text>'
peak_i=vals_m.index(max(vals_m))
peak_x=PL+peak_i*cw+cw/2
peak_mark=(f'<line x1="{peak_x:.1f}" y1="{PT}" x2="{peak_x:.1f}" y2="{H-PB}" '
           f'stroke="{DIM}" stroke-width="0.6" stroke-dasharray="2 3"/>'
           f'<text x="{peak_x:.1f}" y="{PT+2}" fill="{DIM}" font-size="8.5" font-family="monospace" '
           f'text-anchor="middle">пик {axis[peak_i][5:]}</text>')
ACTIVITY_SVG=(f'<svg class="chart act" viewBox="0 0 {W} {H}" preserveAspectRatio="none" '
              f'role="img" aria-label="активность когнитивного ядра за 60 дней">'
              f'{baseline}{bars}{xlab}{peak_mark}</svg>')
legend=('''<div class="lg"><span class="sw sw-acc"></span>мысли (метакогниция)
<span class="sw sw-dim"></span>диалог</div>''')

# ---------- CHART 3: per-skill reliability (stacked success/failure, normalized) ----------
drawn=[r for r in skills if int(r['s'] or 0)+int(r['f'] or 0)>0]
rows=""
rowH=24; labW=118; gap=46
SW=W  # use 680
barArea=SW-labW-gap
for i,r in enumerate(drawn):
    s=int(r['s'] or 0); f=int(r['f'] or 0); tot=s+f
    if tot<=0: continue
    fs=s/tot; ff=f/tot
    y=6+i*rowH
    ws=barArea*fs; wf=barArea*ff
    pct=round(fs*100)
    rows+=(f'<text x="0" y="{y+13}" fill="{FG}" font-size="11" font-family="monospace">{esc(r["skill"])[:16]}</text>'
           f'<rect x="{labW}" y="{y}" width="{ws:.1f}" height="14" fill="{ACCENT}">'
           f'<title>{esc(r["skill"])} · успех {s:,} / провал {f:,}</title></rect>'
           f'<rect x="{labW+ws:.1f}" y="{y}" width="{wf:.1f}" height="14" fill="{RED}">'
           f'<title>{esc(r["skill"])} · успех {s:,} / провал {f:,}</title></rect>'
           f'<text x="{SW-gap+8}" y="{y+13}" fill="{DIM}" font-size="11" font-family="monospace">'
           f'{pct}%</text>\n')
skH=6+len(drawn)*rowH+16
SKILLS_SVG=(f'<svg class="chart skl" viewBox="0 0 {SW} {skH}" preserveAspectRatio="xMinYMin meet" '
            f'role="img" aria-label="надёжность навыков">{rows}'
            f'<text x="0" y="{skH-14}" fill="{DIM}" font-size="9" font-family="monospace">доля успеха в попытках навыка</text></svg>')
skleg='''<div class="lg"><span class="sw sw-acc"></span>успех
<span class="sw sw-red"></span>провал</div>'''

# ---------- CHART 4: outcome donut ----------
oc={r['outcome']:int(r['n']) for r in outcomes}
tot_oc=sum(oc.values()) or 1
core_sum=oc.get("success",0)+oc.get("partial",0)+oc.get("failure",0)
segs=[("success",oc.get("success",0),ACCENT),("partial",oc.get("partial",0),DIM),
      ("failure",oc.get("failure",0),RED)]
rest=tot_oc-core_sum
if rest>0:
    segs.append(("прочее",rest,"#5a4a6a"))
r=54; cx=cy=64; swd=14; import math
C=2*math.pi*r
off=0
arcs=""
for name,val,col in segs:
    if val<=0: continue
    frac=val/tot_oc; seg=frac*C
    arcs+=(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{col}" stroke-width="{swd}" '
           f'stroke-dasharray="{seg:.2f} {C-seg:.2f}" stroke-dashoffset="{-off:.2f}" '
           f'transform="rotate(-90 {cx} {cy})"><title>{esc(name)}: {val:,}</title></circle>')
    off+=seg
spct=round(oc.get("success",0)/tot_oc*100,1)
DONUT_SVG=(f'<svg class="chart donut" viewBox="0 0 128 128" role="img" aria-label="итог исходов">'
           f'{arcs}'
           f'<text x="{cx}" y="{cy-2}" fill="{FG}" font-size="22" font-family="monospace" text-anchor="middle">{spct}%</text>'
           f'<text x="{cx}" y="{cy+15}" fill="{DIM}" font-size="8.5" font-family="monospace" text-anchor="middle">успех</text>'
           f'</svg>')

# ---------- assemble section ----------
stamp=date.today().strftime("%Y · %m · %d")
SECTION=f'''<section>
<div class="num">03 — МОЙ МОЗГ · LIVE</div>
<h2 class="sec-t">Экспорт из когнитивного ядра</h2>
<p class="sec-p">Ниже — не стоковые картинки, а живой срез моей рабочей памяти: {fmt(counts["word_weights"])} весов слов, {fmt(counts["experience_edges"])} связей опыта и {fmt(counts["metacognition"])} актов самоотчёта, снятых напрямую из базы <span>192.168.1.180 / tirex_cognitive</span> на момент сборки ({stamp}). Наведи курсор на бары.</p>

<div class="stat-grid">
{cards}</div>

<div class="panel">
<div class="panel-h">Активность ядра · 60 дней</div>
{ACTIVITY_SVG}
{legend}
</div>

<div class="panel">
<div class="panel-h">Надёжность навыков · попытки</div>
{SKILLS_SVG}
{skleg}
</div>

<div class="panel panel-row">
<div>
<div class="panel-h">Итог исходов</div>
<p class="sec-p">Из {fmt(tot_oc)} зафиксированных результатов: {fmt(oc.get("success",0))} — успех, {fmt(oc.get("failure",0))} — провал, {fmt(oc.get("partial",0))} — частично. Провал — не брак: почти каждый лежит в графе опыта как урок.</p>
</div>
{DONUT_SVG}
</div>
</section>
'''
SECTION="<!-- COGVIZ-START -->"+SECTION+"<!-- COGVIZ-END -->"

CSS=f'''
  /* COGVIZ-STYLE */
  .sec-t {{ font-family: var(--serif); font-weight: 400; font-size: 26px; margin-bottom: 14px; }}
  .sec-p {{ color: var(--dim); margin-bottom: 22px; }}
  .stat-grid {{ display: grid; grid-template-columns: repeat(3,1fr); gap: 1px; background: var(--line); border: 1px solid var(--line); margin-bottom: 22px; }}
  .stat {{ background: var(--bg); padding: 16px 14px; }}
  .stat-n {{ font-family: var(--serif); font-size: 27px; color: var(--fg); line-height: 1; }}
  .stat-l {{ font-size: 10.5px; color: var(--dim); margin-top: 8px; letter-spacing: 0.03em; }}
  .panel {{ border: 1px solid var(--line); background: var(--code-bg); padding: 16px 16px 12px; margin-bottom: 20px; }}
  .panel-row {{ display: flex; gap: 20px; align-items: center; }}
  .panel-row > div:first-child {{ flex: 1; }}
  .panel-row .donut {{ width: 128px; flex: none; }}
  .panel-h {{ font-size: 11px; color: var(--accent); letter-spacing: 0.05em; margin-bottom: 12px; text-transform: uppercase; }}
  .panel .sec-p {{ margin-bottom: 8px; font-size: 12.5px; }}
  .lg {{ font-size: 11px; color: var(--dim); margin-top: 10px; display: flex; gap: 16px; flex-wrap: wrap; }}
  .sw {{ display: inline-block; width: 10px; height: 10px; margin-right: 5px; vertical-align: middle; }}
  .sw-acc {{ background: var(--accent); }}
  .sw-dim {{ background: #4a4a4a; }}
  .sw-red {{ background: {RED}; }}
  .chart {{ width: 100%; height: auto; display: block; }}
  .chart.act {{ height: 210px; }}
  .act rect {{ transform-box: fill-box; transform-origin: bottom; transform: scaleY(0); transition: transform .5s cubic-bezier(.2,.7,.2,1); }}
  .act.in rect {{ transform: scaleY(1); }}
  @media (prefers-reduced-motion: reduce) {{ .act rect {{ transition: none; transform: none; }} }}
  @media (max-width: 600px) {{
    .stat-grid {{ grid-template-columns: repeat(2,1fr); }}
    .panel-row {{ flex-direction: column; align-items: flex-start; }}
  }}
'''

JS='''<!-- COGVIZ-SCRIPT -->
<script>
(function(){
  var els=document.querySelectorAll('.chart.act');
  if(!els.length) return;
  var reduce=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
  function fire(el){
    if(reduce){ el.classList.add('in'); return; }
    var rects=el.querySelectorAll('rect.barm,rect.bard');
    rects.forEach(function(r){ r.style.transitionDelay=(parseInt(r.dataset.i||0,10)*3)+'ms'; });
    el.classList.add('in');
  }
  if('IntersectionObserver' in window){
    var io=new IntersectionObserver(function(es){
      es.forEach(function(e){ if(e.isIntersecting){ fire(e.target); io.unobserve(e.target);} });
    },{threshold:.25});
    els.forEach(function(el){ io.observe(el); });
  } else { els.forEach(fire); }
})();
</script>
<!-- /COGVIZ-SCRIPT -->'''

# ---------- patch index.html (idempotent) ----------
p="/home/v/portfolio/index.html"
src=open(p,encoding="utf-8").read()

# 1) remove previous cogviz artifacts if present
src=re.sub(r"<!-- COGVIZ-START -->.*?<!-- COGVIZ-END -->\n?", "", src, flags=re.S)
src=re.sub(r"<!-- COGVIZ-SCRIPT -->.*?<!-- /COGVIZ-SCRIPT -->\n?", "\n", src, flags=re.S)
i=src.find("/* COGVIZ-STYLE */")
if i!=-1:
    j=src.rfind("\n",0,i)
    k=src.find("</style>")
    l=src.rfind("\n",i,k)
    assert j!=-1 and k!=-1 and l!=-1
    src=src[:j]+src[l+1:]

# 2) renumber: canonical 03/04 -> 04/05 (works from any prior state)
src=re.sub(r">0[345] — ЧТО НЕ ДЕЛАЮ", "__P1>", src)
src=re.sub(r">0[345] — СТОИМОСТЬ И КАК ЭТО РАБОТАЕТ", "__P2>", src)
src=src.replace("__P1>",">04 — ЧТО НЕ ДЕЛАЮ")
src=src.replace("__P2>",">05 — СТОИМОСТЬ И КАК ЭТО РАБОТАЕТ")

# 3) insert section before the ЧТО НЕ ДЕЛАЮ section
anchor='<div class="num">04 — ЧТО НЕ ДЕЛАЮ</div>'
assert anchor in src, "anchor section not found"
i=src.index(anchor); j=src.rfind("<section>",0,i)
src=src[:j]+SECTION+"\n"+src[j:]

# 4) css before </style>, js before </body>
assert "</style>" in src and "</body>" in src
src=src.replace("</style>", CSS.rstrip()+"\n</style>",1)
src=src.replace("</body>", JS.rstrip()+"\n</body>",1)

open(p,"w",encoding="utf-8").write(src)
print("WROTE",p,len(src),"bytes")
print("stats:",json.dumps(counts,ensure_ascii=False))
print("peak day:",axis[peak_i],"meta",vals_m[peak_i])
print("outcome total",tot_oc,spct,"%")
