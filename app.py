import csv, json, math
from pathlib import Path
from flask import Flask, render_template, request, jsonify
import insight_engine
from analysis import (
    generate_asis_summary, generate_pfd_from_stations,
    generate_line_balance, generate_layout,
    generate_efficiency_diff, generate_sop,
    calculate_cost, generate_dpr, generate_shop_schedule,
    generate_abc_inventory, generate_kanban_cards,
    predict_bottleneck_forecast, predict_output_forecast,
    predict_idle_time, predict_stockout_risk,
)

app = Flask(__name__, static_folder='static')
PROJECTS_DIR = Path("projects")
PROJECTS_DIR.mkdir(exist_ok=True)

# ── CSV reader ────────────────────────────────────────────────
def _read_project(filename):
    path = PROJECTS_DIR / filename
    if not path.exists():
        return None, [], []
    meta, stations, components = {}, [], []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            sec = row.get('section','').strip().upper()

            if sec == 'META':
                meta = {
                    'project_name':       row.get('col1',''),
                    'product_name':       row.get('col2',''),
                    'factory_type':       row.get('col3','Discrete/Repetitive'),
                    'location':           row.get('col4',''),
                    'shift_duration_mins':int(row.get('col5') or 480),
                    'target_output':      int(row.get('col6') or 16),
                    'shifts_per_day':     int(row.get('col7') or 1),
                    'working_days_month': int(row.get('col8') or 26),
                    'perf_rating':        float(row.get('col9') or 80) / 100,
                    'allowance_pct':      float(row.get('col10') or 4) / 100,
                    'wage_per_hour':      float(row.get('col11') or 85),
                    'workers':            int(row.get('col12') or 1),
                    'overhead_per_hour':  float(row.get('col13') or 50),
                }

            elif sec == 'STATION':
                stations.append({
                    'station_number': row.get('col1',''),
                    'station_name':   row.get('col2',''),
                    'num_operators':  int(row.get('col3') or 1),
                    'obs_avg':        float(row.get('col4') or 0),
                    'observed_time':  float(row.get('col4') or 0),
                    'type':           row.get('col5','Operation'),
                    'component':      row.get('col6',''),
                    'distance':       float(row.get('col7') or 0),
                })

            elif sec == 'COMPONENT':
                name = row.get('col1','').strip()
                if name:
                    components.append({
                        'name':         name,
                        'unit_cost':    float(row.get('col2') or 0),
                        'annual_usage': int(row.get('col3') or 0),
                        'lead_time':    int(row.get('col4') or 1),
                        'supplier':     row.get('col5',''),
                        'location':     row.get('col6',''),
                        'reorder_qty':  int(row.get('col7') or 0),
                        'max_stock':    int(row.get('col8') or 0),
                    })

    # derive workers from stations if not in META
    if meta and meta.get('workers', 1) <= 1:
        total_ops = sum(s.get('num_operators', 1) for s in stations)
        if total_ops > 1:
            meta['workers'] = total_ops

    return meta, stations, components


def _obs_avg(s):
    t = s.get('observed_time', s.get('obs_avg', 0))
    try: return float(t)
    except: return 0


# ── Routes ────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/projects')
def api_projects():
    files = sorted([f.name for f in PROJECTS_DIR.glob('*.csv')])
    return jsonify({'projects': files})

@app.route('/api/project/<filename>')
def api_project_meta(filename):
    meta, stations, components = _read_project(filename)
    if not meta:
        return jsonify({'error': 'Project not found'}), 404
    obs = [_obs_avg(s) for s in stations]
    total = sum(obs)
    shift = meta['shift_duration_mins']
    target = meta['target_output']
    takt = round(shift / target, 2) if target else 30
    bn_idx = obs.index(max(obs)) if obs else 0
    units_ps = int((shift / (total / 60))) if total > 0 else 0
    return jsonify({
        'meta': meta,
        'station_count': len(stations),
        'component_count': len(components),
        'total_obs_min': round(total / 60, 2),
        'takt_time': takt,
        'bottleneck': stations[bn_idx].get('station_name','') if stations else '',
        'units_per_shift': units_ps,
    })

@app.route('/api/project_data/<filename>')
def api_project_data(filename):
    """Return full project data for pre-filling edit form."""
    meta, stations, components = _read_project(filename)
    if not meta:
        return jsonify({'error': 'Not found'}), 404
    return jsonify({'meta': meta, 'stations': stations, 'components': components})

@app.route('/api/save_project', methods=['POST'])
def api_save_project():
    data = request.get_json()
    name = data.get('project_name','').strip().replace(' ','_')
    if not name:
        return jsonify({'error': 'Project name required'}), 400
    filename = f"{name}.csv"
    path = PROJECTS_DIR / filename
    fieldnames = ['section','col1','col2','col3','col4','col5',
                  'col6','col7','col8','col9','col10','col11','col12','col13']
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        # META row
        w.writerow({'section':'META',
            'col1':  data.get('project_name',''),
            'col2':  data.get('product_name',''),
            'col3':  data.get('factory_type','Discrete/Repetitive'),
            'col4':  data.get('location',''),
            'col5':  data.get('shift_duration_mins', 480),
            'col6':  data.get('target_output', 16),
            'col7':  data.get('shifts_per_day', 1),
            'col8':  data.get('working_days_month', 26),
            'col9':  data.get('perf_rating', 80),
            'col10': data.get('allowance_pct', 4),
            'col11': data.get('wage_per_hour', 85),
            'col12': data.get('workers', 1),
            'col13': data.get('overhead_per_hour', 50),
        })
        # STATION rows
        for i, s in enumerate(data.get('stations', [])):
            if not str(s.get('station_name','')).strip():
                continue
            w.writerow({'section':'STATION',
                'col1': s.get('station_number', i+1),
                'col2': s.get('station_name',''),
                'col3': s.get('num_operators', 1),
                'col4': s.get('obs_avg', 0),
                'col5': s.get('type','Operation'),
                'col6': s.get('component',''),
                'col7': s.get('distance', 0),
            })
        # COMPONENT rows
        for c in data.get('components', []):
            if not str(c.get('name','')).strip():
                continue
            w.writerow({'section':'COMPONENT',
                'col1': c.get('name',''),
                'col2': c.get('unit_cost', 0),
                'col3': c.get('annual_usage', 0),
                'col4': c.get('lead_time', 1),
                'col5': c.get('supplier',''),
                'col6': c.get('location',''),
                'col7': c.get('reorder_qty', 0),
                'col8': c.get('max_stock', 0),
            })
    return jsonify({'ok': True, 'filename': filename})

@app.route('/api/delete_project/<filename>', methods=['DELETE'])
def api_delete_project(filename):
    path = PROJECTS_DIR / filename
    if path.exists():
        path.unlink()
        return jsonify({'ok': True})
    return jsonify({'error': 'Not found'}), 404

# ── Full analysis ─────────────────────────────────────────────
@app.route('/api/analysis/full/<filename>')
def api_full(filename):
    meta, stations, components = _read_project(filename)
    if not meta:
        return jsonify({'error': 'Project not found'}), 404

    shift      = meta['shift_duration_mins']
    target     = meta['target_output']
    perf       = meta['perf_rating']
    allow      = meta['allowance_pct']
    pname      = meta['project_name']
    product    = meta['product_name']
    wage       = meta['wage_per_hour']
    overhead   = meta['overhead_per_hour']
    shifts_day = meta['shifts_per_day']
    work_days  = meta['working_days_month']

    # workers = sum of operators
    workers = sum(s.get('num_operators',1) for s in stations)

    obs       = [_obs_avg(s) for s in stations]
    total_obs = sum(obs)  # seconds
    total_min = total_obs / 60

    # NVA derived from station types
    nva_steps = sum(1 for s in stations
                    if str(s.get('type','')).lower() in ['transport','delay','movement'])
    nva_pct   = round(nva_steps / len(stations) * 100, 1) if stations else 24

    cur_cycle = round(total_min, 2)
    opt_cycle = round(cur_cycle * (1 - (nva_pct/100) * 0.70), 2)
    units_ps  = int(shift / cur_cycle) if cur_cycle > 0 else target

    summary      = generate_asis_summary(stations, shift, target, perf, allow)
    pfd          = generate_pfd_from_stations(stations, pname, meta['location'])
    line_balance = generate_line_balance(stations, shift, target)
    layout       = generate_layout('product', stations, pname)
    efficiency   = generate_efficiency_diff(stations, shift, target, nva_pct)
    sops         = [generate_sop(s, int(s.get('station_number', i+1)), pname, product)
                    for i, s in enumerate(stations)]
    cost         = calculate_cost(wage, workers, shifts_day, units_ps,
                                  cur_cycle, opt_cycle,
                                  working_hours=shift/60,
                                  overhead_per_hour=overhead,
                                  working_days=work_days)
    dpr          = generate_dpr(product, target)
    schedule     = generate_shop_schedule(stations, shift, pname)
    abc          = generate_abc_inventory(components)
    kanban       = generate_kanban_cards(components, pname)

    return jsonify({
        'meta': meta, 'summary': summary, 'pfd': pfd,
        'line_balance': line_balance, 'layout': layout,
        'efficiency': efficiency, 'sops': sops, 'cost': cost,
        'dpr': dpr, 'schedule': schedule, 'abc': abc, 'kanban': kanban,
    })

@app.route('/api/analysis/layout/<filename>/<layout_type>')
def api_layout(filename, layout_type):
    meta, stations, _ = _read_project(filename)
    if not stations:
        return jsonify({'error': 'No station data'}), 404
    return jsonify(generate_layout(layout_type, stations,
                                   meta.get('project_name','')))

@app.route('/api/analysis/cost/<filename>', methods=['POST'])
def api_cost(filename):
    meta, stations, _ = _read_project(filename)
    if not stations:
        return jsonify({'error': 'No station data'}), 404
    body  = request.get_json() or {}
    shift = meta['shift_duration_mins']
    obs   = [_obs_avg(s) for s in stations]
    total = sum(obs)
    nva_steps = sum(1 for s in stations
                    if str(s.get('type','')).lower() in ['transport','delay'])
    nva_pct = nva_steps / len(stations) * 100 if stations else 24
    cur_cycle = round(total / 60, 2)
    opt_cycle = round(cur_cycle * (1 - (nva_pct/100) * 0.70), 2)
    units_ps  = int(shift / cur_cycle) if cur_cycle > 0 else 1
    workers   = sum(s.get('num_operators',1) for s in stations)
    return jsonify(calculate_cost(
        float(body.get('wage_per_hour', meta['wage_per_hour'])),
        int(body.get('workers', workers)),
        int(body.get('shifts', meta['shifts_per_day'])),
        units_ps, cur_cycle, opt_cycle,
        working_hours=shift/60,
        overhead_per_hour=float(body.get('overhead_per_hour', meta['overhead_per_hour'])),
        working_days=meta['working_days_month'],
    ))

# ── Predictions ───────────────────────────────────────────────
@app.route('/api/predictions/<filename>', methods=['POST'])
def api_predictions(filename):
    meta, stations, components = _read_project(filename)
    if not meta:
        return jsonify({'error': 'Project not found'}), 404

    body = request.get_json() or {}
    shift   = meta['shift_duration_mins']
    target  = meta['target_output']
    perf    = meta['perf_rating']
    allow   = meta['allowance_pct']

    # User-supplied prediction inputs (all have safe defaults)
    target_range_max      = int(body.get('target_range_max', target + 8))
    operators_to_add      = int(body.get('operators_to_add', 0))
    station_to_split      = str(body.get('station_to_split', ''))
    exclude_nva           = bool(body.get('exclude_nva', False))
    demand_variability_pct = float(body.get('demand_variability_pct', 15))

    bn    = predict_bottleneck_forecast(stations, shift, target, target_range_max)
    out   = predict_output_forecast(stations, shift, target, perf, allow,
                                    operators_to_add, station_to_split)
    idle  = predict_idle_time(stations, shift, target, exclude_nva)
    stock = predict_stockout_risk(components, demand_variability_pct)

    return jsonify({
        'bottleneck_forecast': bn,
        'output_forecast':     out,
        'idle_time':           idle,
        'stockout_risk':       stock,
    })


@app.route('/api/import_csv', methods=['POST'])
def api_import_csv():
    data     = request.get_json() or {}
    filename = data.get('filename', '').strip()
    content  = data.get('content', '')
    if not filename or not content:
        return jsonify({'error': 'filename and content required'}), 400
    if not filename.endswith('.csv'):
        filename += '.csv'
    # Sanitise filename
    filename = filename.replace('/', '_').replace('\\', '_')
    path = PROJECTS_DIR / filename
    path.write_text(content, encoding='utf-8')
    return jsonify({'ok': True, 'filename': filename})


# ── AI Chat ───────────────────────────────────────────────────
@app.route('/api/model_status')
def api_model_status():
    return jsonify({
        'ready':    insight_engine.is_ready(),
        'loading':  insight_engine.is_loading(),
        'exists':   insight_engine.model_exists(),
        'hf_url':   insight_engine.HF_URL,
        'hf_model': insight_engine.HF_MODEL,
    })

@app.route('/api/chat', methods=['POST'])
def api_chat():
    if not insight_engine.is_ready():
        return jsonify({'error': 'model_not_ready',
                        'message': '⏳ MechAI Intelligence is still loading. Please wait a moment.'}), 503
    data    = request.get_json() or {}
    question = str(data.get('question', '')).strip()
    context  = data.get('context', None)   # dict with takt_pct, bottleneck, etc.
    if not question:
        return jsonify({'error': 'empty_question'}), 400
    answer = insight_engine.infer(question, context)
    return jsonify({'answer': answer})


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
