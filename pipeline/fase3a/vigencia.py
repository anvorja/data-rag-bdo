"""Filtro de vigencia con detección de intención temporal (fase 3a).

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
