"""Controles operativos anti-abuso y de costo (fase 3b, capa 4 del contrato). Van ANTES de enmascarar y de llamar a cualquier proveedor.
  - longitud máxima del mensaje (por defecto 600 caracteres: ~4× el p99 de las preguntas del golden, que son sintéticas y cortas; CALIBRAR con tráfico real);
  - mensajes por minuto y por sesión (evita ráfagas y sesiones interminables que gastan tokens);
  - alerta cuando una sesión acumula N abstenciones seguidas (señal de abuso o de tema ajeno insistente).
Estado en memoria del proceso: sirve para pruebas y un solo servidor; en producción debe vivir en un almacén compartido (p. ej. Redis o la misma PostgreSQL).
Los valores NO guardan el texto del cliente, solo contadores. Uso: python pipeline/fase3b/limites.py --autoprueba"""
import collections, sys, time


class Limites:
    def __init__(self, max_chars=600, max_por_minuto=10, max_por_sesion=60, abstenciones_alerta=4, reloj=time.time):
        self.max_chars, self.max_min, self.max_ses, self.alerta = max_chars, max_por_minuto, max_por_sesion, abstenciones_alerta
        self.reloj = reloj; self.marcas = collections.defaultdict(collections.deque); self.total = collections.Counter(); self.seguidas = collections.Counter()

    def revisar(self, sesion, texto):
        """→ (permitido, motivo). Motivos: vacio | demasiado_largo | demasiados_por_minuto | sesion_agotada."""
        if not texto or not texto.strip(): return False, 'vacio'
        if len(texto) > self.max_chars: return False, 'demasiado_largo'
        ahora = self.reloj(); q = self.marcas[sesion]
        while q and ahora - q[0] > 60: q.popleft()
        if len(q) >= self.max_min: return False, 'demasiados_por_minuto'
        if self.total[sesion] >= self.max_ses: return False, 'sesion_agotada'
        q.append(ahora); self.total[sesion] += 1
        return True, None

    def registrar(self, sesion, accion):
        """Llamar con la acción final de cada turno. → True si la sesión debe marcarse para revisión (abstenciones seguidas)."""
        self.seguidas[sesion] = self.seguidas[sesion] + 1 if accion == 'abstenerse' else 0
        return self.seguidas[sesion] >= self.alerta


MENSAJES = {'vacio': 'Escribe tu pregunta sobre los productos o servicios del Banco de Occidente.',
            'demasiado_largo': 'Tu mensaje es muy largo. ¿Puedes resumirlo en una o dos frases?',
            'demasiados_por_minuto': 'Estás enviando mensajes muy rápido. Espera un momento e inténtalo de nuevo.',
            'sesion_agotada': 'Llegaste al límite de mensajes de esta conversación. Inicia una nueva o escríbenos por WhatsApp.'}


def autoprueba():
    t = [0.0]; L = Limites(max_chars=50, max_por_minuto=3, max_por_sesion=5, abstenciones_alerta=3, reloj=lambda: t[0])
    assert L.revisar('s', '') == (False, 'vacio') and L.revisar('s', 'x' * 51) == (False, 'demasiado_largo')
    assert all(L.revisar('s', 'hola')[0] for _ in range(3)) and L.revisar('s', 'hola') == (False, 'demasiados_por_minuto')
    t[0] = 61; assert L.revisar('s', 'hola')[0] and L.revisar('s', 'hola')[0]
    t[0] = 200; assert L.revisar('s', 'hola') == (False, 'sesion_agotada')
    assert L.revisar('otra', 'hola')[0]                                   # otra sesión no se ve afectada
    assert not L.registrar('a', 'abstenerse') and not L.registrar('a', 'abstenerse') and L.registrar('a', 'abstenerse')
    assert not L.registrar('a', 'responder') and not L.registrar('a', 'abstenerse')     # una respuesta reinicia la cuenta
    print('autoprueba aprobada')


if __name__ == '__main__':
    if '--autoprueba' in sys.argv: autoprueba()
    else: print(__doc__)
