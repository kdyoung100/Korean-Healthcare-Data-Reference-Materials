#!/usr/bin/env python3
"""docs/*.md -> index.html (단일 페이지 자료집 사이트)"""
import os, re, html, json
import markdown

ROOT = "/home/claude/health-data-catalog"
ORDER = ['01-overview', '02-data-summary', '03-public-data', '04-clinical-data',
         '05-research-data', '06-platforms', '07-appendix']

md = markdown.Markdown(extensions=['tables', 'attr_list'])

NUM = re.compile(r'^(\d+(?:\.\d+)*)[.\s]*(.*)$')
DIFF = re.compile(r'난이도\s*[–\-—]\s*([하중상])')


def slug(n):
    return 'sec-' + n.replace('.', '-')


chapters = []          # {num,title,id,html,sections:[{num,title,id,level,diff}]}

for f in ORDER:
    raw = open(f'{ROOT}/docs/{f}.md', encoding='utf-8').read()
    lines = raw.split('\n')
    out, secs = [], []
    ch_num = ch_title = ch_id = None
    cur_entry = None

    for ln in lines:
        m = re.match(r'^(#{1,6})\s+(.*)$', ln)
        if not m:
            out.append(ln)
            continue
        lvl, text = len(m.group(1)), m.group(2).strip()
        nm = NUM.match(text)

        if lvl == 1:
            ch_num = nm.group(1) if nm else str(len(chapters) + 1)
            ch_title = nm.group(2) if nm else text
            ch_id = slug(ch_num)
            continue                                   # 장 제목은 따로 렌더

        if nm:
            n, t = nm.group(1), nm.group(2)
            sid = slug(n)
            parts = len(n.split('.'))
            parent = ''
            if parts >= 3:
                for prev in reversed(secs):
                    if prev['level'] == 2:
                        parent = prev['title']
                        break
            secs.append({'num': n, 'title': t, 'id': sid, 'level': parts,
                         'diff': None, 'ch': ch_num, 'parent': parent,
                         'chtitle': ch_title})
            if parts >= 3:
                cur_entry = secs[-1]
            out.append(f'<h{min(lvl,4)} id="{sid}" class="hd hd-{parts}">'
                       f'<span class="hd-num">{n}</span> {html.escape(t)}</h{min(lvl,4)}>')
        else:
            d = DIFF.search(text)
            if d and cur_entry:
                cur_entry['diff'] = d.group(1)
            label = re.sub(r'\s*\(난이도[^)]*\)', '', text).strip()
            badge = ''
            if d:
                stars = {'하': 1, '중': 2, '상': 3}[d.group(1)]
                badge = (f'<span class="diff diff-{d.group(1)}">신청 난이도 '
                         f'{d.group(1)} <b>{"●" * stars}{"○" * (3 - stars)}</b></span>')
            out.append(f'<h5 class="field">{html.escape(label)}{badge}</h5>')

    body = md.convert('\n'.join(out))
    md.reset()
    body = body.replace('src="../assets/img/', 'src="assets/img/')
    body = body.replace('<img ', '<img loading="lazy" ')
    chapters.append({'num': ch_num, 'title': ch_title, 'id': ch_id,
                     'html': body, 'secs': secs})

ALLNUM = {s['num'] for c in chapters for s in c['secs']}


def is_leaf(sec):
    return not any(n.startswith(sec['num'] + '.') for n in ALLNUM)


entries = [s for c in chapters for s in c['secs']
           if s['level'] >= 3 and is_leaf(s)]
data_entries = [s for c in chapters if c['num'] in ('3', '4', '5', '7')
                for s in c['secs'] if s['level'] >= 3 and is_leaf(s)]
CH_LABEL = {c['num']: c['title'] for c in chapters}

# ------------------------------------------------------------------ HTML
def nav_html():
    o = []
    for c in chapters:
        o.append(f'<li class="nav-ch"><a href="#{c["id"]}" data-t="{c["num"]} {c["title"]}">'
                 f'<span class="n">{c["num"]}</span>{html.escape(c["title"])}</a><ul>')
        for s in c['secs']:
            if s['level'] > 3:
                continue
            cls = 'lv3' if s['level'] == 3 else 'lv2'
            d = f'<i class="dot d-{s["diff"]}"></i>' if s['diff'] else ''
            key = html.escape(f'{s["num"]} {s["title"]} {s.get("parent","")} {s.get("chtitle","")}',
                              quote=True)
            o.append(f'<li class="{cls}"><a href="#{s["id"]}" '
                     f'data-t="{key}">{html.escape(s["title"])}{d}</a></li>')
        o.append('</ul></li>')
    return '\n'.join(o)


def index_html():
    o = []
    for c in chapters:
        items = [s for s in c['secs'] if s['level'] >= 3 and is_leaf(s)]
        if not items:
            continue
        o.append(f'<div class="idx-group"><h3>{c["num"]}. {html.escape(c["title"])}'
                 f' <span class="cnt" data-total="{len(items)}">{len(items)}건</span>'
                 f'</h3><div class="idx-grid">')
        for s in items:
            d = (f'<span class="chip c-{s["diff"]}">난이도 {s["diff"]}</span>'
                 if s['diff'] else '<span class="chip c-na">난이도 미표기</span>')
            key = html.escape(f'{s["num"]} {s["title"]} {s.get("parent","")} {s.get("chtitle","")}',
                              quote=True)
            org = (f'<span class="card-org">{html.escape(s["parent"])}</span>'
                   if s.get('parent') else '')
            o.append(f'<a class="card" href="#{s["id"]}" data-t="{key}">'
                     f'<span class="card-n">{s["num"]}</span>'
                     f'<span class="card-t">{html.escape(s["title"])}</span>'
                     f'{org}{d}</a>')
        o.append('</div></div>')
    return '\n'.join(o)


chapters_html = '\n'.join(
    f'<section class="chapter" id="{c["id"]}">'
    f'<header class="ch-head"><span class="ch-eyebrow">{c["num"]}장</span>'
    f'<h2>{html.escape(c["title"])}</h2></header>{c["html"]}</section>'
    for c in chapters)

n_entries = len(data_entries)
n_diff = sum(1 for e in data_entries if e['diff'])
n_org = sum(1 for c in chapters if c['num'] in ('3', '4', '5', '7')
            for s in c['secs'] if s['level'] == 2)

page = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>보건의료 데이터 자료집 — 공공·임상·연구데이터 통합 자료</title>
<meta name="description" content="보건의료 연구자가 활용 가능한 국내 공공·임상·연구데이터를 제공기관별로 정리한 자료집. 데이터 범위, 신청 절차, 결합 가능 여부를 한곳에서 확인합니다.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Gowun+Batang:wght@400;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css">
<style>
:root{{
  --paper:#EDF0EE; --surface:#FFFFFF; --ink:#0D1B20; --ink-2:#4A5B61;
  --line:#D3DAD7; --line-2:#E7EBE9; --accent:#14564A; --accent-soft:#E2EDE8;
  --ha:#2C7A5B; --jung:#8F6612; --sang:#96393B;
  --sans:'Pretendard Variable',Pretendard,-apple-system,system-ui,sans-serif;
  --serif:'Gowun Batang',serif; --mono:'IBM Plex Mono',ui-monospace,monospace;
  --rail:290px;
}}
*{{box-sizing:border-box}}
html{{scroll-behavior:smooth;scroll-padding-top:1.5rem}}
body{{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);
  font-size:16px;line-height:1.75;-webkit-font-smoothing:antialiased}}
a{{color:var(--accent);text-decoration:none}}
a:hover{{text-decoration:underline}}
:focus-visible{{outline:2px solid var(--accent);outline-offset:2px;border-radius:2px}}

/* ---------- 레이아웃 ---------- */
.wrap{{display:grid;grid-template-columns:var(--rail) minmax(0,1fr);gap:0;
  max-width:1320px;margin:0 auto}}
.rail{{position:sticky;top:0;height:100vh;overflow-y:auto;padding:2rem 1.25rem 3rem;
  border-right:1px solid var(--line);background:var(--paper)}}
main{{background:var(--surface);min-width:0;padding:0 clamp(1.25rem,4vw,4rem) 6rem;
  border-right:1px solid var(--line)}}

/* ---------- 좌측 레일 ---------- */
.rail-brand{{font-family:var(--serif);font-weight:700;font-size:1.05rem;line-height:1.4;
  letter-spacing:-.01em;margin-bottom:.35rem}}
.rail-sub{{font-size:.75rem;color:var(--ink-2);font-family:var(--mono);
  letter-spacing:.02em;margin-bottom:1.25rem}}
#q{{width:100%;padding:.6rem .75rem;border:1px solid var(--line);border-radius:3px;
  background:var(--surface);font-family:var(--sans);font-size:.85rem;color:var(--ink)}}
#q::placeholder{{color:#8B9A9F}}
.rail nav{{margin-top:1.25rem;font-size:.85rem}}
.rail nav ul{{list-style:none;margin:0;padding:0}}
.rail nav > ul > li.nav-ch{{margin-bottom:1rem}}
.nav-ch > a{{display:flex;gap:.5rem;color:var(--ink);font-weight:600;
  padding:.15rem 0;line-height:1.45}}
.nav-ch > a .n{{font-family:var(--mono);color:var(--accent);font-size:.8rem}}
.rail nav li.lv2 a,.rail nav li.lv3 a{{display:flex;align-items:center;gap:.4rem;
  color:var(--ink-2);padding:.16rem 0 .16rem .95rem;line-height:1.45;
  border-left:1px solid var(--line-2)}}
.rail nav li.lv3 a{{padding-left:1.7rem;font-size:.8rem}}
.rail nav a.on{{color:var(--accent);font-weight:600;border-left-color:var(--accent)}}
.dot{{width:6px;height:6px;border-radius:50%;flex:none;margin-left:auto}}
.d-하{{background:var(--ha)}} .d-중{{background:var(--jung)}} .d-상{{background:var(--sang)}}
.rail-foot{{margin-top:2rem;padding-top:1rem;border-top:1px solid var(--line);
  font-size:.72rem;color:var(--ink-2);line-height:1.6}}

/* ---------- 표지 ---------- */
.hero{{padding:clamp(3rem,7vw,5.5rem) 0 2.5rem;border-bottom:1px solid var(--line)}}
.hero .eyebrow{{font-family:var(--mono);font-size:.75rem;letter-spacing:.14em;
  text-transform:uppercase;color:var(--accent)}}
.hero h1{{font-family:var(--serif);font-weight:700;font-size:clamp(2.1rem,5.2vw,3.4rem);
  line-height:1.22;letter-spacing:-.02em;margin:.7rem 0 .9rem}}
.hero p{{max-width:44rem;color:var(--ink-2);margin:0 0 1.8rem;font-size:1.02rem}}
.meta{{display:flex;flex-wrap:wrap;gap:0 2.5rem;font-family:var(--mono);font-size:.78rem;
  color:var(--ink-2);border-top:1px solid var(--line-2);padding-top:1rem}}
.meta b{{display:block;font-family:var(--sans);font-size:1.25rem;color:var(--ink);
  font-weight:700;line-height:1.5}}

/* ---------- 색인 ---------- */
.idx{{padding:2.5rem 0 1rem}}
.idx > h2{{font-family:var(--serif);font-size:1.5rem;margin:0 0 .3rem}}
.idx > p{{color:var(--ink-2);font-size:.88rem;margin:0 0 1.6rem}}
.idx-group{{margin-bottom:2rem}}
.idx-group h3{{font-size:.85rem;font-weight:600;color:var(--ink-2);margin:0 0 .7rem;
  padding-bottom:.4rem;border-bottom:1px solid var(--line-2)}}
.idx-group h3 .cnt{{font-family:var(--mono);color:var(--accent);font-weight:400}}
.idx-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:.6rem}}
.card{{display:flex;flex-direction:column;gap:.3rem;padding:.75rem .85rem;
  border:1px solid var(--line);border-radius:3px;background:var(--surface);
  color:var(--ink);transition:border-color .15s,transform .15s}}
.card:hover{{border-color:var(--accent);text-decoration:none;transform:translateY(-1px)}}
.card-n{{font-family:var(--mono);font-size:.72rem;color:var(--accent)}}
.card-t{{font-weight:600;font-size:.9rem;line-height:1.4}}
.card-org{{font-size:.75rem;color:var(--ink-2)}}
.chip{{font-size:.7rem;font-family:var(--mono);padding:.08rem .4rem;border-radius:2px;
  align-self:flex-start;margin-top:.15rem}}
.c-하{{background:#E4F1EA;color:var(--ha)}}
.c-중{{background:#F6EEDC;color:var(--jung)}}
.c-상{{background:#F6E4E4;color:var(--sang)}}
.c-na{{background:var(--line-2);color:var(--ink-2)}}
.no-hit{{display:none;padding:1.5rem 0;color:var(--ink-2);font-size:.9rem}}

/* ---------- 본문 ---------- */
.chapter{{padding-top:3.5rem}}
.ch-head{{margin-bottom:1.5rem;padding-bottom:.9rem;border-bottom:2px solid var(--ink)}}
.ch-eyebrow{{font-family:var(--mono);font-size:.75rem;letter-spacing:.14em;color:var(--accent)}}
.ch-head h2{{font-family:var(--serif);font-size:clamp(1.7rem,3.6vw,2.3rem);
  margin:.35rem 0 0;letter-spacing:-.015em}}
.hd{{scroll-margin-top:1.5rem}}
.hd-num{{font-family:var(--mono);color:var(--accent);font-weight:400;margin-right:.4em}}
h2.hd{{font-size:1.35rem;margin:3rem 0 1rem;padding-top:.9rem;border-top:1px solid var(--line)}}
.ch-head + h2.hd{{border-top:0;padding-top:0;margin-top:1.6rem}}
main p,main ul,blockquote{{max-width:47rem}}
h3.hd{{font-size:1.12rem;margin:2.4rem 0 .8rem;padding:.55rem .8rem;
  background:var(--accent-soft);border-radius:3px}}
h4.hd{{font-size:1rem;margin:2rem 0 .7rem;padding-left:.7rem;
  border-left:3px solid var(--accent)}}
h5.field{{font-size:.78rem;font-weight:600;color:var(--ink-2);margin:1.5rem 0 .45rem;
  font-family:var(--mono);letter-spacing:.02em;display:flex;flex-wrap:wrap;
  align-items:center;gap:.5rem}}
h5.field::before{{content:"";width:14px;height:1px;background:var(--ink-2);flex:none}}
.diff{{font-family:var(--mono);font-size:.72rem;padding:.1rem .45rem;border-radius:2px}}
.diff b{{letter-spacing:.1em}}
.diff-하{{background:#E4F1EA;color:var(--ha)}}
.diff-중{{background:#F6EEDC;color:var(--jung)}}
.diff-상{{background:#F6E4E4;color:var(--sang)}}
main p{{margin:.7rem 0}}
main ul{{margin:.6rem 0;padding-left:1.15rem}}
main li{{margin:.28rem 0}}
main li::marker{{color:var(--accent)}}
main em{{color:var(--ink-2);font-style:normal;font-size:.85rem;font-family:var(--mono)}}
blockquote{{margin:1rem 0;padding:.8rem 1rem;background:var(--paper);
  border-left:3px solid var(--line);color:var(--ink-2);font-size:.88rem}}
blockquote p{{margin:.2rem 0}}
table{{width:100%;border-collapse:collapse;margin:1.2rem 0;font-size:.82rem;
  display:block;overflow-x:auto;white-space:normal}}
th,td{{border:1px solid var(--line);padding:.45rem .6rem;text-align:left;
  vertical-align:top;min-width:7rem}}
th{{background:var(--accent-soft);font-weight:600;position:sticky;top:0}}
tbody tr:nth-child(even){{background:#FAFBFA}}
img{{max-width:100%;height:auto;border:1px solid var(--line);border-radius:3px;
  margin:1rem 0;display:block}}
code{{font-family:var(--mono);font-size:.86em;background:var(--paper);padding:.1em .3em;
  border-radius:2px}}
.top{{position:fixed;right:1.25rem;bottom:1.25rem;background:var(--ink);color:#fff;
  width:42px;height:42px;border-radius:50%;display:none;align-items:center;
  justify-content:center;font-size:1rem;z-index:20}}
.top.show{{display:flex}}
.top:hover{{text-decoration:none;background:var(--accent)}}

/* ---------- 모바일 ---------- */
.bar{{display:none;position:sticky;top:0;z-index:30;background:var(--surface);
  border-bottom:1px solid var(--line);padding:.6rem 1rem;align-items:center;gap:.75rem}}
.bar b{{font-family:var(--serif);font-size:.95rem}}
.bar button{{margin-left:auto;background:none;border:1px solid var(--line);
  border-radius:3px;padding:.35rem .7rem;font-family:var(--sans);font-size:.8rem;
  color:var(--ink)}}
@media (max-width:940px){{
  .wrap{{grid-template-columns:1fr}}
  .bar{{display:flex}}
  .rail{{position:fixed;inset:52px 0 0 0;height:auto;z-index:29;display:none;
    border-right:0;padding-bottom:4rem}}
  .rail.open{{display:block}}
  main{{border-right:0}}
  th{{position:static}}
}}
@media (prefers-reduced-motion:reduce){{
  html{{scroll-behavior:auto}} *{{transition:none!important}}
}}
@media print{{.rail,.bar,.top,.idx{{display:none}} main{{border:0}}}}
</style>
</head>
<body>
<div class="bar">
  <b>보건의료 데이터 자료집</b>
  <button id="menu" aria-expanded="false">목차</button>
</div>

<div class="wrap">
<aside class="rail" id="rail">
  <div class="rail-brand">보건의료<br>데이터 자료집</div>
  <div class="rail-sub">공공 · 임상 · 연구데이터</div>
  <label for="q" class="sr" style="position:absolute;left:-9999px">데이터 찾기</label>
  <input id="q" type="search" placeholder="데이터·기관 이름으로 찾기" autocomplete="off">
  <nav aria-label="자료집 목차"><ul>
{nav_html()}
  </ul></nav>
  <div class="rail-foot">
    기준일 2026-08-20 · 최종초안<br>
    수치와 절차는 제공기관 정책에 따라 변경될 수 있습니다.
  </div>
</aside>

<main>
  <header class="hero">
    <div class="eyebrow">Korean Healthcare Data Reference</div>
    <h1>보건의료 데이터 자료집</h1>
    <p>보건의료 연구자가 활용할 수 있는 국내 공공·임상·연구데이터를 제공기관별로 정리했습니다.
       데이터의 범위와 최신성, 신청 절차와 난이도, 결합 가능 여부를 항목마다 같은 형식으로 확인할 수 있습니다.</p>
    <div class="meta">
      <div>수록 데이터<b>{n_entries}건</b></div>
      <div>제공기관 그룹<b>{n_org}곳</b></div>
      <div>신청 난이도 표기<b>{n_diff}건</b></div>
      <div>기준일<b>2026.08.20</b></div>
    </div>
  </header>

  <section class="idx" id="index">
    <h2>데이터 색인</h2>
    <p>검색창에 기관명이나 데이터명을 입력하면 아래 목록과 목차가 함께 좁혀집니다.
       난이도는 각 데이터의 ‘데이터 획득’ 항목에 표기된 신청 난이도입니다.</p>
{index_html()}
    <p class="no-hit" id="nohit">검색어와 맞는 데이터가 없습니다. 기관명(예: 질병관리청)이나 데이터명 일부로 다시 찾아보세요.</p>
  </section>

{chapters_html}
</main>
</div>

<a href="#" class="top" id="top" aria-label="맨 위로">↑</a>

<script>
(function(){{
  var q=document.getElementById('q');
  var cards=[].slice.call(document.querySelectorAll('.card'));
  var navs=[].slice.call(document.querySelectorAll('.rail nav a'));
  var groups=[].slice.call(document.querySelectorAll('.idx-group'));
  var nohit=document.getElementById('nohit');

  function norm(s){{return (s||'').toLowerCase().replace(/\\s+/g,'');}}
  function filter(){{
    var v=norm(q.value), hits=0;
    cards.forEach(function(c){{
      var on=!v||norm(c.dataset.t).indexOf(v)>-1;
      c.style.display=on?'':'none'; if(on)hits++;
    }});
    groups.forEach(function(g){{
      var n=g.querySelectorAll('.card:not([style*="none"])').length;
      g.style.display=n?'':'none';
      var c=g.querySelector('.cnt');
      c.textContent=(v? n+'건 / 전체 '+c.dataset.total+'건' : c.dataset.total+'건');
    }});
    navs.forEach(function(a){{
      var li=a.parentElement;
      if(li.classList.contains('nav-ch')){{return;}}
      li.style.display=(!v||norm(a.dataset.t).indexOf(v)>-1)?'':'none';
    }});
    [].slice.call(document.querySelectorAll('.nav-ch')).forEach(function(ch){{
      var any=[].slice.call(ch.querySelectorAll('li')).some(function(li){{
        return li.style.display!=='none';
      }});
      ch.style.display=(!v||any)?'':'none';
    }});
    nohit.style.display=(v&&!hits)?'block':'none';
  }}
  q.addEventListener('input',filter);

  var menu=document.getElementById('menu'), rail=document.getElementById('rail');
  menu.addEventListener('click',function(){{
    var open=rail.classList.toggle('open');
    menu.setAttribute('aria-expanded',open);
    menu.textContent=open?'닫기':'목차';
  }});
  rail.addEventListener('click',function(e){{
    if(e.target.tagName==='A'&&window.innerWidth<=940){{
      rail.classList.remove('open');menu.textContent='목차';
      menu.setAttribute('aria-expanded','false');
    }}
  }});

  var top=document.getElementById('top');
  var heads=[].slice.call(document.querySelectorAll('.chapter, .hd'));
  var map={{}};
  navs.forEach(function(a){{map[a.getAttribute('href').slice(1)]=a;}});
  function spy(){{
    top.classList.toggle('show',window.scrollY>600);
    var cur=null;
    heads.forEach(function(h){{
      if(h.getBoundingClientRect().top<120) cur=h.id;
    }});
    navs.forEach(function(a){{a.classList.remove('on');}});
    if(cur&&map[cur]) map[cur].classList.add('on');
  }}
  var tick=false;
  window.addEventListener('scroll',function(){{
    if(!tick){{requestAnimationFrame(function(){{spy();tick=false;}});tick=true;}}
  }});
  spy();
}})();
</script>
</body>
</html>
"""

open(f'{ROOT}/index.html', 'w', encoding='utf-8').write(page)
open(f'{ROOT}/.nojekyll', 'w').write('')
print('index.html', len(page), 'bytes | entries', n_entries, '| diff', n_diff)
print('chapters:', [(c['num'], c['title'], len(c['secs'])) for c in chapters])
