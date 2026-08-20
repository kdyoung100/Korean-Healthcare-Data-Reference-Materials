#!/usr/bin/env python3
"""HWPX -> GitHub-ready Markdown repository."""
import os, re, shutil, unicodedata
from lxml import etree
from PIL import Image

SRC = "/home/claude/hwpx"
OUT = "/home/claude/health-data-catalog"
NS = {
    'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph',
    'hc': 'http://www.hancom.co.kr/hwpml/2011/core',
    'opf': 'http://www.idpf.org/2007/opf/',
}
QP = lambda t: '{%s}%s' % (NS['hp'], t)
QC = lambda t: '{%s}%s' % (NS['hc'], t)

# ---- binary manifest -------------------------------------------------
hpf = etree.parse(os.path.join(SRC, 'Contents/content.hpf'))
BIN = {it.get('id'): it.get('href').replace('BinData/', '')
       for it in hpf.iter('{%s}item' % NS['opf']) if it.get('href', '').startswith('BinData')}

# images used in headers/footers (logos) — excluded from output
CHROME_IMGS = set()


def clean(s):
    s = s.replace('\u3000', ' ').replace('\xa0', ' ')
    s = re.sub(r'[ \t]+', ' ', s)
    return s.strip()


def para_text(p):
    parts = []
    for run in p.findall(QP('run')):
        for child in run:
            tag = etree.QName(child).localname
            if tag == 't':
                parts.append(''.join(child.itertext()))
            elif tag == 'tab':
                parts.append(' ')
            elif tag == 'lineBreak':
                parts.append(' ')
    return clean(''.join(parts))


def cell_text(tc):
    sub = tc.find(QP('subList'))
    if sub is None:
        return ''
    lines = [para_text(p) for p in sub.findall(QP('p'))]
    txt = '<br>'.join(x for x in lines if x)
    return txt.replace('|', '\\|')


def table_md(tbl):
    """Build a grid honouring colSpan/rowSpan via cellAddr."""
    cells = []
    maxr = maxc = 0
    for tr in tbl.findall(QP('tr')):
        for tc in tr.findall(QP('tc')):
            addr = tc.find(QP('cellAddr'))
            span = tc.find(QP('cellSpan'))
            r = int(addr.get('rowAddr')) if addr is not None else 0
            c = int(addr.get('colAddr')) if addr is not None else 0
            rs = int(span.get('rowSpan', 1)) if span is not None else 1
            cs = int(span.get('colSpan', 1)) if span is not None else 1
            cells.append((r, c, rs, cs, cell_text(tc)))
            maxr = max(maxr, r + rs)
            maxc = max(maxc, c + cs)
    if not cells:
        return ''
    grid = [['' for _ in range(maxc)] for _ in range(maxr)]
    for r, c, rs, cs, txt in cells:
        for i in range(rs):
            for j in range(cs):
                if r + i < maxr and c + j < maxc:
                    grid[r + i][c + j] = txt if (i == 0 and j == 0) else (txt if txt else '')
    # merged continuation cells: repeat value (markdown has no spans)
    for r, c, rs, cs, txt in cells:
        for i in range(rs):
            for j in range(cs):
                if (i or j) and r + i < maxr and c + j < maxc:
                    grid[r + i][c + j] = txt if j == 0 else ''
    # drop fully empty trailing columns
    while maxc > 1 and all(not row[maxc - 1].strip() for row in grid):
        for row in grid:
            row.pop()
        maxc -= 1
    out = ['| ' + ' | '.join(grid[0]) + ' |',
           '|' + '|'.join([' --- '] * maxc) + '|']
    for row in grid[1:]:
        out.append('| ' + ' | '.join(row) + ' |')
    return '\n'.join(out)


def strip_chrome(root):
    """Remove headers/footers (repeated logos & page furniture)."""
    for tag in ('header', 'footer'):
        for el in root.findall('.//' + QP(tag)):
            for img in el.iter(QC('img')):
                CHROME_IMGS.add(img.get('binaryItemIDRef'))
            el.getparent().remove(el)


HEAD_NUM = re.compile(r'^\d+(\.\d+)*[\.\s]')


def convert(path):
    root = etree.parse(path).getroot()
    strip_chrome(root)
    blocks = []          # list of (kind, payload)
    for p in root.findall(QP('p')):
        style = p.get('styleIDRef')
        text = para_text(p)
        if text:
            if text.startswith('■'):
                blocks.append(('hb', text.lstrip('■ ').strip()))
            elif style == '3':
                blocks.append(('h1', text))
            elif style == '4':
                blocks.append(('h2', text))
            elif style == '5':
                if HEAD_NUM.match(text) and len(text) < 60:
                    blocks.append(('hn', text))
                elif text.startswith('·'):
                    blocks.append(('li', text.lstrip('· ').strip()))
                else:
                    blocks.append(('p', text))
            elif style == '6':
                if HEAD_NUM.match(text) and len(text) < 60:
                    blocks.append(('hn', text))
                else:
                    blocks.append(('p', text))
            elif style == '7':
                if text.startswith('·'):
                    blocks.append(('li', text.lstrip('· ').strip()))
                elif text.startswith('-'):
                    blocks.append(('li2', text.lstrip('- ').strip()))
                else:
                    blocks.append(('p', text))
            elif style == '0' and text.startswith('그림'):
                blocks.append(('cap', text))
            else:
                blocks.append(('p', text))

        for tbl in p.iter(QP('tbl')):
            blocks.append(('tbl', table_md(tbl)))
        for pic in p.iter(QP('pic')):
            img = pic.find(QC('img'))
            if img is not None:
                blocks.append(('img', img.get('binaryItemIDRef')))
    return blocks


DOTS = re.compile(r'^(\d+(?:\.\d+)*)')


def render(blocks, img_rel='../assets/img'):
    md, used = [], []
    last_lvl, last_cap = 2, None
    for kind, val in blocks:
        if kind == 'hn':
            m = DOTS.match(val)
            lvl = min(len(m.group(1).split('.')), 5) if m else 3
            last_lvl = lvl
            md += ['', '#' * lvl + ' ' + val, '']
            continue
        if kind == 'hb':
            lvl = min(last_lvl + 1, 6)
            md += ['', '#' * lvl + ' ' + val, '']
            continue
        if kind == 'h1':
            last_lvl = 1
            md += ['', '# ' + val, '']
        elif kind == 'h2':
            last_lvl = 2
            md += ['', '## ' + val, '']
        elif kind == 'h3':
            md += ['', '### ' + val, '']
        elif kind == 'h4':
            md += ['', '#### ' + val, '']
        elif kind == 'li':
            md.append('- ' + val)
        elif kind == 'li2':
            md.append('  - ' + val)
        elif kind == 'cap':
            last_cap = val
            md += ['', f'*{val}*', '']
        elif kind == 'tbl':
            if not val:
                continue
            lines = val.split('\n')
            if lines[1].strip() == '| --- |':      # single-column box -> quote
                cells = [l.strip().strip('|').strip()
                         for i, l in enumerate(lines) if i != 1]
                cells = [c for c in cells if c]
                if not cells:
                    continue
                text = '<br>'.join(cells)
                for ln in text.split('<br>'):
                    if ln.strip():
                        md.append('> ' + ln.strip())
                md.append('')
                continue
            if not [l for l in lines[2:] if l.replace('|', '').strip()]:
                continue
            md += ['', val, '']
        elif kind == 'img':
            if val in CHROME_IMGS:
                continue
            fn = BIN.get(val, '')
            if not fn:
                continue
            png = os.path.splitext(fn)[0] + '.png'
            used.append(fn)
            alt = (last_cap or '미리보기').replace('[', '(').replace(']', ')')
            md += ['', f'![{alt}]({img_rel}/{png})', '']
        else:
            md += ['', val, '']
    txt = '\n'.join(md)
    txt = re.sub(r'\n{3,}', '\n\n', txt).strip() + '\n'
    return txt, used


# ---------------------------------------------------------------- build
if os.path.exists(OUT):
    shutil.rmtree(OUT)
os.makedirs(os.path.join(OUT, 'docs'))
os.makedirs(os.path.join(OUT, 'assets/img'))
os.makedirs(os.path.join(OUT, 'source'))

blocks = convert(os.path.join(SRC, 'Contents/section1.xml'))

# split by chapter (h1)
chapters, cur = [], None
for b in blocks:
    if b[0] == 'h1':
        cur = [b[1], []]
        chapters.append(cur)
    elif cur is not None:
        cur[1].append(b)

SLUG = {
    '1': '01-overview', '2': '02-data-summary', '3': '03-public-data',
    '4': '04-clinical-data', '5': '05-research-data',
    '6': '06-platforms', '7': '07-appendix',
}

all_used, toc = [], []
for title, body in chapters:
    num = re.match(r'(\d+)', title).group(1)
    slug = SLUG.get(num, 'ch' + num)
    txt, used = render([('h1', title)] + body)
    all_used += used
    open(f'{OUT}/docs/{slug}.md', 'w', encoding='utf-8').write(txt)
    toc.append((title, slug, [t for k, t in body if k == 'h2']))

# copy + normalise images
for fn in sorted(set(all_used)):
    src = os.path.join(SRC, 'BinData', fn)
    dst = os.path.join(OUT, 'assets/img', os.path.splitext(fn)[0] + '.png')
    im = Image.open(src)
    if im.mode not in ('RGB', 'RGBA', 'P'):
        im = im.convert('RGB')
    im.save(dst, 'PNG', optimize=True)

shutil.copy('/mnt/user-data/uploads/보건의료_데이터_자료집_최종초안_260820.hwpx',
            os.path.join(OUT, 'source'))

print('chapters:', [(t, s) for t, s, _ in toc])
print('images:', sorted(set(all_used)))
import json
json.dump([[t, s, subs] for t, s, subs in toc], open('/home/claude/toc.json', 'w'), ensure_ascii=False)
