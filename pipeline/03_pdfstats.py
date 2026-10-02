import json, re, os, subprocess, collections
import multiprocessing as mp

B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) + '/'
R = B + '_raw/'
OUT = B + 'rag-bocc/'
rows = [json.loads(l) for l in open(OUT + 'corpus.jsonl')]

# ---- mapa url -> archivo original ----
urls_lim = [l.strip() for l in open(B + 'enlaces-rag-bocc-limpio.txt') if l.strip()]
u2orig = {}
old = json.load(open(R + 'paginas_bocc.json'))
for r in old:
    if r.get('binary'):
        u2orig[r['url']] = R + f"bin/{r['i']:03d}.dat"
pp_urls = [u for u in urls_lim if 'portalpublico.bancodeoccidente.com.co' in u and '/documents/' in u]
# orden de aparicion == orden en portalpublico.json (22 = promociones html)
pp_all = [u for u in urls_lim if u.startswith('https://portalpublico.bancodeoccidente.com.co')]
for k, u in enumerate(pp_all):
    f = R + f'bin/pp{k:02d}.dat'
    if os.path.exists(f): u2orig[u] = f
for k, u in enumerate(urls_lim):
    f = R + f'ext/{k:03d}.dat'
    if os.path.exists(f) and u not in u2orig: u2orig[u] = f
sel = json.load(open(R + 'sel_docs.json'))
for o in sel:
    f = R + f"dl/{o['i']:04d}.dat"
    if os.path.exists(f):
        u = 'https://www.bancodeoccidente.com.co' + o['u'] if o['u'].startswith('/') else o['u']
        u2orig[u] = f

def pdf_stats(f):
    try:
        if open(f, 'rb').read(4) != b'%PDF': return None
        info = subprocess.run(['pdfinfo', f], capture_output=True, text=True, timeout=60).stdout
        pg = int((re.search(r'Pages:\s+(\d+)', info) or [0, 0])[1])
        im = subprocess.run(['pdfimages', '-list', f], capture_output=True, text=True, timeout=120).stdout.strip().split('\n')[2:]
        n = len(im); big = 0
        for l in im:
            p = l.split()
            try:
                if int(p[3]) > 400 and int(p[4]) > 300: big += 1
            except Exception: pass
        return dict(pages=pg, imgs=n, imgs_big=big, size=os.path.getsize(f))
    except Exception:
        return None

def work(r):
    f = u2orig.get(r['url'])
    return r['id'], (pdf_stats(f) if f else None)

if __name__ == '__main__':
    with mp.Pool(8) as p:
        res = dict(p.map(work, rows, chunksize=8))
    json.dump(res, open(R + 'f1_pdfstats.json', 'w'))
    print(len(res), sum(1 for v in res.values() if v))
