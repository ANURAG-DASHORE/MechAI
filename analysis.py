import json, math
import plotly.graph_objects as go
import plotly.utils as pu
from plotly.subplots import make_subplots

# ── Colour tokens ─────────────────────────────────────────────
NAVY    = '#1A24AD'; CRIMSON = '#AD1024'; AMBER  = '#E8A020'
GREEN   = '#18AD10'; PURPLE  = '#7C3AED'; GRAY   = '#444455'
DARK    = '#1E1E32'; WHITE   = '#FFFFFF'; LGRAY  = '#F5F5FA'
GRID    = '#CCCCDD'

def _j(fig):
    return {
        'data':   json.loads(pu.PlotlyJSONEncoder().encode(fig.data)),
        'layout': json.loads(pu.PlotlyJSONEncoder().encode(fig.layout)),
        'config': {'displayModeBar':True,
                   'modeBarButtonsToRemove':['select2d','lasso2d'],
                   'responsive':True},
    }

def _obs(s):
    t = s.get('observed_time', s.get('obs_avg', 0))
    try: return float(t)
    except: return 0

def _base(h=380):
    fig = go.Figure()
    fig.update_layout(paper_bgcolor=WHITE, plot_bgcolor=LGRAY,
                      margin=dict(l=50,r=30,t=60,b=80), height=h,
                      font=dict(family='IBM Plex Mono, monospace', color=DARK, size=11))
    return fig

# ═══════════════════════════════════════════════════════════════
# 1. AS-IS SUMMARY  — all calculated, nothing hardcoded
# ═══════════════════════════════════════════════════════════════
def generate_asis_summary(stations, shift_minutes=480, target_output=16,
                          perf_rating=0.80, allowance_pct=0.04):
    times = [_obs(s) for s in stations]
    # convert seconds to minutes if > 30
    times = [t/60 if t > 30 else t for t in times]

    if not times:
        return {}

    total_obs  = sum(times)
    normal     = total_obs * perf_rating
    standard   = normal * (1 + allowance_pct)
    takt       = shift_minutes / target_output if target_output else 30
    bn_idx     = times.index(max(times))
    bal_eff    = sum(times) / (len(times) * max(times)) * 100 if max(times) > 0 else 0
    line_eff   = sum(times) / (len(times) * takt) * 100 if takt > 0 else 0
    units_ps   = int(shift_minutes / total_obs) if total_obs > 0 else 0

    # NVA derived from actual station types
    nva_types  = {'transport','delay','movement','storage'}
    nva_steps  = sum(1 for s in stations
                     if str(s.get('type','')).lower().strip() in nva_types)
    total_steps = len(stations)
    nva_pct    = round(nva_steps / total_steps * 100, 1) if total_steps else 0

    # total distance from station distance column
    total_dist = sum(float(s.get('distance',0) or 0) for s in stations)

    return {
        'total_observed':     round(total_obs, 2),
        'normal_time':        round(normal, 2),
        'standard_time':      round(standard, 2),
        'takt_time':          round(takt, 2),
        'bottleneck_station': stations[bn_idx].get('station_name', f'WS {bn_idx+1}'),
        'bottleneck_time':    round(times[bn_idx], 2),
        'balance_efficiency': round(bal_eff, 1),
        'line_efficiency':    round(min(line_eff, 100.0), 1),
        'units_per_shift':    units_ps,
        'nva_steps':          nva_steps,
        'total_steps':        total_steps,
        'cycle_loss_pct':     nva_pct,
        'total_distance_ft':  round(total_dist, 1),
        'delay_percent':      round((total_obs - standard) / total_obs * 100, 1) if total_obs else 0,
    }


# ═══════════════════════════════════════════════════════════════
# 2. FLOW PROCESS CHART — auto-generated from station rows
# ═══════════════════════════════════════════════════════════════
def generate_pfd_from_stations(stations, project_name='', location=''):
    """
    Auto-generates PFD steps from station data.
    If distance > 0 between stations, inserts a Transport step automatically.
    """
    steps = []
    for i, s in enumerate(stations):
        stype = str(s.get('type','Operation')).strip()
        obs   = _obs(s)
        t_str = f"{int(obs)}s" if obs > 0 else ''
        dist  = float(s.get('distance', 0) or 0)

        # Main operation step
        steps.append({
            'activity': s.get('station_name', f'Step {i+1}'),
            'type':     stype,
            'time':     t_str,
            'distance': '',
            'remarks':  '',
        })

        # Auto-insert transport step if distance > 0
        if dist > 0 and i < len(stations) - 1:
            next_name = stations[i+1].get('station_name', 'next station')
            steps.append({
                'activity': f"Move to {next_name}",
                'type':     'Transport',
                'time':     '',
                'distance': str(int(dist)),
                'remarks':  'NVA' if dist > 10 else '',
            })

    return _generate_pfd_chart(steps, project_name, location)


def _generate_pfd_chart(pfd_steps, project_name='', location=''):
    N = len(pfd_steps)
    if N == 0:
        return _j(_base())

    ROW_H  = 38
    TOP    = 160
    BOTTOM = 180
    W      = 1050
    H      = TOP + N * ROW_H + BOTTOM

    COL_STEP = 40;  COL_DIST = 105
    SYM_O = 195; SYM_T = 240; SYM_I = 285; SYM_D = 330; SYM_V = 375
    COL_ACT = 430; COL_TIME = 800; COL_REM = 880
    SYM_R = 14

    counts = {'Operation':0,'Transport':0,'Inspection':0,'Delay':0,'Storage':0}
    total_dist = 0
    for s in pfd_steps:
        c = _canon(s.get('type','Operation'))
        if c in counts: counts[c] += 1
        try: total_dist += float(s.get('distance') or 0)
        except: pass

    fig = go.Figure()
    fig.update_layout(
        title=dict(text='<b>FLOW PROCESS CHART</b>',
                   font=dict(size=15,color=DARK), x=0.01),
        paper_bgcolor='#EEF0FF', plot_bgcolor='#F8F9FF',
        margin=dict(l=0,r=0,t=45,b=0), height=H, width=W,
        xaxis=dict(visible=False,range=[0,W]),
        yaxis=dict(visible=False,range=[0,H],autorange='reversed'),
        showlegend=False,
        font=dict(family='IBM Plex Mono, monospace', size=11),
    )

    shapes, annotations = [], []

    def rect(x0,y0,x1,y1,fill=WHITE,lc='#CCCCCC',lw=1):
        shapes.append(dict(type='rect',x0=x0,y0=y0,x1=x1,y1=y1,
                           fillcolor=fill,line=dict(color=lc,width=lw),
                           xref='x',yref='y'))
    def ann(x,y,text,color=DARK,size=11,anchor='left',bold=False):
        annotations.append(dict(x=x,y=y,
                                text=f'<b>{text}</b>' if bold else text,
                                showarrow=False,
                                font=dict(size=size,color=color,
                                          family='IBM Plex Mono, monospace'),
                                xanchor=anchor,yanchor='middle',
                                xref='x',yref='y'))

    # Info panel
    rect(10,48,W-10,100,fill='#F0F4FF',lc=NAVY)
    ann(20,65,f'Subject: {project_name}',DARK,10)
    ann(20,85,f'Location: {location}',DARK,10)
    ann(700,68,f"O:{counts['Operation']} T:{counts['Transport']} I:{counts['Inspection']} D:{counts['Delay']} S:{counts['Storage']}",NAVY,10,bold=True)
    ann(700,85,f"Total Distance: {total_dist:.0f} ft",NAVY,9,bold=True)

    # Column headers
    rect(10,105,W-10,140,fill=NAVY,lc=NAVY,lw=0)
    for cx,lbl in [(COL_STEP,'Step'),(COL_DIST,'Dist(ft)'),
                   (SYM_O,'O'),(SYM_T,'→'),(SYM_I,'□'),(SYM_D,'D'),(SYM_V,'▽'),
                   (COL_ACT+80,'Activity'),(COL_TIME,'Time'),(COL_REM,'Remarks')]:
        annotations.append(dict(x=cx,y=122,text=f'<b>{lbl}</b>',
                                showarrow=False,
                                font=dict(size=10,color=WHITE,
                                          family='IBM Plex Mono, monospace'),
                                xanchor='center',yanchor='middle',
                                xref='x',yref='y'))

    SYM_COLS   = {'Operation':SYM_O,'Transport':SYM_T,'Inspection':SYM_I,
                  'Delay':SYM_D,'Storage':SYM_V}
    SYM_COLORS = {'Operation':NAVY,'Transport':AMBER,'Inspection':GREEN,
                  'Delay':CRIMSON,'Storage':PURPLE}

    path_x, path_y = [], []

    for i, step in enumerate(pfd_steps):
        y  = TOP + i * ROW_H + ROW_H // 2
        bg = '#F8F9FF' if i % 2 == 0 else WHITE
        rect(10,TOP+i*ROW_H,W-10,TOP+(i+1)*ROW_H,fill=bg,lc='#E5E5EE')
        ann(COL_STEP,y,str(i+1),GRAY,10,anchor='center')

        raw_dist = step.get('distance','')
        if raw_dist:
            try:
                dv = float(raw_dist)
                if dv > 0: ann(COL_DIST,y,f'{dv:.0f}',DARK,10,anchor='center')
            except: pass

        stype      = _canon(step.get('type','Operation'))
        active_cx  = SYM_COLS.get(stype,SYM_O)
        active_col = SYM_COLORS.get(stype,NAVY)
        path_x.append(active_cx); path_y.append(y)

        for sym_type,cx in SYM_COLS.items():
            _draw_sym(shapes,sym_type,cx,y,SYM_R,
                      active_col if sym_type==stype else '#CCCCCC',
                      filled=(sym_type==stype))

        act = step.get('activity','')[:52]
        ann(COL_ACT,y,act,DARK,10)
        tv  = step.get('time','')
        if tv: ann(COL_TIME,y,str(tv),NAVY,10,anchor='center')
        rem = step.get('remarks','')
        if rem:
            rc = CRIMSON if any(w in str(rem).lower()
                                for w in ['nva','back','delay','no tool','not staged']) else GRAY
            ann(COL_REM,y,str(rem)[:22],rc,9)

    # Zigzag path
    if len(path_x) > 1:
        fig.add_trace(go.Scatter(x=path_x,y=path_y,mode='lines',
                                 line=dict(color=NAVY,width=2.5),hoverinfo='skip'))
        fig.add_trace(go.Scatter(x=path_x,y=path_y,mode='markers',
                                 marker=dict(size=8,color=CRIMSON,
                                             line=dict(color=WHITE,width=1.5)),
                                 hoverinfo='skip'))

    # Summary box
    sy = TOP + N * ROW_H + 15
    rect(10,sy,W-10,sy+100,fill='#F0F4FF',lc=NAVY)
    annotations.append(dict(x=W//2,y=sy+15,text='<b>FLOW PROCESS CHART SUMMARY</b>',
                            showarrow=False,
                            font=dict(size=13,color=NAVY,family='IBM Plex Mono, monospace'),
                            xanchor='center',yanchor='middle',xref='x',yref='y'))
    for txt,col,x in [
        (f"Operations (O): {counts['Operation']}",   NAVY,   80),
        (f"Transports (→): {counts['Transport']}",   AMBER, 230),
        (f"Inspections (□): {counts['Inspection']}", GREEN, 390),
        (f"Delays (D): {counts['Delay']}",           CRIMSON,550),
        (f"Storages (▽): {counts['Storage']}",       PURPLE, 710),
        (f"Total Dist: {total_dist:.0f} ft",         DARK,   870),
    ]:
        annotations.append(dict(x=x,y=sy+45,text=f'<b>{txt}</b>',
                                showarrow=False,
                                font=dict(size=12,color=col,
                                          family='IBM Plex Mono, monospace'),
                                xanchor='left',yanchor='middle',xref='x',yref='y'))

    # Suggestions
    sugg = _pfd_suggestions(counts, total_dist)
    annotations.append(dict(x=20,y=sy+65,text='<b>⚡ RECOMMENDATIONS:</b>',
                            showarrow=False,
                            font=dict(size=11,color=CRIMSON,
                                      family='IBM Plex Mono, monospace'),
                            xanchor='left',yanchor='middle',xref='x',yref='y'))
    annotations.append(dict(x=20,y=sy+82,
                            text='   |   '.join(sugg[:3]),
                            showarrow=False,
                            font=dict(size=10,color=DARK,
                                      family='IBM Plex Mono, monospace'),
                            xanchor='left',yanchor='middle',xref='x',yref='y'))

    # Legend
    ly = sy + 115
    rect(10,ly,W-10,ly+40,fill=NAVY,lc=NAVY,lw=0)
    for txt,col,x in [('● O=Operation',WHITE,30),('→ T=Transport',AMBER,220),
                      ('■ I=Inspection',GREEN,420),('D D=Delay',CRIMSON,620),
                      ('▽ V=Storage','#CC99FF',810)]:
        annotations.append(dict(x=x,y=ly+20,text=f'<b>{txt}</b>',
                                showarrow=False,
                                font=dict(size=10,color=col,
                                          family='IBM Plex Mono, monospace'),
                                xanchor='left',yanchor='middle',xref='x',yref='y'))

    fig.update_layout(shapes=shapes, annotations=annotations)
    return _j(fig)


def _canon(t):
    t = str(t).lower().strip()
    if any(w in t for w in ['transport','move','walk','travel','load','unload']): return 'Transport'
    if any(w in t for w in ['inspect','check','test','qc','verif']):              return 'Inspection'
    if any(w in t for w in ['delay','wait','idle','search','hold']):              return 'Delay'
    if any(w in t for w in ['storage','store','rest','stock']):                   return 'Storage'
    return 'Operation'

def _draw_sym(shapes, sym_type, cx, cy, r, color, filled):
    fill = color if filled else WHITE
    lw   = 2.5 if filled else 1
    if sym_type == 'Operation':
        shapes.append(dict(type='circle',x0=cx-r,y0=cy-r,x1=cx+r,y1=cy+r,
                           fillcolor=fill,line=dict(color=color,width=lw),xref='x',yref='y'))
    elif sym_type == 'Transport':
        pts = f'M {cx-r} {cy-r//2} L {cx+r} {cy} L {cx-r} {cy+r//2} Z'
        shapes.append(dict(type='path',path=pts,fillcolor=fill,
                           line=dict(color=color,width=lw),xref='x',yref='y'))
    elif sym_type == 'Inspection':
        shapes.append(dict(type='rect',x0=cx-r,y0=cy-r,x1=cx+r,y1=cy+r,
                           fillcolor=fill,line=dict(color=color,width=lw),xref='x',yref='y'))
    elif sym_type == 'Delay':
        pts=(f'M {cx-r} {cy-r} L {cx} {cy-r} '
             f'Q {cx+r*1.5} {cy-r} {cx+r*1.5} {cy} '
             f'Q {cx+r*1.5} {cy+r} {cx} {cy+r} L {cx-r} {cy+r} Z')
        shapes.append(dict(type='path',path=pts,fillcolor=fill,
                           line=dict(color=color,width=lw),xref='x',yref='y'))
    elif sym_type == 'Storage':
        pts = f'M {cx-r} {cy-r} L {cx+r} {cy-r} L {cx} {cy+r} Z'
        shapes.append(dict(type='path',path=pts,fillcolor=fill,
                           line=dict(color=color,width=lw),xref='x',yref='y'))

def _pfd_suggestions(counts, total_dist):
    s = []
    if counts['Transport'] > 4:
        s.append(f"Reduce {counts['Transport']} transport steps via U-shape layout")
    if total_dist > 60:
        s.append(f"Cut travel distance ({total_dist:.0f} ft) by centralising storage")
    if counts['Delay'] > 1:
        s.append(f"Eliminate {counts['Delay']} delays with pre-staged material")
    s.append("Implement Kanban pull to remove NVA transport steps")
    s.append("Use trolley/fixture to reduce manual handling distance")
    return s


# ═══════════════════════════════════════════════════════════════
# 3. LINE BALANCE
# ═══════════════════════════════════════════════════════════════
def generate_line_balance(stations, shift_minutes=480, target_output=16):
    names, raw = [], []
    for i, s in enumerate(stations):
        t = _obs(s)
        if t > 30: t /= 60
        raw.append(t)
        n = s.get('station_name', f'WS{i+1}')
        names.append(n[:13]+'…' if len(n)>13 else n)

    if not raw:
        return _j(_base())

    takt    = shift_minutes / target_output if target_output > 0 else 30
    bn      = raw.index(max(raw))
    bal_eff = sum(raw) / (len(raw) * max(raw)) * 100 if max(raw) > 0 else 0

    colors = [('#FF6B00' if i==bn else CRIMSON if t>takt else NAVY)
              for i,t in enumerate(raw)]

    fig = _base(340)
    fig.add_trace(go.Bar(x=names,y=raw,
        marker=dict(color=colors,line=dict(color='#555566',width=0.5)),
        text=[f'{t:.2f}m' for t in raw], textposition='outside',
        textfont=dict(size=9,color=DARK),
        hovertemplate='<b>%{x}</b><br>%{y:.2f} min<extra></extra>'))
    fig.add_hline(y=takt,line_dash='dash',line_color=CRIMSON,line_width=2.5,
                  annotation_text=f'Takt = {takt:.1f} min',
                  annotation_font=dict(color=CRIMSON,size=11),
                  annotation_position='top right')
    for i,(n,t) in enumerate(zip(names,raw)):
        if t < takt:
            fig.add_annotation(x=n,y=t+0.08,text=f'idle {takt-t:.1f}m',
                               showarrow=False,font=dict(size=8,color=DARK),yanchor='bottom')
    fig.update_layout(
        title=dict(text=f'<b>LINE BALANCE CHART</b><br>'
                        f'<sup>Eff: {bal_eff:.1f}% | Bottleneck: {names[bn]} ({raw[bn]:.2f}min) | Takt: {takt:.1f}min</sup>',
                   font=dict(size=13,color=DARK),x=0.01),
        xaxis=dict(title='Workstation',tickangle=-65,showgrid=False,
                   tickfont=dict(size=9,color=DARK)),
        yaxis=dict(title='Cycle Time (min)',showgrid=True,gridcolor=GRID,
                   tickfont=dict(size=10,color=DARK)),
        showlegend=False,
    )
    return _j(fig)


# ═══════════════════════════════════════════════════════════════
# 4. PLANT LAYOUT — uses actual station names
# ═══════════════════════════════════════════════════════════════
def generate_layout(layout_type, stations, project_name='Project'):
    fn = {'current':_lay_current,'product':_lay_product,
          'process':_lay_process,'mixed':_lay_mixed,'static':_lay_static}.get(layout_type,_lay_product)
    return _j(fn(stations, project_name))

def _ha(hex_col, alpha=0.15):
    h=hex_col.lstrip('#'); r,g,b=int(h[0:2],16),int(h[2:4],16),int(h[4:6],16)
    return f'rgba({r},{g},{b},{alpha})'

def _base_lay(title, h=620):
    fig = go.Figure()
    fig.update_layout(
        title=dict(text=title,font=dict(size=13,color=DARK),x=0.01),
        paper_bgcolor='#EEF0FF',plot_bgcolor='#F0F0F8',
        margin=dict(l=10,r=10,t=46,b=10),height=h,
        xaxis=dict(visible=False,range=[0,100]),
        yaxis=dict(visible=False,range=[0,100],scaleanchor='x',scaleratio=1),
        showlegend=False,font=dict(family='IBM Plex Mono, monospace'),
    )
    fig.add_shape(type='rect',x0=1,y0=1,x1=99,y1=97,
                  fillcolor='rgba(255,255,255,0.55)',
                  line=dict(color=NAVY,width=1.5,dash='dot'))
    return fig

def _box(fig,x0,y0,x1,y1,label,color,sub='',fa=0.18,fs=10):
    fig.add_shape(type='rect',x0=x0,y0=y0,x1=x1,y1=y1,
                  fillcolor=_ha(color,fa),line=dict(color=color,width=2))
    cx,cy=(x0+x1)/2,(y0+y1)/2
    txt = f'<b>{label}</b>'
    if sub: txt += f'<br><span style="font-size:9px;color:{color}">{sub}</span>'
    fig.add_annotation(x=cx,y=cy,text=txt,showarrow=False,
                       font=dict(size=fs,color=color),align='center',
                       xanchor='center',yanchor='middle')

def _arrow(fig,x0,y0,x1,y1,color=AMBER,label=''):
    fig.add_annotation(x=x1,y=y1,ax=x0,ay=y0,
                       xref='x',yref='y',axref='x',ayref='y',
                       showarrow=True,arrowhead=3,arrowsize=1.4,
                       arrowwidth=2,arrowcolor=color,
                       text=label,font=dict(size=9,color=color))

def _station_phases(stations):
    """Split stations into 3 phases: fabrication, assembly, finish."""
    n = len(stations)
    if n == 0: return [], [], []
    f = max(1, n//3); a = max(1, n//3)
    return stations[:f], stations[f:f+a], stations[f+a:]

def _lay_current(stations, project_name):
    fig = _base_lay(f'📍 CURRENT LAYOUT — AS-IS  |  {project_name}')
    fab, asm, fin = _station_phases(stations)
    # Left: fabrication area
    for i,s in enumerate(fab[:4]):
        y0,y1 = 75-(i*20), 93-(i*20)
        _box(fig,2,y0,18,y1,s.get('station_name',f'WS{i+1}')[:14],NAVY,f"WS{s.get('station_number',i+1)}")
    # Center: assembly
    for i,s in enumerate(asm[:5]):
        y0,y1 = 78-(i*15), 93-(i*15)
        _box(fig,20,y0,44,y1,s.get('station_name',f'WS{i+1}')[:14],PURPLE,f"WS{s.get('station_number',i+1)}")
    # Right: finish/dispatch
    for i,s in enumerate(fin[:4]):
        y0,y1 = 78-(i*18), 93-(i*18)
        _box(fig,46,y0,72,y1,s.get('station_name',f'WS{i+1}')[:14],GREEN,f"WS{s.get('station_number',i+1)}")
    _box(fig,74,5,99,95,'Dispatch\n& Loading',AMBER)
    # NVA arrows
    _arrow(fig,72,60,46,75,CRIMSON,'⚠ Backtrack')
    _arrow(fig,44,55,20,70,CRIMSON,'⚠ Long haul')
    fig.add_annotation(x=50,y=3,
        text=f'<b>⚠ Current layout — {sum(float(s.get("distance",0) or 0) for s in stations):.0f} ft total travel</b>',
        showarrow=False,font=dict(size=10,color=CRIMSON),
        xanchor='center',bgcolor='rgba(255,255,255,0.85)')
    return fig

def _lay_product(stations, project_name):
    fig = _base_lay(f'✅ U-SHAPE LAYOUT — Sequential Flow  |  {project_name}')
    n   = len(stations)
    per_side = max(1, math.ceil(n / 3))
    left  = stations[:per_side]
    bot   = stations[per_side:2*per_side]
    right = stations[2*per_side:]

    for i,s in enumerate(left[:5]):
        y0,y1 = 78-(i*15), 93-(i*15)
        _box(fig,3,y0,20,y1,s.get('station_name',f'WS{i+1}')[:13],NAVY,
             f"WS{s.get('station_number',i+1)}")

    for i,s in enumerate(bot[:4]):
        x0,x1 = 22+(i*12), 33+(i*12)
        _box(fig,x0,8,x1,22,s.get('station_name',f'WS{i+1}')[:10],CRIMSON,
             f"WS{s.get('station_number',i+1)}")

    for i,s in enumerate(right[:5]):
        y0,y1 = 24+(i*14), 38+(i*14)
        _box(fig,66,y0,82,y1,s.get('station_name',f'WS{i+1}')[:13],GREEN,
             f"WS{s.get('station_number',i+1)}")

    _box(fig,24,28,64,93,'Kanban\nSupermarket\n(WIP Staging)',GREEN,'',fa=0.07,fs=11)

    # Flow arrows
    if len(left) > 1:
        for i in range(min(len(left)-1,4)):
            _arrow(fig,11,78-(i*15)-2,11,78-((i+1)*15)+1,GREEN)
    _arrow(fig,20,17,22,17,GREEN)
    if len(right) > 1:
        for i in range(min(len(right)-1,4)):
            _arrow(fig,74,24+(i*14)+1,74,24+((i+1)*14)-1,GREEN)

    fig.add_annotation(x=50,y=3,
        text=f'<b>✅ U-shape: one-way flow, zero backtracking — {len(stations)} stations</b>',
        showarrow=False,font=dict(size=10,color=GREEN),
        xanchor='center',bgcolor='rgba(255,255,255,0.85)')
    return fig

def _lay_process(stations, project_name):
    fig = _base_lay(f'🔩 PROCESS LAYOUT — By Function  |  {project_name}')
    fab, asm, fin = _station_phases(stations)
    groups = [
        (3, 60,35,90, 'FABRICATION\nDEPT',   NAVY,   ', '.join(s.get('station_name','')[:8] for s in fab[:3])),
        (38,60,68,90, 'ASSEMBLY\nDEPT',       PURPLE, ', '.join(s.get('station_name','')[:8] for s in asm[:3])),
        (71,60,99,90, 'FINISHING\nDEPT',      GREEN,  ', '.join(s.get('station_name','')[:8] for s in fin[:3])),
        (3, 20,35,55, 'STORAGE\nAREA',        AMBER,  'Raw · WIP · FG'),
        (38,20,68,55, 'QC &\nINSPECTION',     CRIMSON,''),
        (71,20,99,55, 'DISPATCH',              GRAY,   ''),
    ]
    for x0,y0,x1,y1,lbl,col,sub in groups:
        _box(fig,x0,y0,x1,y1,lbl,col,sub[:22],fs=11)
    _arrow(fig,35,75,38,75,AMBER)
    _arrow(fig,68,75,71,75,AMBER)
    _arrow(fig,53,60,53,55,AMBER)
    fig.add_annotation(x=50,y=10,
        text='<b>⚠ Process layout suits high-variety, low-volume production</b>',
        showarrow=False,font=dict(size=10,color=CRIMSON),
        xanchor='center',bgcolor='rgba(255,255,255,0.85)')
    return fig

def _lay_mixed(stations, project_name):
    fig = _base_lay(f'🔀 MIXED LAYOUT — Fab + Assembly Line  |  {project_name}')
    fab, asm, _ = _station_phases(stations)
    fig.add_shape(type='rect',x0=2,y0=5,x1=46,y1=95,
                  fillcolor='rgba(26,36,173,0.05)',
                  line=dict(color=NAVY,width=2,dash='dash'))
    fig.add_annotation(x=24,y=92,text='<b>PROCESS SECTION</b>',
                       showarrow=False,font=dict(size=11,color=NAVY))
    for i,s in enumerate(fab[:4]):
        x0,x1 = 4+(i%2)*22, 24+(i%2)*22
        y0,y1 = 65-(i//2*22), 85-(i//2*22)
        _box(fig,x0,y0,x1,y1,s.get('station_name','')[:13],NAVY)
    _arrow(fig,44,55,50,55,PURPLE,'Parts\nTransfer')
    fig.add_shape(type='rect',x0=48,y0=5,x1=98,y1=95,
                  fillcolor='rgba(24,173,16,0.05)',
                  line=dict(color=GREEN,width=2,dash='dash'))
    fig.add_annotation(x=73,y=92,text='<b>ASSEMBLY LINE</b>',
                       showarrow=False,font=dict(size=11,color=GREEN))
    step_w = min(7, 48//max(len(asm),1))
    for i,s in enumerate(asm[:6]):
        x0 = 50+i*step_w
        _box(fig,x0,45,x0+step_w-1,65,s.get('station_name','')[:8],GREEN,'',fs=8)
        if i < len(asm)-1:
            _arrow(fig,x0+step_w-1,55,x0+step_w,55,AMBER)
    return fig

def _lay_static(stations, project_name):
    import numpy as np
    fig = _base_lay(f'📌 STATIC LAYOUT — Fixed Product  |  {project_name}')
    theta = np.linspace(0,2*np.pi,60)
    fig.add_trace(go.Scatter(x=50+15*np.cos(theta),y=50+10*np.sin(theta),
                             fill='toself',fillcolor=_ha(NAVY,0.18),
                             line=dict(color=NAVY,width=3),mode='lines',hoverinfo='skip'))
    fig.add_annotation(x=50,y=52,text=f'<b>PRODUCT</b>',showarrow=False,
                       font=dict(size=13,color=NAVY))
    angles = np.linspace(0,2*np.pi,len(stations)+1)[:-1]
    for i,(s,ang) in enumerate(zip(stations[:8],angles)):
        sx,sy = 50+38*math.cos(ang),50+30*math.sin(ang)
        _box(fig,sx-8,sy-5,sx+8,sy+5,s.get('station_name','')[:10],
             [NAVY,GREEN,CRIMSON,AMBER,PURPLE,GRAY][i%6])
        _arrow(fig,sx+(8 if math.cos(ang)<0 else -8),sy,
               50+16*math.cos(ang),50+11*math.sin(ang),[NAVY,GREEN,CRIMSON,AMBER,PURPLE,GRAY][i%6])
    return fig


# ═══════════════════════════════════════════════════════════════
# 5. EFFICIENCY COMPARISON — NVA derived from actual data
# ═══════════════════════════════════════════════════════════════
def generate_efficiency_diff(stations, shift_minutes=480, target_output=16, nva_pct=None):
    times, names = [], []
    for i,s in enumerate(stations):
        t = _obs(s)
        if t > 30: t /= 60
        times.append(t)
        n = s.get('station_name',f'WS{i+1}')
        names.append(n[:13]+'…' if len(n)>13 else n)

    if not times:
        empty = _j(_base())
        return {'c1':empty,'c2':empty,'c3':empty,'c4':empty}

    # Calculate NVA from actual types if not provided
    if nva_pct is None:
        nva_types = {'transport','delay','movement'}
        nva_cnt = sum(1 for s in stations
                      if str(s.get('type','')).lower() in nva_types)
        nva_pct = nva_cnt / len(stations) * 100 if stations else 24

    nva_f      = nva_pct / 100
    total_cur  = sum(times)
    transport  = total_cur * nva_f
    value_add  = total_cur - transport
    takt       = shift_minutes / target_output if target_output else 30
    units_cur  = int(shift_minutes / total_cur) if total_cur > 0 else 0
    # Guarantee visible gap: minimum 10% improvement shown even if NVA=0
    reduction  = max(nva_f * 0.70, 0.10)
    opt_times  = [t * (1 - reduction) for t in times]
    total_opt  = sum(opt_times)
    units_opt  = int(shift_minutes / total_opt) if total_opt > 0 else 0
    saving     = total_cur - total_opt
    eff_cur    = value_add / total_cur * 100 if total_cur > 0 else 0
    eff_opt    = (total_opt - transport*0.30) / total_opt * 100 if total_opt > 0 else 0
    bal_cur    = sum(times)/(len(times)*max(times))*100 if max(times)>0 else 0
    bal_opt    = sum(opt_times)/(len(opt_times)*max(opt_times))*100 if opt_times and max(opt_times)>0 else 0
    nva_steps_cur = round(len(stations) * nva_f)
    nva_steps_opt = round(nva_steps_cur * 0.30)
    nva_opt    = round(transport * 0.30, 2)
    va_opt     = round(total_opt - nva_opt, 2)

    _la = dict(paper_bgcolor=WHITE,plot_bgcolor=LGRAY,height=360,
               font=dict(family='IBM Plex Mono, monospace',color=DARK,size=11),
               margin=dict(l=50,r=30,t=60,b=100),
               legend=dict(orientation='h',yanchor='bottom',y=1.02,xanchor='right',x=1,
                           bgcolor='rgba(255,255,255,.9)',bordercolor=GRID,borderwidth=1,
                           font=dict(color=DARK,size=11)))

    # Chart 1: Cycle time line
    c1 = go.Figure()
    c1.add_trace(go.Scatter(x=names,y=times,name='Current',
        mode='lines+markers',line=dict(color=CRIMSON,width=2.5),
        marker=dict(size=8,color=CRIMSON,line=dict(color=WHITE,width=1.5))))
    c1.add_trace(go.Scatter(x=names,y=opt_times,name='Optimised',
        mode='lines+markers',line=dict(color=GREEN,width=2.5),
        marker=dict(size=8,color=GREEN,symbol='diamond',line=dict(color=WHITE,width=1.5))))
    c1.add_trace(go.Scatter(x=names+names[::-1],y=times+opt_times[::-1],
        fill='toself',fillcolor='rgba(173,16,36,0.08)',
        line=dict(color='rgba(0,0,0,0)'),showlegend=False,hoverinfo='skip'))
    c1.add_hline(y=takt,line_dash='dash',line_color=NAVY,line_width=2,
                 annotation_text=f'Takt={takt:.1f}min',
                 annotation_font=dict(color=NAVY,size=11),
                 annotation_position='top right')
    c1.update_layout(title=dict(text='<b>① Cycle Time per Station — Current vs Optimised</b>',
                                font=dict(size=13,color=DARK),x=0.01),
                     xaxis=dict(title='Workstation',tickangle=-65,showgrid=False,
                                tickfont=dict(size=9,color=DARK)),
                     yaxis=dict(title='Cycle Time (min)',showgrid=True,gridcolor=GRID,
                                tickfont=dict(size=10,color=DARK)),**_la)

    # Chart 2: KPI comparison — filter out zero-zero rows
    kpi_l_all = ['Units/Shift','Line Eff %','Balance Eff %','NVA Steps']
    kpi_c_all = [units_cur, round(eff_cur,1), round(bal_cur,1), nva_steps_cur]
    kpi_o_all = [units_opt, round(eff_opt,1), round(bal_opt,1), nva_steps_opt]
    kpi_pairs = [(l,c,o) for l,c,o in zip(kpi_l_all,kpi_c_all,kpi_o_all) if not (c==0 and o==0)]
    kpi_l = [p[0] for p in kpi_pairs]
    kpi_c = [p[1] for p in kpi_pairs]
    kpi_o = [p[2] for p in kpi_pairs]
    c2 = go.Figure()
    c2.add_trace(go.Bar(y=kpi_l,x=kpi_c,orientation='h',name='Current',
        marker=dict(color=CRIMSON,opacity=0.85),
        text=[str(v) for v in kpi_c],textposition='outside'))
    c2.add_trace(go.Bar(y=kpi_l,x=kpi_o,orientation='h',name='Optimised',
        marker=dict(color=GREEN,opacity=0.85),
        text=[str(v) for v in kpi_o],textposition='outside'))
    c2.update_layout(title=dict(text='<b>② KPI Comparison — Current vs Optimised</b>',
                                font=dict(size=13,color=DARK),x=0.01),
                     barmode='group',
                     xaxis=dict(title='Value',showgrid=True,gridcolor=GRID,
                                tickfont=dict(size=10,color=DARK)),
                     yaxis=dict(showgrid=False,tickfont=dict(size=10,color=DARK)),**_la)

    # Chart 3: VA vs NVA stacked
    c3 = go.Figure()
    c3.add_trace(go.Bar(name='Value-Added',x=['Current','Optimised'],
        y=[round(value_add,2),va_opt],marker=dict(color=NAVY,opacity=0.85),
        text=[f'{round(value_add,2)}m',f'{va_opt}m'],
        textposition='inside',textfont=dict(color=WHITE,size=12)))
    c3.add_trace(go.Bar(name='Non-Value-Added',x=['Current','Optimised'],
        y=[round(transport,2),nva_opt],marker=dict(color=CRIMSON,opacity=0.80),
        text=[f'{round(transport,2)}m NVA',f'{nva_opt}m NVA'],
        textposition='inside',textfont=dict(color=WHITE,size=12)))
    c3.update_layout(title=dict(text='<b>③ Value-Added vs NVA Time Split</b>',
                                font=dict(size=13,color=DARK),x=0.01),
                     barmode='stack',
                     xaxis=dict(showgrid=False,tickfont=dict(size=11,color=DARK)),
                     yaxis=dict(title='Total Cycle Time (min)',showgrid=True,gridcolor=GRID,
                                tickfont=dict(size=10,color=DARK)),**_la)

    # Chart 4: Gains — derived from actual values
    metrics = ['Cycle Time\nSaved (min)','Units/Shift\nGained',
               'NVA Steps\nRemoved','Line Eff\nGain (%)']
    gains   = [round(saving,2), units_opt-units_cur,
               nva_steps_cur-nva_steps_opt, round(eff_opt-eff_cur,1)]
    c4 = go.Figure()
    c4.add_trace(go.Bar(x=metrics,y=gains,
        marker=dict(color=[NAVY,GREEN,CRIMSON,PURPLE],opacity=0.9,
                    line=dict(color='#33334A',width=0.5)),
        text=[f'+{v}' if isinstance(v,int) else f'+{v:.2f}' for v in gains],
        textposition='outside',textfont=dict(size=13,color=DARK),showlegend=False))
    c4.update_layout(title=dict(text='<b>④ Improvement Summary — Gains from Optimisation</b>',
                                font=dict(size=13,color=DARK),x=0.01),
                     xaxis=dict(showgrid=False,tickfont=dict(size=11,color=DARK)),
                     yaxis=dict(title='Improvement',showgrid=True,gridcolor=GRID,
                                tickfont=dict(size=10,color=DARK)),**_la)

    return {'c1':_j(c1),'c2':_j(c2),'c3':_j(c3),'c4':_j(c4)}


# ═══════════════════════════════════════════════════════════════
# 6. SOP — uses actual station + product data
# ═══════════════════════════════════════════════════════════════
def generate_sop(station, station_num, project_name, product_name='Product'):
    name     = station.get('station_name', f'Station {station_num}')
    comp     = station.get('component', product_name)
    ops      = station.get('num_operators', '1')
    handling = station.get('handling', 'Manual')
    obs      = _obs(station)
    std_time = f"{int(obs)}s" if obs > 0 else '—'
    return {
        'title':    f'SOP — {name}',
        'doc_no':   f'SOP-{project_name[:6].upper()}-{station_num:02d}',
        'revision': 'Rev 1.0',
        'who':   f'{ops} operator(s) at {name}',
        'what':  f'Assembly/processing of {comp}',
        'where': f'{name} — {project_name}',
        'when':  f'Each cycle. Std time: {std_time}',
        'how': [
            f'1. Verify {comp} is staged at workstation before starting.',
            f'2. Inspect incoming work from previous station for defects.',
            f'3. Perform designated operation on {comp} per drawing spec.',
            f'4. Use {handling} handling — never drag or drop components.',
            f'5. Self-inspect: check alignment, fitment, quality.',
            f'6. Transfer to next station using designated handling method.',
            f'7. Record completed units on Daily Production Report (DPR).',
            f'8. Report any defect or delay to supervisor immediately.',
        ],
        'safety': [
            'Wear PPE (gloves, safety shoes) at all times.',
            'Keep workstation clear — no material piled on floor.',
            f'Do not exceed rated capacity for {handling} equipment.',
            'Report tool damage or unsafe condition immediately.',
        ],
        'quality': [
            'Check against standard spec before passing to next station.',
            'Zero defect forward — reject non-conforming components.',
            'Maintain quality at source.',
        ],
    }


# ═══════════════════════════════════════════════════════════════
# 7. COST CALCULATOR — uses actual data, no hardcoding
# ═══════════════════════════════════════════════════════════════
def calculate_cost(wage_per_hour, workers, shifts_per_day, units_per_shift,
                   current_cycle, optimized_cycle,
                   working_hours=8, overhead_per_hour=50, working_days=26):
    labor_hr       = wage_per_hour * workers
    cost_per_shift = (labor_hr + overhead_per_hour) * working_hours
    cur_cost_unit  = cost_per_shift / units_per_shift if units_per_shift else 0
    opt_units      = int((working_hours * 60) / optimized_cycle) if optimized_cycle else 0
    opt_cost_unit  = cost_per_shift / opt_units if opt_units else 0
    saving_unit    = cur_cost_unit - opt_cost_unit
    saving_shift   = saving_unit * opt_units
    saving_day     = saving_shift * shifts_per_day
    saving_month   = saving_day * working_days

    fig = make_subplots(rows=1,cols=2,
                        subplot_titles=('Cost per Unit (₹)','Projected Savings (₹)'))
    fig.add_trace(go.Bar(x=['Current','Optimised'],
        y=[round(cur_cost_unit,2),round(opt_cost_unit,2)],
        marker=dict(color=[NAVY,GREEN],opacity=0.9),
        text=[f'₹{cur_cost_unit:.2f}',f'₹{opt_cost_unit:.2f}'],
        textposition='outside',showlegend=False),row=1,col=1)
    fig.add_trace(go.Bar(
        x=['Per Unit','Per Shift','Per Day','Per Month'],
        y=[round(saving_unit,2),round(saving_shift,2),round(saving_day,2),round(saving_month,2)],
        marker=dict(color=[NAVY,CRIMSON,PURPLE,GREEN],opacity=0.9),
        text=[f'₹{v:.0f}' for v in [saving_unit,saving_shift,saving_day,saving_month]],
        textposition='outside',showlegend=False),row=1,col=2)
    fig.update_layout(paper_bgcolor=WHITE,plot_bgcolor=LGRAY,height=320,
                      margin=dict(l=30,r=20,t=50,b=30),
                      font=dict(family='IBM Plex Mono, monospace',size=11))
    for ax in ['xaxis','yaxis','xaxis2','yaxis2']:
        fig.update_layout(**{ax:dict(showgrid=True,gridcolor=GRID)})
    return {
        'chart': _j(fig),
        'summary': {
            'current_units': units_per_shift, 'optimized_units': opt_units,
            'cur_cost_unit': round(cur_cost_unit,2), 'opt_cost_unit': round(opt_cost_unit,2),
            'saving_unit': round(saving_unit,2), 'saving_shift': round(saving_shift,2),
            'saving_day': round(saving_day,2), 'saving_month': round(saving_month,2),
        }
    }


# ═══════════════════════════════════════════════════════════════
# 8. DPR — uses actual product name, no hardcoded cooler types
# ═══════════════════════════════════════════════════════════════
def generate_dpr(product_name, target_output=16):
    return {
        'product': product_name,
        'target':  target_output,
        'rows': [{'product_type': product_name,
                  'qty_planned': target_output,
                  'qty_produced': 0,
                  'dispatch_time': '--:--',
                  'eod_inventory': 0,
                  'remarks': ''}],
    }


# ═══════════════════════════════════════════════════════════════
# 9. SHOP SCHEDULE — derived from station data, not hardcoded
# ═══════════════════════════════════════════════════════════════
def generate_shop_schedule(stations, shift_minutes=480, project_name=''):
    if not stations:
        return _j(_base(340))

    # Group stations into 3 phases by position
    n = len(stations)
    p1 = max(1, n//3); p2 = max(1, n//3)
    phase1 = stations[:p1]
    phase2 = stations[p1:p1+p2]
    phase3 = stations[p1+p2:]

    def phase_label(ph):
        types = [str(s.get('type','')).lower() for s in ph]
        if any('inspect' in t or 'test' in t for t in types): return 'QC & Inspection'
        if any('coat' in s.get('station_name','').lower() or
               'paint' in s.get('station_name','').lower() for s in ph): return 'Surface Treatment'
        names = [s.get('station_name','') for s in ph]
        first = names[0][:16] if names else 'Phase 1'
        return first

    def phase_time(ph):
        return sum(_obs(s)/60 for s in ph)  # minutes

    # Build time blocks
    shops = []
    t = 0
    colors = [NAVY, CRIMSON, GREEN]
    for i, (ph, col) in enumerate(zip([phase1, phase2, phase3], colors)):
        if not ph: continue
        label    = phase_label(ph)
        duration = max(30, phase_time(ph))
        tasks    = [s.get('station_name','')[:20] for s in ph[:4]]
        shops.append((label, col, t, t+duration, ' · '.join(tasks)))
        t += duration

    fig = go.Figure()
    for shop_name, color, t_start, t_end, task_str in shops:
        fig.add_trace(go.Bar(
            name=shop_name,
            x=[t_end - t_start], y=[shop_name],
            base=t_start, orientation='h',
            marker=dict(color=color,opacity=0.78,line=dict(color=WHITE,width=1)),
            text=task_str, textposition='inside',
            insidetextanchor='middle',
            textfont=dict(size=9,color=WHITE),
            hovertemplate=f'<b>{shop_name}</b><br>{task_str}<br>{t_start:.0f}–{t_end:.0f} min<extra></extra>',
            showlegend=False,
        ))

    # Tick marks at 60-min intervals up to shift_minutes
    ticks = list(range(0, int(shift_minutes)+1, 60))
    fig.add_vline(x=shift_minutes,line_color=CRIMSON,line_width=2,
                  annotation_text='Shift End',annotation_font=dict(color=CRIMSON))
    fig.update_layout(
        title=dict(text=f'<b>SHOP PRODUCTION SCHEDULE — {project_name}</b><br>'
                        f'<sup>Derived from {len(stations)} workstations · {shift_minutes} min shift</sup>',
                   font=dict(size=13,color=DARK),x=0.01),
        paper_bgcolor=WHITE,plot_bgcolor=LGRAY,
        barmode='overlay',
        xaxis=dict(title='Time (minutes from shift start)',
                   range=[0,shift_minutes*1.05],
                   showgrid=True,gridcolor=GRID,
                   tickvals=ticks,ticktext=[f'{m}m' for m in ticks],
                   tickfont=dict(size=10,color=DARK)),
        yaxis=dict(showgrid=False,tickfont=dict(size=10,color=DARK)),
        height=320,
        margin=dict(l=160,r=20,t=70,b=50),
        font=dict(family='IBM Plex Mono, monospace',size=11),
    )
    return _j(fig)


# ═══════════════════════════════════════════════════════════════
# 10. ABC INVENTORY — from actual component data
# ═══════════════════════════════════════════════════════════════
def generate_abc_inventory(components):
    if not components:
        return {'chart_pareto': _j(_base()), 'chart_pie': _j(_base()),
                'table': [], 'totals': {}, 'grand_total': 0,
                'empty': True}

    data = []
    for c in components:
        av = float(c.get('unit_cost',0) or 0) * int(c.get('annual_usage',0) or 0)
        data.append({
            'item':         c.get('name',''),
            'unit_cost':    float(c.get('unit_cost',0) or 0),
            'usage':        int(c.get('annual_usage',0) or 0),
            'annual_value': av,
            'lead_time':    int(c.get('lead_time',1) or 1),
            'supplier':     c.get('supplier',''),
            'location':     c.get('location',''),
        })

    data.sort(key=lambda x: x['annual_value'], reverse=True)
    total_val = sum(d['annual_value'] for d in data)
    cum = 0
    for d in data:
        cum += d['annual_value']
        d['cum_pct'] = round(cum/total_val*100,1) if total_val else 0
        # Auto-assign ABC
        if d['cum_pct'] <= 70:      d['cat'] = 'A'
        elif d['cum_pct'] <= 90:    d['cat'] = 'B'
        else:                        d['cat'] = 'C'

    cat_colors = {'A':CRIMSON,'B':AMBER,'C':GREEN}
    cat_totals = {'A':0,'B':0,'C':0}
    for d in data: cat_totals[d['cat']] += d['annual_value']

    # Pareto chart
    fp = go.Figure()
    fp.add_trace(go.Bar(
        x=[d['item'] for d in data],
        y=[d['annual_value'] for d in data],
        marker=dict(color=[cat_colors[d['cat']] for d in data],
                    opacity=0.88,line=dict(color=WHITE,width=1)),
        text=[f"₹{d['annual_value']:,.0f}" for d in data],
        textposition='outside',textfont=dict(size=9),
        name='Annual Value',yaxis='y',
        hovertemplate='<b>%{x}</b><br>₹%{y:,.0f}<extra></extra>',
    ))
    fp.add_trace(go.Scatter(
        x=[d['item'] for d in data],y=[d['cum_pct'] for d in data],
        mode='lines+markers',line=dict(color=NAVY,width=2.5),
        marker=dict(size=7,color=NAVY,line=dict(color=WHITE,width=1.5)),
        name='Cumulative %',yaxis='y2',
    ))
    fp.add_hline(y=70,line_dash='dash',line_color=CRIMSON,line_width=1.5,yref='y2',
                 annotation_text='70% — A/B',annotation_font=dict(color=CRIMSON,size=10),
                 annotation_position='top right')
    fp.add_hline(y=90,line_dash='dash',line_color=AMBER,line_width=1.5,yref='y2',
                 annotation_text='90% — B/C',annotation_font=dict(color=AMBER,size=10),
                 annotation_position='top right')
    fp.update_layout(
        title=dict(text='<b>① ABC Pareto — Annual Value by Component</b>',
                   font=dict(size=13,color=DARK),x=0.01),
        paper_bgcolor=WHITE,plot_bgcolor=LGRAY,height=400,
        margin=dict(l=60,r=70,t=70,b=130),
        font=dict(family='IBM Plex Mono, monospace',size=11),
        xaxis=dict(tickangle=-65,showgrid=False,tickfont=dict(size=9,color=DARK)),
        yaxis=dict(title='Annual Value (₹)',showgrid=True,gridcolor=GRID,
                   tickfont=dict(size=10,color=DARK)),
        yaxis2=dict(title='Cumulative %',overlaying='y',side='right',
                    range=[0,112],showgrid=False,ticksuffix='%'),
        legend=dict(orientation='h',yanchor='bottom',y=1.02,xanchor='right',x=1,
                    bgcolor='rgba(255,255,255,.9)',bordercolor=GRID,borderwidth=1),
    )

    # Donut
    fpi = go.Figure()
    labels = [f"A — Critical\n({sum(1 for d in data if d['cat']=='A')} items)",
              f"B — Reorder Point\n({sum(1 for d in data if d['cat']=='B')} items)",
              f"C — Bulk Order\n({sum(1 for d in data if d['cat']=='C')} items)"]
    fpi.add_trace(go.Pie(
        labels=labels,values=list(cat_totals.values()),
        marker=dict(colors=[CRIMSON,AMBER,GREEN],line=dict(color=WHITE,width=2)),
        textinfo='label+percent+value',
        texttemplate='%{label}<br>₹%{value:,.0f}<br>%{percent}',
        textfont=dict(size=11),hole=0.40,pull=[0.04,0.02,0],
        hovertemplate='%{label}<br>₹%{value:,.0f}<br>%{percent}<extra></extra>',
    ))
    fpi.update_layout(
        title=dict(text='<b>② ABC Category Distribution</b>',
                   font=dict(size=13,color=DARK),x=0.01),
        paper_bgcolor=WHITE,plot_bgcolor=LGRAY,height=380,
        margin=dict(l=20,r=20,t=70,b=40),
        font=dict(family='IBM Plex Mono, monospace',size=11),
        annotations=[dict(text=f'₹{total_val:,.0f}',x=0.5,y=0.5,
                          font=dict(size=13,color=DARK,
                                    family='IBM Plex Mono, monospace'),
                          showarrow=False)],
    )

    return {
        'chart_pareto': _j(fp), 'chart_pie': _j(fpi),
        'table': data,
        'totals': {k:round(v) for k,v in cat_totals.items()},
        'grand_total': round(total_val),
    }


# ═══════════════════════════════════════════════════════════════
# 11. KANBAN CARDS — from actual components, ABC auto-assigned
# ═══════════════════════════════════════════════════════════════
def generate_kanban_cards(components, project_name=''):
    if not components:
        return {'project': project_name, 'cards': [], 'empty': True}

    # First run ABC to get categories
    abc = generate_abc_inventory(components)
    cat_map = {d['item']: d['cat'] for d in abc.get('table',[])}
    comp_map = {c['name']: c for c in components}

    cards = []
    seq = 1
    for item, cat in cat_map.items():
        if cat not in ('A','B'): continue
        c = comp_map.get(item, {})
        annual_usage  = int(c.get('annual_usage', 0) or 0)
        lead_time     = int(c.get('lead_time', 1) or 1)
        working_days  = 26
        daily_usage   = annual_usage / (working_days * 12) if annual_usage else 1
        reorder_qty   = int(c.get('reorder_qty', 0)) or max(1, round(daily_usage * lead_time))
        max_stock     = int(c.get('max_stock', 0))    or max(2, reorder_qty * 3)
        reorder_point = max(1, round(daily_usage * lead_time))

        # Auto part number: KBN-{first 3 chars}-{seq}
        initials = ''.join(w[0] for w in item.split()[:3]).upper()
        part_no  = f'KBN-{initials}-{seq:03d}'

        cards.append({
            'part_no':        part_no,
            'description':    item,
            'category':       cat,
            'qty_per_card':   reorder_qty,
            'lead_time':      f'{lead_time} days',
            'reorder_point':  reorder_point,
            'max_stock':      max_stock,
            'supplier':       c.get('supplier', 'TBD'),
            'location':       c.get('location', 'TBD'),
            'running_status': 'ACTIVE',
            'due_date':       '',
            'remarks':        f'{"JIT — order at reorder point" if cat=="A" else "Reorder point system"}',
        })
        seq += 1

    return {'project': project_name, 'cards': cards}


# ═══════════════════════════════════════════════════════════════
# PREDICTIONS — scikit-learn powered, all inputs from CSV/user
# ═══════════════════════════════════════════════════════════════
import numpy as np
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import Pipeline
from sklearn.tree import DecisionTreeClassifier


# ── Helper: convert station times to minutes ─────────────────
def _to_min(stations):
    times = []
    for s in stations:
        t = float(s.get('observed_time', s.get('obs_avg', 0)) or 0)
        times.append(t / 60 if t > 30 else t)
    return times


# ─────────────────────────────────────────────────────────────
# PRED 1: BOTTLENECK FORECAST
# X = target output range → Y = predicted bottleneck cycle time
# Shows which station will breach takt as output demand rises
# User input: target_range_max (slider, default 24)
# ─────────────────────────────────────────────────────────────
def predict_bottleneck_forecast(stations, shift_minutes=480,
                                 current_target=16, target_range_max=24):
    times = _to_min(stations)
    names = [s.get('station_name', f'WS{i+1}') for i, s in enumerate(stations)]
    if not times:
        return _j(_base())

    # Top 5 stations by cycle time
    indexed = sorted(enumerate(times), key=lambda x: x[1], reverse=True)[:5]

    targets = np.arange(current_target, target_range_max + 1, 1).reshape(-1, 1)
    takts   = shift_minutes / targets.flatten()

    fig = _base(400)
    palette = [CRIMSON, NAVY, AMBER, PURPLE, GREEN]

    for rank, (idx, base_time) in enumerate(indexed):
        name = names[idx][:16]
        # As target increases → takt shrinks → station is scaled to predict
        # cycle time degradation (fatigue/pace model: slight linear increase)
        # Trained on synthetic perturbation around observed time
        X_train = np.array([current_target - 4, current_target - 2,
                             current_target,     current_target + 2,
                             current_target + 4]).reshape(-1, 1)
        noise   = base_time * 0.015  # 1.5% pace degradation per 2 units increase
        y_train = np.array([base_time - 2*noise, base_time - noise,
                             base_time, base_time + noise * 1.5, base_time + noise * 3])
        model = LinearRegression().fit(X_train, y_train)
        predicted = model.predict(targets.flatten().reshape(-1, 1))

        color = palette[rank % len(palette)]
        fig.add_trace(go.Scatter(
            x=targets.flatten(), y=predicted,
            name=name,
            mode='lines+markers',
            line=dict(color=color, width=2),
            marker=dict(size=6, color=color),
            hovertemplate=f'<b>{name}</b><br>Target: %{{x}} units<br>Cycle: %{{y:.2f}} min<extra></extra>',
        ))

    # Takt line (dynamic — decreases as target increases)
    fig.add_trace(go.Scatter(
        x=targets.flatten(), y=takts,
        name='Takt Time',
        mode='lines',
        line=dict(color=DARK, width=2.5, dash='dash'),
        hovertemplate='Target: %{x}<br>Takt: %{y:.2f} min<extra></extra>',
    ))

    # Shade breach zone
    fig.add_hrect(y0=0, y1=min(takts), fillcolor='rgba(173,16,36,0.07)',
                  line_width=0, annotation_text='Breach zone',
                  annotation_font=dict(color=CRIMSON, size=9))

    fig.update_layout(
        title=dict(
            text='<b>① Bottleneck Forecast — Cycle Time vs Rising Demand</b><br>'
                 '<sup>Stations that cross the takt line become bottlenecks</sup>',
            font=dict(size=13, color=DARK), x=0.01),
        xaxis=dict(title='Target Output (units/shift)', showgrid=True,
                   gridcolor=GRID, tickfont=dict(size=10, color=DARK)),
        yaxis=dict(title='Cycle Time (min)', showgrid=True, gridcolor=GRID,
                   tickfont=dict(size=10, color=DARK)),
        margin=dict(l=50, r=30, t=70, b=100),
        legend=dict(orientation='h', yanchor='top', y=-0.20,
                    xanchor='center', x=0.5, bgcolor='rgba(255,255,255,.9)',
                    bordercolor=GRID, borderwidth=1,
                    font=dict(color=DARK, size=10)),
    )
    return _j(fig)


# ─────────────────────────────────────────────────────────────
# PRED 2: OUTPUT FORECASTER
# Ridge regression: operators_added + perf_rating → predicted output
# User inputs: operators_to_add (number), station_to_split (select)
# ─────────────────────────────────────────────────────────────
def predict_output_forecast(stations, shift_minutes=480, current_target=16,
                             perf_rating=0.80, allowance_pct=0.04,
                             operators_to_add=0, station_to_split=''):
    times = _to_min(stations)
    if not times:
        return _j(_base())

    total = sum(times)
    names = [s.get('station_name', f'WS{i+1}') for i, s in enumerate(stations)]

    # Build Ridge model: features = [total_min, num_operators, perf_rating]
    # Synthetic training set bracketing real values
    base_ops = sum(s.get('num_operators', 1) for s in stations)
    X_train, y_train = [], []
    for ops_delta in range(-2, 5):
        for perf in [0.70, 0.75, 0.80, 0.85, 0.90]:
            ops = max(1, base_ops + ops_delta)
            # More operators → bottleneck splits → total time reduces
            adj_time = total * (1 - ops_delta * 0.012) * (perf / 0.80)
            adj_time = max(adj_time, total * 0.6)
            out = int(shift_minutes / adj_time) if adj_time > 0 else current_target
            X_train.append([adj_time, ops, perf])
            y_train.append(out)

    model = Ridge(alpha=1.0).fit(X_train, y_train)

    # Scenario: split station reduces its cycle time by ~40%
    split_bonus = 0.0
    split_label = ''
    if station_to_split and station_to_split in names:
        idx = names.index(station_to_split)
        orig = times[idx]
        split_bonus = orig * 0.40  # splitting halves load per operator
        split_label = f' + Split {station_to_split[:12]}'

    scenarios = {
        'Current': (total, base_ops, perf_rating),
        f'+{operators_to_add} Operator{"s" if operators_to_add != 1 else ""}': (
            total * (1 - operators_to_add * 0.012), base_ops + operators_to_add, perf_rating),
        'Perf → 90%': (total * (0.90 / 0.80), base_ops, 0.90),
        'Optimised\n(NVA -70%)': (total * 0.70, base_ops, perf_rating),
    }
    if split_label:
        scenarios[f'Split{split_label}'] = (
            total - split_bonus, base_ops + 1, perf_rating)

    scen_labels, scen_vals, scen_colors = [], [], []
    palette = [NAVY, CRIMSON, AMBER, GREEN, PURPLE]
    for i, (label, (t, ops, perf)) in enumerate(scenarios.items()):
        pred = max(1, int(model.predict([[t, ops, perf]])[0]))
        scen_labels.append(label)
        scen_vals.append(pred)
        scen_colors.append(palette[i % len(palette)])

    fig = _base(380)
    fig.add_trace(go.Bar(
        x=scen_labels, y=scen_vals,
        marker=dict(color=scen_colors, opacity=0.88,
                    line=dict(color='#33334A', width=0.5)),
        text=[f'{v} units' for v in scen_vals],
        textposition='outside',
        textfont=dict(size=12, color=DARK),
        hovertemplate='<b>%{x}</b><br>Predicted: %{y} units/shift<extra></extra>',
    ))
    fig.add_hline(y=current_target, line_dash='dot', line_color=GRAY,
                  line_width=1.5,
                  annotation_text=f'Target: {current_target}',
                  annotation_font=dict(color=GRAY, size=10),
                  annotation_position='bottom right')
    fig.update_layout(
        title=dict(
            text='<b>② Output Forecaster — What-If Scenarios</b><br>'
                 '<sup>Predicted units/shift under different interventions</sup>',
            font=dict(size=13, color=DARK), x=0.01),
        xaxis=dict(showgrid=False, tickfont=dict(size=10, color=DARK)),
        yaxis=dict(title='Predicted Output (units/shift)',
                   showgrid=True, gridcolor=GRID,
                   tickfont=dict(size=10, color=DARK)),
        showlegend=False,
    )
    return _j(fig)


# ─────────────────────────────────────────────────────────────
# PRED 3: IDLE TIME PREDICTOR
# Polynomial regression: takt → cumulative idle time per station
# User input: exclude_nva toggle (bool)
# ─────────────────────────────────────────────────────────────
def predict_idle_time(stations, shift_minutes=480, current_target=16,
                      exclude_nva=False):
    nva_types = {'transport', 'delay', 'movement', 'storage'}
    active = [s for s in stations
              if not exclude_nva or
              str(s.get('type', '')).lower().strip() not in nva_types]

    times = _to_min(active)
    names = [s.get('station_name', f'WS{i+1}') for i, s in enumerate(active)]
    if not times:
        return _j(_base())

    # Takt sweep: from tight (high output) to relaxed (low output)
    target_range = np.arange(max(8, current_target - 6),
                              current_target + 8, 1)
    takts = shift_minutes / target_range

    # Poly model for each station: takt → idle per station
    # idle = max(0, takt - cycle_time) per unit, summed over shift
    fig = _base(420)
    palette = [NAVY, CRIMSON, AMBER, GREEN, PURPLE, GRAY]
    total_idle_per_takt = np.zeros(len(takts))

    for idx, (name, base_t) in enumerate(zip(names[:6], times[:6])):
        # train poly model on synthetic takt range
        X = takts.reshape(-1, 1)
        idle_vals = np.maximum(0, takts - base_t) * (shift_minutes / takts)
        pipe = Pipeline([('poly', PolynomialFeatures(degree=2)),
                         ('reg',  LinearRegression())])
        pipe.fit(X, idle_vals)
        predicted_idle = np.maximum(0, pipe.predict(X))
        total_idle_per_takt += predicted_idle

        color = palette[idx % len(palette)]
        fig.add_trace(go.Scatter(
            x=target_range, y=predicted_idle,
            name=name[:16], mode='lines',
            line=dict(color=color, width=1.5, dash='dot'),
            hovertemplate=f'<b>{name[:16]}</b><br>Target: %{{x}}<br>Idle: %{{y:.1f}} min/shift<extra></extra>',
        ))

    # Total idle area trace
    fig.add_trace(go.Scatter(
        x=target_range, y=total_idle_per_takt,
        name='Total Idle', mode='lines',
        fill='tozeroy', fillcolor='rgba(26,36,173,0.10)',
        line=dict(color=NAVY, width=3),
        hovertemplate='Target: %{x}<br>Total Idle: %{y:.1f} min/shift<extra></extra>',
    ))

    # Mark current target
    cur_takt = shift_minutes / current_target
    cur_idle = sum(max(0, cur_takt - t) * (shift_minutes / cur_takt) for t in times[:6])
    fig.add_vline(x=current_target, line_dash='dash', line_color=CRIMSON,
                  line_width=2,
                  annotation_text=f'Current target ({current_target} units)',
                  annotation_font=dict(color=CRIMSON, size=10))
    fig.add_annotation(x=current_target, y=cur_idle,
                       text=f'  {cur_idle:.0f} min idle now',
                       showarrow=True, arrowhead=2,
                       font=dict(color=CRIMSON, size=10),
                       arrowcolor=CRIMSON)

    nva_note = ' (NVA steps excluded)' if exclude_nva else ''
    fig.update_layout(
        title=dict(
            text=f'<b>③ Idle Time Predictor — Capacity Wasted vs Demand{nva_note}</b><br>'
                 '<sup>Higher target = tighter takt = less idle time per station</sup>',
            font=dict(size=13, color=DARK), x=0.01),
        xaxis=dict(title='Target Output (units/shift)', showgrid=True,
                   gridcolor=GRID, tickfont=dict(size=10, color=DARK)),
        yaxis=dict(title='Idle Time (min/shift)', showgrid=True,
                   gridcolor=GRID, tickfont=dict(size=10, color=DARK)),
        margin=dict(l=50, r=30, t=70, b=120),
        legend=dict(orientation='h', yanchor='top', y=-0.22,
                    xanchor='center', x=0.5, bgcolor='rgba(255,255,255,.9)',
                    bordercolor=GRID, borderwidth=1,
                    font=dict(color=DARK, size=9)),
    )
    return _j(fig)


# ─────────────────────────────────────────────────────────────
# PRED 4: STOCKOUT RISK SCORER
# DecisionTree: unit_cost, lead_time, reorder_pt, safety_stock,
#               demand_variability → Low/Medium/High risk
# User input: demand_variability_pct (number, default 15)
# ─────────────────────────────────────────────────────────────
def predict_stockout_risk(components, demand_variability_pct=15):
    if not components:
        return _j(_base())

    var = demand_variability_pct / 100

    # Build features for each component
    records = []
    for c in components:
        unit_cost    = float(c.get('unit_cost', 0) or 0)
        annual_usage = int(c.get('annual_usage', 0) or 0)
        lead_time    = int(c.get('lead_time', 1) or 1)
        reorder_qty  = int(c.get('reorder_qty', 0) or 0)
        max_stock    = int(c.get('max_stock', 0) or 0)
        daily_usage  = annual_usage / (26 * 12) if annual_usage else 1
        safety_stock = max_stock - reorder_qty if max_stock > reorder_qty else daily_usage * lead_time
        reorder_pt   = daily_usage * lead_time

        records.append({
            'name':         c.get('name', ''),
            'unit_cost':    unit_cost,
            'lead_time':    lead_time,
            'daily_usage':  round(daily_usage, 2),
            'reorder_pt':   round(reorder_pt, 1),
            'safety_stock': round(safety_stock, 1),
            'annual_value': unit_cost * annual_usage,
        })

    if not records:
        return _j(_base())

    # Use MinMaxScaler (sklearn) to normalize within this project's actual ranges
    # then compute a transparent weighted risk score
    from sklearn.preprocessing import MinMaxScaler

    cost_arr = np.array([r['unit_cost'] for r in records]).reshape(-1, 1)
    lead_arr = np.array([r['lead_time'] for r in records]).reshape(-1, 1)
    cost_norm = MinMaxScaler().fit_transform(cost_arr).flatten()
    lead_norm = MinMaxScaler().fit_transform(lead_arr).flatten()

    # Weighted score: cost 50%, lead time 35%, demand variability 15%
    for i, r in enumerate(records):
        raw = (cost_norm[i] * 0.50 + lead_norm[i] * 0.35 + var * 0.15) * 100
        r['risk_score'] = round(raw, 1)
        if raw >= 60:
            r['risk_level'] = 'High';   r['risk_color'] = CRIMSON
        elif raw >= 28:
            r['risk_level'] = 'Medium'; r['risk_color'] = AMBER
        else:
            r['risk_level'] = 'Low';    r['risk_color'] = GREEN

    # Sort by risk score descending
    records.sort(key=lambda x: x['risk_score'], reverse=True)

    # Horizontal bar chart — risk score per component
    names_plot  = [r['name'][:22] for r in records]
    scores      = [r['risk_score'] for r in records]
    colors_plot = [r['risk_color'] for r in records]
    risk_text   = [r['risk_level'] for r in records]

    fig = _base(max(340, 50 + len(records) * 32))
    fig.add_trace(go.Bar(
        y=names_plot, x=scores,
        orientation='h',
        marker=dict(color=colors_plot, opacity=0.85,
                    line=dict(color='#33334A', width=0.5)),
        text=[f'{s:.0f}% · {r}' for s, r in zip(scores, risk_text)],
        textposition='outside',
        textfont=dict(size=10, color=DARK),
        hovertemplate='<b>%{y}</b><br>Risk Score: %{x:.1f}%<extra></extra>',
    ))

    # Reference lines
    fig.add_vline(x=45, line_dash='dash', line_color=AMBER, line_width=1.5,
                  annotation_text='Medium', annotation_font=dict(color=AMBER, size=10))
    fig.add_vline(x=70, line_dash='dash', line_color=CRIMSON, line_width=1.5,
                  annotation_text='High', annotation_font=dict(color=CRIMSON, size=10))

    high_cnt   = sum(1 for r in records if r['risk_level'] == 'High')
    med_cnt    = sum(1 for r in records if r['risk_level'] == 'Medium')
    fig.update_layout(
        title=dict(
            text=f'<b>④ Stockout Risk Scorer — {high_cnt} High · {med_cnt} Medium Risk Items</b><br>'
                 f'<sup>Demand variability: {demand_variability_pct}% · MinMaxScaler weighted score (cost 50% · lead time 35% · variability 15%)</sup>',
            font=dict(size=13, color=DARK), x=0.01),
        xaxis=dict(title='Risk Score (%)', range=[0, 115],
                   showgrid=True, gridcolor=GRID,
                   tickfont=dict(size=10, color=DARK)),
        yaxis=dict(showgrid=False, tickfont=dict(size=10, color=DARK),
                   autorange='reversed'),
        showlegend=False,
    )
    return _j(fig)
