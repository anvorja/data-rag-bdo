"""API del panel de pruebas con usuario real (fase 3b → piloto). Sirve al dashboard web (React + TypeScript), que no vive en este repositorio todavía.

Qué expone (contrato completo en /docs, OpenAPI en /openapi.json; de ahí se pueden generar los tipos de TypeScript):
  GET  /api/salud                      estado del servicio: corpus, recuperador, proveedor LLM (sin exponer claves)
  POST /api/sesiones                   abre un chat: devuelve el aviso de asistente virtual y el texto de consentimiento (una vez por chat)
  POST /api/sesiones/{id}/consentimiento   registra si el usuario acepta el tratamiento de datos (obligatorio antes de chatear)
  POST /api/chat                       un turno del asistente (docs/CONTRATO-3B.md): acción, respuesta, citas y avisos puestos por el código
  POST /api/buscar                     solo recuperación (híbrido + vigencia blanda + rerank-3), sin LLM: para consultar los documentos fuente
  GET  /api/documentos                 catálogo de documentos indexables, con filtros
  GET  /api/documentos/filtros         valores posibles de los filtros, con conteos
  GET  /api/documentos/{id}            un documento: metadatos, texto (Markdown) y cadena de versiones
  GET  /api/documentos/{id}/fragmentos/{n}   un fragmento citado (para resaltar la cita en el visor)
  POST /api/valoraciones               valoración del usuario de prueba sobre un turno (útil / correcta / comentario)

Reglas que se mantienen aquí:
  - Todo texto del usuario pasa por los límites anti-abuso y por el enmascaramiento ANTES de llegar a Voyage o al LLM.
  - El registro de la prueba (_raw/pruebas/, no versionado) guarda solo texto ENMASCARADO y metadatos; nunca el mensaje original.
  - Solo se sirven documentos indexables (el doc 806, con datos personales, no aparece).
  - Las claves salen del entorno (.env); /api/salud dice qué falta, nunca el valor.

Configuración (entorno): RAG_BASE, LLM_PROVEEDOR (deepseek | openai; por defecto deepseek), LLM_MODELO (por defecto el del proveedor),
PROMPT_JUEZ (p1 | p2; por defecto p2, el mejor en el ciclo completo del 2026-11-20), CORS_ORIGENES (coma; por defecto http://localhost:5173), REGISTRO_PRUEBAS (carpeta).
Arranque: set -a; . ./.env; set +a; python -m uvicorn api.app:app --port 8000      (pruebas sin proveedores: python -m api.test_api)
"""
import datetime, json, os, sys, threading, uuid
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) + '/'
for sub in ('pipeline/fase3b', 'pipeline/fase3a'):
    sys.path.insert(0, B + sub)

AVISO_INICIO = ('Hola, soy el asistente virtual del Banco de Occidente: no soy una persona. Respondo con la documentación pública del banco y te indico la fuente de cada dato. '
                'Para quejas, reclamaciones o reportes de fraude te remito al WhatsApp del banco.')
TEXTO_CONSENTIMIENTO = ('Para atender tu consulta, el texto que escribas se procesa con proveedores de tecnología que pueden estar fuera de Colombia. Antes de enviarlo quitamos '
                        'nombres, números de documento, cuentas y tarjetas. No escribas claves ni datos de tus productos. ¿Aceptas que tratemos tu consulta de esta forma?')


# ---------- modelos de la API (de aquí sale el contrato para el frontend) ----------
class Cita(BaseModel):
    n: int
    doc_id: str
    url: str
    titulo: str
    pagina: Optional[int] = None
    encabezado: Optional[str] = None
    fragmento: str = Field(description='id del fragmento, «<doc_id>#<n>»')
    estado_vigencia: str
    vigente_hasta: Optional[str] = None
    aviso: Optional[str] = None


class Traza(BaseModel):
    via: Optional[str] = Field(None, description='limites | escalamiento_reglas | cuenta_propia | compuerta | verificador | generador')
    top1_rerank: Optional[float] = None
    juez: Optional[bool] = None
    reintento: bool = False
    problemas: list[str] = []
    datos_enmascarados: dict[str, int] = Field({}, description='tipo → cantidad; nunca el valor')
    segundos: Optional[float] = None
    tokens_generador: int = 0
    alerta_sesion: bool = False


class Sesion(BaseModel):
    sesion_id: str
    aviso_inicio: str
    texto_consentimiento: str


class Consentimiento(BaseModel):
    acepta: bool


class PeticionChat(BaseModel):
    sesion_id: str
    mensaje: str


class RespuestaChat(BaseModel):
    turno_id: str
    accion: Literal['responder', 'abstenerse', 'escalar', 'aclarar']
    respuesta: str
    citas: list[Cita] = []
    avisos: list[str] = []
    traza: Traza


class PeticionBuscar(BaseModel):
    sesion_id: str
    consulta: str
    k: int = Field(10, ge=1, le=20)


class Resultado(BaseModel):
    puntaje: float
    fragmento: str
    doc_id: str
    titulo: str
    url: str
    pagina: Optional[int] = None
    encabezado: Optional[str] = None
    estado_vigencia: str
    vigente_hasta: Optional[str] = None
    aviso: Optional[str] = None
    texto: str


class RespuestaBuscar(BaseModel):
    consulta_enmascarada: str
    resultados: list[Resultado]


class DocumentoResumen(BaseModel):
    id: str
    titulo: str
    url: str
    tipo_contenido: str
    tipo_doc: Optional[str] = None
    segmento: Optional[str] = None
    area: Optional[str] = None
    estado_vigencia: str
    vigente_desde: Optional[str] = None
    vigente_hasta: Optional[str] = None
    paginas: Optional[int] = None
    fuente: Optional[str] = None


class Version(BaseModel):
    id: str
    estado_vigencia: str
    vigente_desde: Optional[str] = None
    vigente_hasta: Optional[str] = None


class Documento(DocumentoResumen):
    descripcion: Optional[str] = None
    aviso: Optional[str] = None
    fecha_extraccion: Optional[str] = None
    texto: str = Field(description='Markdown; los PDF llevan marcas «<!-- página N -->»')
    versiones: list[Version] = Field([], description='todas las versiones del mismo documento (incluida esta), de la más nueva a la más antigua')
    n_fragmentos: int


class ListaDocumentos(BaseModel):
    total: int
    documentos: list[DocumentoResumen]


class Fragmento(BaseModel):
    fragmento: str
    doc_id: str
    pagina: Optional[int] = None
    encabezado: Optional[str] = None
    texto: str


class Valoracion(BaseModel):
    sesion_id: str
    turno_id: str
    util: Optional[bool] = None
    correcta: Optional[Literal['si', 'parcial', 'no']] = None
    comentario: Optional[str] = Field(None, max_length=1000)


class Salud(BaseModel):
    estado: Literal['ok', 'degradado']
    documentos_indexables: int
    recuperador_cargado: bool
    reranker: str = 'voyage rerank-3'
    llm_proveedor: str
    llm_modelo: Optional[str] = None
    llm_listo: bool
    llm_error: Optional[str] = None
    faltan_variables: list[str]


# ---------- estado del servicio ----------
class Servicio:
    """Carga perezosa: el corpus se lee al arrancar (liviano); el recuperador (e5 + BM25 + Voyage) y el asistente (LLM) al primer uso.
    `fabrica_recuperador` y `fabrica_asistente` se pueden sustituir en pruebas para no llamar a proveedores pagos."""

    def __init__(self, base=B):
        self.B = base
        self.filas = [json.loads(l) for l in open(base + 'rag-bocc/corpus.jsonl')]
        self.docs = {r['id']: r for r in self.filas if r.get('indexar') and r.get('texto')}
        from vigencia import grupos_version, aviso
        self._aviso = aviso
        self.grupos = grupos_version(self.filas)
        self.proveedor = os.environ.get('LLM_PROVEEDOR', 'deepseek')
        self.modelo = os.environ.get('LLM_MODELO') or None
        self.prompt_juez = os.environ.get('PROMPT_JUEZ', 'p2')
        self.registro = os.environ.get('REGISTRO_PRUEBAS', base + '_raw/pruebas') + '/'
        self.sesiones = {}
        self.turnos = {}                    # turno_id → sesion_id (para validar valoraciones)
        self._rec = self._asis = None; self._asis_error = None
        self._lock = threading.Lock()       # un turno a la vez: el recuperador y los límites no son seguros entre hilos (basta para un usuario de prueba)
        from limites import Limites
        self.limites = Limites()
        self._fragmentos = None

    # fábricas sustituibles
    def fabrica_recuperador(self):
        from recuperar import Recuperador
        return Recuperador(self.B)

    def fabrica_asistente(self, rec):
        from asistente import Asistente
        kw = dict(modelo=self.modelo) if self.modelo else {}
        return Asistente(self.B, proveedor=self.proveedor, prompt_juez=self.prompt_juez, recuperador=rec, **kw)

    def enmascarar(self, texto):
        from enmascarar import enmascarar
        return enmascarar(texto)

    @property
    def rec(self):
        if self._rec is None: self._rec = self.fabrica_recuperador()
        return self._rec

    @property
    def asistente(self):
        if self._asis is None:
            try: self._asis = self.fabrica_asistente(self.rec); self._asis_error = None
            except Exception as e: self._asis_error = str(e); raise
        return self._asis

    def fragmentos(self):
        """cid → fragmento, sin cargar modelos (mismo chunking que el recuperador)."""
        if self._fragmentos is None:
            if self._rec is not None: self._fragmentos = {c['cid']: c for c in self._rec.ch}
            else:
                from chunking import chunk_corpus
                self._fragmentos = {c['cid']: c for c in chunk_corpus(self.filas, 'estructural')}
        return self._fragmentos

    def anotar(self, archivo, fila):
        os.makedirs(self.registro, exist_ok=True)
        with open(self.registro + archivo, 'a') as f: f.write(json.dumps(dict(fecha=datetime.datetime.now().isoformat(timespec='seconds'), **fila), ensure_ascii=False) + '\n')

    def sesion_valida(self, sid, exigir_consentimiento=True):
        s = self.sesiones.get(sid)
        if s is None: raise HTTPException(404, 'Sesión inexistente: abre una con POST /api/sesiones')
        if exigir_consentimiento and not s['consentimiento']: raise HTTPException(403, 'Falta el consentimiento del usuario para tratar su consulta')
        return s


def _error_proveedor(e):
    """Traduce errores de los proveedores a mensajes claros para el panel (sin detalles de la cuenta)."""
    cod = getattr(e, 'status_code', None)
    if cod == 402: return 503, 'El proveedor LLM no tiene saldo (HTTP 402). Hay que recargar la cuenta.'
    if cod in (401, 403): return 503, 'El proveedor rechazó la clave (HTTP %s). Revisa el .env.' % cod
    if cod == 429: return 503, 'El proveedor limitó las peticiones (HTTP 429). Intenta de nuevo en un momento.'
    if isinstance(e, RuntimeError) and 'Falta' in str(e): return 503, str(e)
    if isinstance(e, ImportError): return 500, f'Falta una dependencia en el entorno del servidor: {e.name} (¿se arrancó con el python del .venv? usar: python -m uvicorn …)'
    return 502, f'Fallo del proveedor: {type(e).__name__}'


def crear_app(servicio=None):
    svc = servicio or Servicio()
    app = FastAPI(title='API del asistente virtual Banco de Occidente (panel de pruebas)', version='0.1.0')
    app.state.svc = svc
    origenes = [o.strip() for o in os.environ.get('CORS_ORIGENES', 'http://localhost:5173').split(',') if o.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origenes, allow_methods=['GET', 'POST'], allow_headers=['Content-Type'])

    def resumen(d):
        return DocumentoResumen(id=d['id'], titulo=d.get('titulo_publico') or d['titulo'], url=d['url'], tipo_contenido=d['tipo_contenido'], tipo_doc=d.get('tipo_doc'),
                                segmento=d.get('segmento'), area=d.get('area'), estado_vigencia=d['estado_vigencia'], vigente_desde=d.get('vigente_desde'),
                                vigente_hasta=d.get('vigente_hasta'), paginas=d.get('paginas'), fuente=d.get('fuente'))

    @app.get('/api/salud', response_model=Salud)
    def salud():
        from suficiencia import PROVEEDORES
        cfg = PROVEEDORES.get(svc.proveedor, {})
        faltan = [v for v in ['VOYAGE_API_KEY', cfg.get('clave')] if v and not os.environ.get(v)]
        if svc.proveedor == 'openai' and not (svc.modelo or os.environ.get('OPENAI_MODEL_JUEZ')): faltan.append('OPENAI_MODEL_JUEZ o LLM_MODELO')
        listo = svc._asis is not None
        return Salud(estado='ok' if not faltan and not svc._asis_error else 'degradado', documentos_indexables=len(svc.docs), recuperador_cargado=svc._rec is not None,
                     llm_proveedor=svc.proveedor, llm_modelo=svc._asis.modelo if listo else (svc.modelo or (cfg.get('modelo') or (None, None))[1]),
                     llm_listo=listo, llm_error=svc._asis_error, faltan_variables=faltan)

    @app.post('/api/sesiones', response_model=Sesion)
    def abrir_sesion():
        sid = uuid.uuid4().hex
        svc.sesiones[sid] = dict(creada=datetime.datetime.now().isoformat(timespec='seconds'), consentimiento=False)
        return Sesion(sesion_id=sid, aviso_inicio=AVISO_INICIO, texto_consentimiento=TEXTO_CONSENTIMIENTO)

    @app.post('/api/sesiones/{sid}/consentimiento')
    def consentir(sid: str, c: Consentimiento):
        s = svc.sesion_valida(sid, exigir_consentimiento=False); s['consentimiento'] = c.acepta
        svc.anotar('sesiones.jsonl', dict(sesion=sid, consentimiento=c.acepta))
        return dict(sesion_id=sid, consentimiento=c.acepta)

    @app.post('/api/chat', response_model=RespuestaChat)
    def chat(p: PeticionChat):
        svc.sesion_valida(p.sesion_id)
        with svc._lock:
            try:
                r = svc.asistente.responder(p.mensaje, sesion=p.sesion_id, limites=svc.limites)
            except HTTPException: raise
            except Exception as e:
                cod, msg = _error_proveedor(e); svc.anotar('errores.jsonl', dict(sesion=p.sesion_id, ruta='chat', codigo=cod, error=msg)); raise HTTPException(cod, msg)
        t = r['traza']; tid = uuid.uuid4().hex[:12]; svc.turnos[tid] = p.sesion_id
        traza = Traza(via=t.get('via'), top1_rerank=t.get('top1_rerank'), juez=t.get('juez'), reintento=t.get('reintento', False), problemas=t.get('problemas', []),
                      datos_enmascarados=t.get('enmascarado') or {}, segundos=t.get('segundos'), tokens_generador=t.get('tokens_generador', 0), alerta_sesion=bool(t.get('alerta_sesion')))
        q_masc = svc.enmascarar(p.mensaje)[0] if t.get('via') != 'limites' else None      # en el registro nunca va el texto original
        svc.anotar('turnos.jsonl', dict(sesion=p.sesion_id, turno=tid, pregunta_enmascarada=q_masc, accion=r['accion'], respuesta=r['respuesta'],
                                        citas=[c['fragmento'] for c in r['citas']], avisos=r['avisos'], traza=traza.model_dump()))
        return RespuestaChat(turno_id=tid, accion=r['accion'], respuesta=r['respuesta'], citas=r['citas'], avisos=r['avisos'], traza=traza)

    @app.post('/api/buscar', response_model=RespuestaBuscar)
    def buscar(p: PeticionBuscar):
        svc.sesion_valida(p.sesion_id)
        with svc._lock:
            ok, motivo = svc.limites.revisar(p.sesion_id, p.consulta)
            if not ok: raise HTTPException(429 if motivo in ('demasiados_por_minuto', 'sesion_agotada') else 422, f'Consulta rechazada: {motivo}')
            q, _ = svc.enmascarar(p.consulta)
            try: res = svc.rec.buscar(q)
            except Exception as e: cod, msg = _error_proveedor(e); raise HTTPException(cod, msg.replace('LLM', 'de reranking'))
        out = []
        for i, s in res[:p.k]:
            c = svc.rec.ch[i]; d = svc.rec.corpus[c['doc']]
            out.append(Resultado(puntaje=round(s, 4), fragmento=c['cid'], doc_id=d['id'], titulo=d.get('titulo_publico') or d['titulo'], url=d['url'], pagina=c.get('pagina'),
                                 encabezado=c.get('encabezado') or None, estado_vigencia=d['estado_vigencia'], vigente_hasta=d.get('vigente_hasta'), aviso=svc._aviso(d), texto=c['texto']))
        svc.anotar('busquedas.jsonl', dict(sesion=p.sesion_id, consulta_enmascarada=q, resultados=[r.fragmento for r in out]))
        return RespuestaBuscar(consulta_enmascarada=q, resultados=out)

    @app.get('/api/documentos', response_model=ListaDocumentos)
    def documentos(q: Optional[str] = None, segmento: Optional[str] = None, area: Optional[str] = None, estado: Optional[str] = None, tipo: Optional[str] = None,
                   incluir_historicos: bool = False, desde: int = Query(0, ge=0), limite: int = Query(50, ge=1, le=200)):
        """Búsqueda por título/descripción (texto exacto, sin modelos ni costo). Por defecto oculta las versiones históricas."""
        ql = (q or '').lower().strip()
        sel = [d for d in svc.docs.values()
               if (incluir_historicos or d['estado_vigencia'] != 'historico' or estado == 'historico')
               and (not segmento or d.get('segmento') == segmento) and (not area or d.get('area') == area)
               and (not estado or d['estado_vigencia'] == estado) and (not tipo or d.get('tipo_doc') == tipo)
               and (not ql or ql in ((d.get('titulo_publico') or '') + ' ' + d['titulo'] + ' ' + (d.get('descripcion') or '')).lower())]
        sel.sort(key=lambda d: int(d['id']))
        return ListaDocumentos(total=len(sel), documentos=[resumen(d) for d in sel[desde:desde + limite]])

    @app.get('/api/documentos/filtros')
    def filtros():
        import collections
        cuenta = lambda k: dict(collections.Counter(d.get(k) for d in svc.docs.values() if d.get(k)).most_common())
        return dict(segmento=cuenta('segmento'), area=cuenta('area'), estado=cuenta('estado_vigencia'), tipo=cuenta('tipo_doc'))

    @app.get('/api/documentos/{doc_id}', response_model=Documento)
    def documento(doc_id: str):
        d = svc.docs.get(doc_id)
        if d is None: raise HTTPException(404, 'Documento inexistente o no indexable')
        vers = sorted((svc.docs[i] for i in svc.grupos.get(doc_id, {doc_id}) if i in svc.docs), key=lambda x: -int(x['id']))
        nfr = sum(1 for cid in svc.fragmentos() if cid.split('#')[0] == doc_id)
        return Documento(**resumen(d).model_dump(), descripcion=d.get('descripcion'), aviso=svc._aviso(d), fecha_extraccion=d.get('fecha_extraccion'), texto=d['texto'],
                         versiones=[Version(id=v['id'], estado_vigencia=v['estado_vigencia'], vigente_desde=v.get('vigente_desde'), vigente_hasta=v.get('vigente_hasta')) for v in vers],
                         n_fragmentos=nfr)

    @app.get('/api/documentos/{doc_id}/fragmentos/{n}', response_model=Fragmento)
    def fragmento(doc_id: str, n: int):
        c = svc.fragmentos().get(f'{doc_id}#{n}')
        if c is None or doc_id not in svc.docs: raise HTTPException(404, 'Fragmento inexistente')
        return Fragmento(fragmento=c['cid'], doc_id=doc_id, pagina=c.get('pagina'), encabezado=c.get('encabezado') or None, texto=c['texto'])

    @app.post('/api/valoraciones')
    def valorar(v: Valoracion):
        svc.sesion_valida(v.sesion_id)
        if svc.turnos.get(v.turno_id) != v.sesion_id: raise HTTPException(404, 'Turno inexistente en esta sesión')
        com = svc.enmascarar(v.comentario)[0] if v.comentario else None
        svc.anotar('valoraciones.jsonl', dict(sesion=v.sesion_id, turno=v.turno_id, util=v.util, correcta=v.correcta, comentario_enmascarado=com))
        return dict(ok=True)

    return app


app = crear_app() if os.environ.get('API_SIN_ARRANQUE') != '1' else None
