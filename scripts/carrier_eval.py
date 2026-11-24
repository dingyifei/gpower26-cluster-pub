import sys, glob, os, xml.etree.ElementTree as ET
root = sys.argv[1]; A, B = sys.argv[2], sys.argv[3]
def res(crit_list, default, c):
    simdep = False
    for cr in crit_list:
        ch = cr.get('channel')
        if ch is None or c in ch.split(';'):
            extra = {k: v for k, v in cr.attrib.items() if k not in ('action', 'channel')}
            if extra: simdep = True; continue   # SIM-conditioned: only with matching SIM
            return cr.get('action'), simdep
    return default, simdep
rows = []
for f in sorted(glob.glob(root + '/**/enable-disable-packages/*.xml', recursive=True)):
    for p in ET.parse(f).getroot().iter('package-disable-enable-criteria'):
        cl = list(p.iter('criteria')); d = p.get('default_action')
        ra, sa = res(cl, d, A); rb, sb = res(cl, d, B)
        rows.append((p.get('package'), ra + ('*' if sa else ''), rb + ('*' if sb else '')))
for f in sorted(glob.glob(root + '/**/filter-system-apps/*.xml', recursive=True)):
    for m in ET.parse(f).getroot().iter('module'):
        v = m.get('value', '').split(';'); prop = m.get('prop')
        if prop != 'ro.carrier': rows.append(('[module] ' + m.get('name'), f'{prop}={m.get("value")}', '(not carrier)')); continue
        on = lambda c: m.get('action') if c in v else ('disable' if m.get('action') == 'enable' else 'enable')
        rows.append(('[module] ' + m.get('name'), on(A), on(B)))
diff = [r for r in rows if r[1] != r[2]]
print(f'{len(rows)} rules, {len(diff)} differ ({A} -> {B}); * = more conditions on SIM mccmnc/gid')
for r in sorted(diff, key=lambda r: (r[1], r[0])): print(f'  {r[0]:60s} {r[1]:10s} -> {r[2]}')
