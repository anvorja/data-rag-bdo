// Rastreo en anchura de páginas HTML (requiere extractor.js). Ejemplo: sección de empresas.
// Excluye /en/, licitaciones, rutas /wps/ antiguas y documentos. Profundidad máxima 3, tope 250 páginas.
window.__emp = { pages: {}, queue: [], seen: new Set(), done: false };
const seeds = ['/web/empresas', '/web/empresas/creditos', '/web/empresas/cuentas', '/web/empresas/leasing'].map(s => location.origin + s);
seeds.forEach(s => { window.__emp.seen.add(s); window.__emp.queue.push([s, 0]); });
(async () => { const E = window.__emp; const worker = async () => { while (E.queue.length && Object.keys(E.pages).length < 250) { const [u, d] = E.queue.shift();
  try { const r = await window.__get(u); E.pages[u] = r; if (!r.binary && d < 3) { for (const l of (r.allLinks || [])) { const n = window.__norm(l); if (!n) continue; const p = new URL(n).pathname;
    if (/\/web\/empresas/.test(p) && !/\/documents\//.test(p) && !E.seen.has(n)) { E.seen.add(n); E.queue.push([n, d + 1]); } } } } catch (e) { E.pages[u] = { url: u, error: String(e) }; } } };
  await Promise.all([1, 2, 3, 4, 5].map(worker)); E.done = true; })();
