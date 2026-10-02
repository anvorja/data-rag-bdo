// Se ejecuta DENTRO de una pestaña del navegador (Playwright) ya abierta en bancodeoccidente.com.co.
// El sitio responde 403 a curl/Chrome headless (CloudFront); desde la pestaña, fetch() del mismo origen sí funciona.
window.__ex = (html, base) => {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const meta = n => (doc.querySelector(`meta[name="${n}"],meta[property="${n}"]`) || {}).content || '';
  const root = doc.querySelector('[role=main]') || doc.querySelector('.layout-content') || doc.querySelector('#content') || doc.body;
  const allLinks = [...doc.querySelectorAll('a[href]')].map(a => { try { return new URL(a.getAttribute('href'), base).href } catch (e) { return null } }).filter(Boolean);
  root.querySelectorAll('script,style,noscript,svg,iframe,template,link,[hidden],.sr-only').forEach(e => e.remove());
  const abs = h => { try { return new URL(h, base).href } catch (e) { return h } };
  const links = new Set();
  const norm = s => s.replace(/\s+/g, ' ').trim();
  const inline = n => { let o = ''; n.childNodes.forEach(c => { if (c.nodeType === 3) o += c.textContent; else if (c.nodeType === 1) { const t = c.tagName; if (t === 'BR') o += '\n'; else if (t === 'A') { const h = c.getAttribute('href'); const tx = norm(inline(c)); if (h && !h.startsWith('javascript') && !h.startsWith('#')) { links.add(abs(h)); o += tx ? `[${tx}](${abs(h)})` : ''; } else o += tx; } else if (t === 'IMG') { const a = norm(c.getAttribute('alt') || ''); if (a) o += ` (imagen: ${a}) `; } else if (t === 'STRONG' || t === 'B') { const x = norm(inline(c)); o += x ? `**${x}**` : ''; } else o += inline(c); } }); return o; };
  const blocks = new Set(['P', 'DIV', 'SECTION', 'ARTICLE', 'UL', 'OL', 'LI', 'TABLE', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'BLOCKQUOTE', 'DL', 'FORM', 'FIGURE', 'DETAILS', 'SUMMARY', 'TR', 'ASIDE', 'HEADER', 'FOOTER', 'NAV', 'MAIN', 'BUTTON', 'PRE']);
  const walk = (n, depth) => { let out = [];
    n.childNodes.forEach(c => {
      if (c.nodeType === 3) { const t = norm(c.textContent); if (t) out.push(t); return; }
      if (c.nodeType !== 1) return;
      const t = c.tagName;
      if (/^H[1-6]$/.test(t)) { const x = norm(inline(c)); if (x) out.push('\n' + '#'.repeat(+t[1]) + ' ' + x + '\n'); }
      else if (t === 'UL' || t === 'OL') { let i = 0; c.querySelectorAll(':scope > li').forEach(li => { i++; const x = walk(li, depth + 1).join(' ').replace(/\n+/g, ' ').trim(); if (x) out.push(' '.repeat(depth * 2) + (t === 'OL' ? i + '. ' : '- ') + x); }); }
      else if (t === 'TABLE') { const rows = [...c.querySelectorAll('tr')].map(tr => [...tr.children].map(td => norm(inline(td)).replace(/\|/g, '/')).join(' | ')).filter(r => r.replace(/[|\s]/g, '')); if (rows.length) out.push('\n' + rows.map(r => '| ' + r + ' |').join('\n') + '\n'); }
      else if (t === 'P' || t === 'SUMMARY' || t === 'BUTTON' || t === 'BLOCKQUOTE' || t === 'A') { const x = norm(inline(c)); if (x) out.push(x); }
      else if (blocks.has(t)) { const hasBlock = [...c.children].some(k => blocks.has(k.tagName)); if (hasBlock) out.push(...walk(c, depth)); else { const x = norm(inline(c)); if (x) out.push(x); } }
      else { const x = norm(inline(c)); if (x) out.push(x); }
    }); return out; };
  const txt = walk(root, 0).join('\n').replace(/\n{3,}/g, '\n\n').trim();
  return { title: norm(doc.title), description: meta('description') || meta('og:description'), text: txt, links: [...links], allLinks: [...new Set(allLinks)] };
};
window.__get = async (u) => { const r = await fetch(u); const ct = r.headers.get('content-type') || ''; if (ct.includes('html')) { const h = await r.text(); const x = window.__ex(h, r.url); return { url: u, final: r.url, status: r.status, ct, ...x }; } const b = await r.arrayBuffer(); return { url: u, final: r.url, status: r.status, ct, size: b.byteLength, binary: true }; };
window.__norm = u => { try { const x = new URL(u, location.href); if (!/bancodeoccidente\.com\.co$/.test(x.hostname)) return null; x.hash = ''; ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'].forEach(k => x.searchParams.delete(k)); return x.href.replace(/\/$/, ''); } catch (e) { return null } };
