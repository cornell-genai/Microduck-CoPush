import json,sys
sys.path.insert(0,'scripts/rl')
from ci_report import wilson
def W(k,n):
    lo,hi=wilson(k,n);return f"{100*k/n:.1f}% ({100*lo:.1f} to {100*hi:.1f})"
for name in sys.argv[1:]:
    d=json.load(open(f'experiments/d2-heavybox/h0-mass-investigation/results/{name}.json'))
    print('==',name,'depth',d.get('depth'),'com',d.get('com_drop'))
    for r in d['rows']:
        n=r['n']
        print(f"{r['mult']}x mu={r['mu']} {r['mode']:7s} succ {r['success']}/{n} {W(r['success'],n)} | coop {r['coop']} {W(r['coop'],n)} | falls {r['falls']} tipped {r['tipped']} overshoot {r['overshoot']} | moved2 {r['moved_2cm']} moved10 {r['moved_10cm']} prog {r['progress_mean']:.2f}/{r['start_dist_mean']:.2f} | steps {r['steps_success_mean'] and round(r['steps_success_mean'])} max {r['steps_success_max']} | z {r['contact_z_mean_cm'] and round(r['contact_z_mean_cm'],1)}/{r['contact_z_p95max_cm'] and round(r['contact_z_p95max_cm'],1)}/{r['contact_z_max_cm'] and round(r['contact_z_max_cm'],1)} tilt95 {r['max_tilt_p95']:.0f} pushA {r['push_a_mean']:.2f} {r['reasons']}")
