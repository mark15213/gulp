#!/usr/bin/env python3
"""Build the Gulp one-pager HTML (Sediment philosophy) with embedded fonts."""
import base64, random, os, pathlib

HERE = pathlib.Path(__file__).parent
FONTS = HERE / "fonts"
random.seed(7)  # deterministic motif

def font_face(family, file, weight="400", style="normal"):
    data = base64.b64encode((FONTS / file).read_bytes()).decode()
    return (f"@font-face{{font-family:'{family}';font-weight:{weight};"
            f"font-style:{style};src:url(data:font/ttf;base64,{data}) format('truetype');}}")

faces = "".join([
    font_face("Young", "YoungSerif-Regular.ttf"),
    font_face("Instr", "InstrumentSerif-Regular.ttf"),
    font_face("Instr", "InstrumentSerif-Italic.ttf", style="italic"),
    font_face("Work", "WorkSans-Regular.ttf"),
    font_face("Work", "WorkSans-Bold.ttf", weight="700"),
    font_face("Work", "WorkSans-Italic.ttf", style="italic"),
    font_face("Mono", "GeistMono-Regular.ttf"),
    font_face("Mono", "GeistMono-Bold.ttf", weight="700"),
])

# ---- generative motifs (SVG) -------------------------------------------------
def scatter(w, h, n, seed):
    r = random.Random(seed)
    out = []
    for _ in range(n):
        x, y = r.uniform(2, w-2), r.uniform(2, h-2)
        rad = r.uniform(1.4, 3.6)
        op = r.uniform(0.30, 0.72)
        col = "#C24E2C" if r.random() < 0.10 else "#1A1C1B"
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rad:.1f}" fill="{col}" opacity="{op:.2f}"/>')
    return "".join(out)

def funnel(w, h, n, seed):
    r = random.Random(seed)
    fx, fy = w/2, h-6
    lines = []
    for _ in range(n):
        sx = r.uniform(4, w-4)
        sy = r.uniform(2, h*0.30)
        midx = (sx+fx)/2 + r.uniform(-8, 8)
        lines.append(f'<path d="M{sx:.1f},{sy:.1f} Q{midx:.1f},{(sy+fy)/2:.1f} {fx:.1f},{fy:.1f}" '
                     f'fill="none" stroke="#1A1C1B" stroke-width="0.8" opacity="0.32"/>')
    node = (f'<circle cx="{fx:.1f}" cy="{fy:.1f}" r="6.5" fill="#0F5C4A"/>'
            f'<circle cx="{fx:.1f}" cy="{fy:.1f}" r="11" fill="none" stroke="#0F5C4A" stroke-width="1" opacity="0.5"/>')
    return "".join(lines) + node

def grid_cards(w, h, cols, rows, seed):
    r = random.Random(seed)
    out = []
    gap = 6
    cw = (w - gap*(cols-1)) / cols
    ch = (h - gap*(rows-1)) / rows
    for i in range(cols):
        for j in range(rows):
            x = i*(cw+gap); y = j*(ch+gap)
            if r.random() < 0.16:
                fill, op = "#C24E2C", "0.92"
            else:
                fill, op = "#0F5C4A", f"{r.uniform(0.55,0.95):.2f}"
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cw:.1f}" height="{ch:.1f}" rx="2.2" fill="{fill}" opacity="{op}"/>')
    return "".join(out)

intake_svg = f'<svg viewBox="0 0 220 132" width="100%" height="132">{scatter(220,132,46,11)}</svg>'
digest_svg = f'<svg viewBox="0 0 220 132" width="100%" height="132">{funnel(220,132,18,21)}</svg>'
mastery_svg = f'<svg viewBox="0 0 220 132" width="100%" height="132">{grid_cards(220,132,9,5,31)}</svg>'

# left-margin "core sample": scattered at top -> ordered at bottom
def core_sample(w, h, seed):
    r = random.Random(seed)
    out = []
    bands = 26
    for b in range(bands):
        y = 6 + b*((h-12)/bands)
        order = b/bands  # 0 top -> 1 bottom
        count = int(7 - order*4)
        for k in range(max(count,1)):
            if order < 0.5:
                x = r.uniform(2, w-2)
            else:
                slots = max(count,1)
                x = (w/(slots+1))*(k+1) + r.uniform(-1.5,1.5)*(1-order)
            rad = 2.2 - order*0.7
            op = 0.25 + order*0.45
            col = "#C24E2C" if (order>0.85 and k==0) else ("#0F5C4A" if order>0.5 else "#1A1C1B")
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{rad:.1f}" fill="{col}" opacity="{op:.2f}"/>')
    return f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}">{"".join(out)}</svg>'

core_svg = core_sample(34, 1900, 5)

# ---- content -----------------------------------------------------------------
win = [
    ("RECALL", "source management, a daily knowledge stream, a real mastery model"),
    ("READWISE", "testable knowledge, not just resurfaced highlights"),
    ("NOTEBOOKLM", "a long-term, cross-topic system with real spaced repetition"),
    ("REMNOTE", "starts from your real stream, not manual notes"),
    ("CUBOX", "active mastery after reading, not just retrieval"),
    ("OBSIDIAN / NOTION / TANA", "the system builds itself — no setup, no upkeep"),
]
mvp = [
    ("Universal inbox", "links · PDF · video · podcast · audio · screenshots — WeChat, extension, share sheet, email-in"),
    ("AI knowledge pack", "summary, background, terms, claims, counter-views, links to prior knowledge"),
    ("Card-based KB", "Source · Claim · Concept · Question · Card · Conversation · Insight"),
    ("Gulp mode", "daily 5–10 min: new + due reviews, retests, MCQ, explain-it, apply-it"),
    ("Conversation capture", "chat any card; on exit, extract new points & corrected misconceptions"),
    ("Mastery + scheduling", "right / wrong / fuzzy → interval; FSRS later"),
]
principles = [
    "Digestion, not collection",
    "Mastery is the unit, not the bookmark",
    "Forward anything — capture must be effortless",
    "The system builds itself",
    "Conversations are assets",
]

win_html = "".join(
    f'<div class="win"><span class="vs">vs</span><span class="wname">{a}</span>'
    f'<span class="wadd">{b}</span></div>' for a,b in win)

mvp_html = "".join(
    f'<div class="mvp"><span class="num">{i+1:02d}</span>'
    f'<div><div class="mt">{t}</div><div class="md">{d}</div></div></div>'
    for i,(t,d) in enumerate(mvp))

pr_html = "".join(
    f'<div class="pr"><span class="pn">{i+1:02d}</span><span class="pt">{p}</span></div>'
    for i,p in enumerate(principles))

stage = lambda label, sub, svg, arrow: f'''
<div class="stage">
  <div class="stagebox">{svg}</div>
  <div class="stagelab">{label}</div>
  <div class="stagesub">{sub}</div>
</div>{'<div class="arrow">&rarr;</div>' if arrow else ''}'''

flow = (stage("INTAKE", "a universal inbox for anything you consume", intake_svg, True)
      + stage("DIGEST", "AI turns each input into a knowledge pack, not a summary", digest_svg, True)
      + stage("MASTERY", "cards, tested &amp; scheduled until you own it", mastery_svg, False))

html = f'''<!doctype html><html><head><meta charset="utf-8"><style>
{faces}
@page{{size:13.5417in 24.5417in;margin:0;}}
*{{margin:0;padding:0;box-sizing:border-box;-webkit-print-color-adjust:exact;print-color-adjust:exact;}}
:root{{
  --paper:#F2EEE3; --paper2:#E9E2D2; --ink:#1A1C1B; --soft:#55584F;
  --green:#0F5C4A; --ember:#C24E2C; --line:rgba(26,28,27,.20);
}}
html,body{{background:#cfc8b8;}}
.page{{position:relative;width:1300px;height:2356px;background:var(--paper);
  padding:84px 88px 0;overflow:hidden;}}
.frame{{position:absolute;inset:26px;border:1px solid var(--line);pointer-events:none;}}
.core{{position:absolute;left:40px;top:300px;opacity:.9;}}
.tlc{{position:absolute;left:40px;top:40px;font-family:Mono;font-size:11px;
  letter-spacing:.14em;color:var(--soft);}}
.trc{{position:absolute;right:40px;top:40px;font-family:Mono;font-size:11px;
  letter-spacing:.14em;color:var(--soft);text-align:right;}}
.wrap{{position:relative;margin-left:46px;}}

/* masthead */
.eyebrow{{display:flex;justify-content:space-between;align-items:baseline;
  font-family:Mono;font-size:12.5px;letter-spacing:.22em;color:var(--soft);
  padding-bottom:14px;border-bottom:1px solid var(--ink);}}
.mast{{display:flex;align-items:flex-end;justify-content:space-between;margin-top:20px;}}
.word{{font-family:Young;font-size:150px;line-height:.9;color:var(--ink);letter-spacing:-.01em;}}
.word .dot{{color:var(--ember);}}
.mastr{{font-family:Instr;font-style:italic;font-size:25px;color:var(--soft);
  text-align:right;max-width:330px;line-height:1.25;padding-bottom:14px;}}

/* hero */
.hero{{margin-top:46px;}}
.pos{{font-family:Young;font-size:50px;line-height:1.12;color:var(--ink);
  letter-spacing:-.012em;max-width:1060px;}}
.pos em{{font-family:Instr;font-style:italic;color:var(--green);}}
.posb{{font-family:Work;font-size:20.5px;line-height:1.5;color:var(--soft);
  margin-top:18px;max-width:880px;}}
.tag{{font-family:Instr;font-style:italic;font-size:33px;color:var(--ember);
  margin-top:26px;letter-spacing:.005em;}}

/* why this matters */
.why{{margin-top:40px;background:var(--paper2);border-left:3px solid var(--green);
  padding:30px 38px 32px;display:flex;gap:42px;align-items:flex-start;}}
.whymark{{font-family:Young;font-size:80px;color:var(--green);line-height:.7;}}
.whyq{{font-family:Instr;font-style:italic;font-size:29px;line-height:1.28;color:var(--ink);}}
.whyb{{font-family:Work;font-size:18px;line-height:1.55;color:var(--soft);margin-top:14px;max-width:880px;}}

/* section label */
.slab{{font-family:Mono;font-size:13px;letter-spacing:.26em;color:var(--soft);
  display:flex;align-items:center;gap:14px;margin:44px 0 22px;}}
.slab::after{{content:"";flex:1;height:1px;background:var(--line);}}
.slab .ix{{color:var(--ember);}}

/* flow */
.flow{{display:flex;align-items:flex-start;gap:0;}}
.stage{{flex:1;}}
.stagebox{{background:#fff8;border:1px solid var(--line);height:152px;padding:10px 12px;
  display:flex;align-items:center;}}
.stagelab{{font-family:Mono;font-weight:700;font-size:16px;letter-spacing:.16em;
  color:var(--ink);margin-top:16px;}}
.stagesub{{font-family:Work;font-size:14.5px;line-height:1.4;color:var(--soft);
  margin-top:7px;max-width:300px;}}
.arrow{{font-family:Mono;font-size:30px;color:var(--ember);padding:54px 22px 0;align-self:flex-start;}}
.loop{{margin-top:24px;font-family:Mono;font-size:14.5px;letter-spacing:.10em;
  color:var(--ink);background:var(--ink);color:var(--paper);padding:14px 22px;
  display:flex;justify-content:center;gap:14px;}}
.loop b{{color:#E9C24A;font-weight:400;}}

/* two-col */
.cols{{display:grid;grid-template-columns:1fr 1.18fr;gap:54px;margin-top:6px;}}
.win{{display:grid;grid-template-columns:24px 1fr;gap:0 12px;padding:12px 0;
  border-bottom:1px solid var(--line);align-items:baseline;}}
.win:first-of-type{{border-top:1px solid var(--line);}}
.vs{{font-family:Instr;font-style:italic;font-size:17px;color:var(--ember);grid-row:span 2;}}
.wname{{font-family:Mono;font-weight:700;font-size:14px;letter-spacing:.13em;color:var(--ink);}}
.wadd{{font-family:Work;font-size:16px;line-height:1.4;color:var(--soft);grid-column:2;margin-top:3px;}}
.mvp{{display:grid;grid-template-columns:42px 1fr;gap:0 14px;padding:11px 0;border-bottom:1px solid var(--line);}}
.mvp:first-of-type{{border-top:1px solid var(--line);}}
.num{{font-family:Young;font-size:26px;color:var(--green);line-height:1;}}
.mt{{font-family:Work;font-weight:700;font-size:17px;color:var(--ink);}}
.md{{font-family:Work;font-size:14.5px;line-height:1.42;color:var(--soft);margin-top:3px;}}
.ng{{margin-top:18px;font-family:Work;font-size:14.5px;color:var(--soft);line-height:1.5;}}
.ng b{{font-family:Mono;font-size:11.5px;letter-spacing:.2em;color:var(--ember);font-weight:700;}}

/* principles */
.prs{{display:grid;grid-template-columns:repeat(5,1fr);gap:20px;}}
.pr{{border-top:2px solid var(--green);padding-top:12px;}}
.pn{{font-family:Mono;font-size:12px;color:var(--ember);letter-spacing:.1em;}}
.pt{{display:block;font-family:Work;font-weight:700;font-size:16.5px;line-height:1.28;
  color:var(--ink);margin-top:8px;}}

/* success */
.succ{{margin-top:42px;background:var(--green);color:var(--paper);
  padding:30px 40px;display:flex;gap:32px;align-items:center;}}
.succl{{font-family:Mono;font-size:13px;letter-spacing:.24em;color:#E9C24A;
  writing-mode:vertical-rl;transform:rotate(180deg);white-space:nowrap;}}
.succt{{font-family:Instr;font-style:italic;font-size:26px;line-height:1.32;}}
.foot{{display:flex;justify-content:space-between;margin-top:18px;font-family:Mono;
  font-size:11px;letter-spacing:.16em;color:var(--soft);}}
</style></head><body>
<div class="page">
  <div class="frame"></div>
  <div class="tlc">GULP / FIG.01</div>
  <div class="trc">INTERNAL NORTH-STAR · v1<br>2026.06.18</div>
  <div class="core">{core_svg}</div>
  <div class="wrap">

    <div class="eyebrow"><span>PRODUCT ONE-PAGER</span><span>DIGEST · ABSORB · MASTER</span></div>
    <div class="mast">
      <div class="word">Gulp<span class="dot">.</span></div>
      <div class="mastr">a personal learning system<br>for the age of information overload</div>
    </div>

    <div class="hero">
      <div class="pos">Save anything and you still forget it. Gulp <em>digests</em> what you consume into knowledge you can <em>recall, test, and reuse.</em></div>
      <div class="tag">Forward anything. Gulp turns it into knowledge you can actually remember.</div>
    </div>

    <div class="slab"><span class="ix">00</span>WHY THIS MATTERS</div>
    <div class="why">
      <div class="whymark">&ldquo;</div>
      <div>
        <div class="whyq">The smarter AI gets, the more it does for us — and the less we do for ourselves.</div>
        <div class="whyb">Gulp makes the opposite bet: AI&rsquo;s highest use is to make the person using it stronger. Same powerful models — pointed at your growth, not just your output. You stay the one who understands.</div>
      </div>
    </div>

    <div class="slab"><span class="ix">01</span>THE CORE LOOP</div>
    <div class="flow">{flow}</div>
    <div class="loop"><span>FORWARD ANYTHING</span><b>&rarr;</b><span>KNOWLEDGE PACK</span><b>&rarr;</b><span>5 MIN IN GULP MODE</span><b>&rarr;</b><span>MASTERY TRACKED</span></div>

    <div class="cols">
      <div>
        <div class="slab"><span class="ix">02</span>WHY WE WIN</div>
        {win_html}
      </div>
      <div>
        <div class="slab"><span class="ix">03</span>MVP — THE SHARP LOOP</div>
        {mvp_html}
        <div class="ng"><b>NOT, IN v1:</b>&nbsp; a general PKM · a read-later reader · a team tool · a content platform · notes-first.</div>
      </div>
    </div>

    <div class="slab"><span class="ix">04</span>PRINCIPLES</div>
    <div class="prs">{pr_html}</div>

    <div class="succ">
      <div class="succl">SUCCESS</div>
      <div class="succt">Users return to Gulp mode unforced and get measurably sharper week over week — cards graduated, retention climbing. If people <span style="color:#E9C24A">learn</span> from Gulp instead of just stashing in it, we win.</div>
    </div>
    <div class="foot"><span>GULP — PRODUCT DEFINITION</span><span>SEDIMENT / SPECIMEN 01</span><span>PG. 01 / 01</span></div>

  </div>
</div>
</body></html>'''

out = HERE / "one-pager.html"
out.write_text(html, encoding="utf-8")
print("wrote", out, len(html), "bytes")
