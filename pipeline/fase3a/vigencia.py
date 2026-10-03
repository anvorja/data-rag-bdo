"""Filtro de vigencia con detección de intención temporal (fase 3a).

Dos políticas:
  doc_ok         DURA (fase 3a): oculta vencido/historico salvo intención temporal. Un cliente que pregunta por una campaña ya terminada no recibe nada.
  doc_ok_blanda  BLANDA (decisión 2026-10-02): oculta solo `historico` (versión reemplazada, existe una vigente) salvo intención temporal; `vencido`
                 (terminó y no tiene sucesora) se recupera siempre y se MARCA con `aviso()`, que construye la advertencia con los metadatos del documento.

Por defecto solo se recuperan documentos en estado vigente / por_verificar / periodo_reciente. Si la consulta tiene intención
temporal (menciona un año, «antes», «histórico», «cuándo cambió»…), se abre el filtro a todos los estados.
"""
import re

TEMPORAL = re.compile(r'(?i)((?<!\d)20[12]\d(?!\d)|\bantes\b|\banterior(es)?\b|hist[oó]ric|cu[aá]ndo cambi|cambi[oó] (la|el|entre)|evolu[ct]ion|evolucion|a[nñ]o pasado|hace (un|dos|tres) a[nñ]o|trimestre pasado|mes pasado|en su momento|desde cu[aá]ndo|hasta cu[aá]ndo|vigencia anterior|ya no|todav[ií]a|a[uú]n puedo)')
NO_VIGENTES = {'vencido', 'historico'}


def intencion_temporal(q):
    return bool(TEMPORAL.search(q))


def doc_ok(estado, q):
    return intencion_temporal(q) or estado not in NO_VIGENTES


def doc_ok_blanda(estado, q):
    """Política blanda: `vencido` (campaña terminada, sin sucesor) se recupera y se advierte; `historico` (hay versión nueva) solo si se pregunta por el pasado."""
    return intencion_temporal(q) or estado != 'historico'


MESES = 'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()


def fecha_larga(iso):
    a, m, d = iso.split('-'); return f'{int(d)} de {MESES[int(m) - 1]} de {a}'


def aviso(r):
    """Advertencia de vigencia para una respuesta, construida SOLO con metadatos del corpus (el modelo no la inventa). None si no hace falta."""
    e, hasta, desde = r.get('estado_vigencia'), r.get('vigente_hasta'), r.get('vigente_desde')
    if e == 'vencido':
        return f"Esta información ya no está vigente: «{r['titulo']}» " + (f'terminó el {fecha_larga(hasta)}.' if hasta else 'ya terminó.') + ' Consulta en los canales oficiales si hay una versión nueva.'
    if e == 'historico':
        return 'Este dato corresponde a una versión anterior' + (f', vigente hasta el {fecha_larga(hasta)}' if hasta else '') + '. Puede haber cambiado.'
    if e == 'vigente_hasta_reemplazo':
        return 'Estas tasas se publican cada mes' + (f' y las últimas cargadas cubren hasta el {fecha_larga(hasta)}' if hasta else '') + '; si ya empezó un mes nuevo, pueden haber cambiado. Está atento a la actualización.'
    if e == 'sujeta_a_existencias':
        return 'Esta campaña termina cuando se agote el cupo o cuando el banco lo comunique; confirma que siga disponible.'
    if e == 'vigente' and hasta: return f'Vigente hasta el {fecha_larga(hasta)}.'
    return None


def grupos_version(rows):
    """doc_id → conjunto de documentos que son versiones del mismo contenido (enlazados por `version_de`)."""
    padre = {r['id']: r['id'] for r in rows}
    def raiz(x):
        while padre[x] != x: padre[x] = padre[padre[x]]; x = padre[x]
        return x
    for r in rows:
        if r.get('version_de'): padre[raiz(r['id'])] = raiz(r['version_de'])
    g = {}
    for r in rows: g.setdefault(raiz(r['id']), set()).add(r['id'])
    return {i: g[raiz(i)] for i in padre}
