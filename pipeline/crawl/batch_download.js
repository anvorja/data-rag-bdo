// Descarga documentos (PDF/Word/Excel) en lote desde la pestaña del navegador y los devuelve en base64.
// Uso: window.__runBatch([[id, '/documents/d/guest/slug'], ...]) y guardar el resultado en _raw/dl_NN.json;
// luego decodificar cada entrada a _raw/dl/NNNN.dat (ver pipeline/README.md).
window.__runBatch = async (arr) => {
  const b64 = buf => { const u = new Uint8Array(buf); let s = ''; for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode.apply(null, u.subarray(i, i + 0x8000)); return btoa(s); };
  const out = {}; const q = arr.slice();
  const w = async () => { while (q.length) { const [i, u] = q.shift(); try { const r = await fetch(u); const ct = r.headers.get('content-type') || ''; const b = await r.arrayBuffer();
    if (b.byteLength > 60e6) out[i] = { u, status: r.status, ct, size: b.byteLength, skipped: true };
    else out[i] = { u, status: r.status, ct, size: b.byteLength, b64: b64(b) }; } catch (e) { out[i] = { u, error: String(e) }; } } };
  await Promise.all([1, 2, 3, 4].map(w)); return out;
};
