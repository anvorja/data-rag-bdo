import subprocess,re,os,glob,zipfile,html as H,unicodedata
def run(cmd, **k):
    return subprocess.run(cmd, capture_output=True, text=True, **k)

def clean(t):
    t = t.replace('\r', '')
    t = re.sub(r'[ \t]+\n', '\n', t)
    t = re.sub(r'\n{4,}', '\n\n\n', t)
    return t.strip()

def pdf_text(path):
    o = path + '.txt'
    subprocess.run(['pdftotext', '-layout', path, o], stderr=subprocess.DEVNULL, timeout=300)
    t = open(o, errors='ignore').read()
    pages = t.split('\f')
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    if len([p for p in pages if p.strip()]) == 0 or len(t.strip()) < 400:
        ocr = ocr_pdf(path)
        if len(ocr.strip()) > len(t.strip()):
            return clean(ocr), 'pdf (OCR)'
    if len(pages) > 1:
        t = ''.join(f'\n\n<!-- página {i+1} -->\n\n{p}' for i, p in enumerate(pages))
    return clean(t), 'pdf'

def ocr_pdf(path, maxp=40):
    d = path + '_ocr'
    os.makedirs(d, exist_ok=True)
    subprocess.run(['pdftoppm', '-r', '170', '-l', str(maxp), '-png', path, d + '/p'], stderr=subprocess.DEVNULL)
    out = []
    for i, f in enumerate(sorted(glob.glob(d + '/p*.png'))):
        r = run(['tesseract', f, '-', '-l', 'spa'])
        out.append(f'\n\n<!-- página {i+1} -->\n\n' + r.stdout)
    return ''.join(out)

def ocr_img(path):
    return run(['tesseract', path, '-', '-l', 'spa']).stdout

def docx_text(p):
    z = zipfile.ZipFile(p); x = z.read('word/document.xml').decode('utf8')
    x = re.sub(r'</w:p>', '\n', x); x = re.sub(r'<w:tab/>', '\t', x); x = re.sub(r'<[^>]+>', '', x)
    return clean(H.unescape(x))

def xlsx_text(p, maxrows=4000):
    from lxml import etree
    z = zipfile.ZipFile(p); names = z.namelist(); ss = []
    ns = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
    if 'xl/sharedStrings.xml' in names:
        for _, el in etree.iterparse(z.open('xl/sharedStrings.xml'), tag=ns + 'si'):
            ss.append(''.join(t.text or '' for t in el.iter(ns + 't'))); el.clear()
    wb = z.read('xl/workbook.xml').decode('utf8'); sheets = re.findall(r'<sheet [^>]*name="([^"]*)"', wb)
    out = []
    sh = sorted([n for n in names if re.match(r'xl/worksheets/sheet\d+\.xml', n)], key=lambda n: int(re.findall(r'\d+', n)[0]))
    for idx, n in enumerate(sh):
        out.append(f'## Hoja: {H.unescape(sheets[idx]) if idx < len(sheets) else idx}')
        rows = 0
        for _, row in etree.iterparse(z.open(n), tag=ns + 'row'):
            cells = []
            for c in row.iter(ns + 'c'):
                v = c.find(ns + 'v'); t = c.get('t')
                if t == 's' and v is not None and v.text and v.text.isdigit(): cells.append(ss[int(v.text)] if int(v.text) < len(ss) else '')
                elif t == 'inlineStr': cells.append(''.join(x.text or '' for x in c.iter(ns + 't')))
                elif v is not None and v.text: cells.append(v.text)
            if any(x.strip() for x in cells): out.append(' | '.join(cells)); rows += 1
            row.clear()
            if rows >= maxrows: out.append(f'… (hoja truncada a {maxrows} filas)'); break
    return clean('\n'.join(out))

def slugify(s, n=60):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    s = re.sub(r'[^a-zA-Z0-9]+', '-', s).strip('-').lower()
    return (s[:n].strip('-')) or 'doc'

