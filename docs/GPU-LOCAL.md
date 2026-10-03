# GPU local (NVIDIA GTX 1650 Ti) para el reranker: configuración paso a paso

Estado: **en curso** (Fases A y B hechas; faltan C y D) (se actualiza a medida que cada paso se ejecuta y se verifica). Equipo: Linux Mint 22.3 (base Ubuntu 24.04), kernel 7.0.0-34-generic, Secure Boot **activado**,
GPU NVIDIA GeForce GTX 1650 Ti Mobile (TU117M, 4 GB) + Intel UHD integrada. Docker 29.8.2 ya instalado y el usuario pertenece al grupo `docker`.

Objetivo: poder ejecutar el reranker abierto `BAAI/bge-reranker-v2-m3` (≈1,1 GB en fp16) en la GPU local, primero directo en Python y luego como servicio en un contenedor Docker.
Línea base medida: en CPU tarda unos 16 s por consulta (20 candidatos).

Leyenda: ☐ pendiente · ☑ hecho y verificado.

## Antes de empezar: estado inicial (verificado el 2026-10-02)
- El sistema usa el driver libre `nouveau`; no hay paquetes `nvidia-driver-*` ni `nvidia-container-toolkit` instalados. `nvidia-smi` no existe.
- `ubuntu-drivers devices` ofrece: `nvidia-driver-580-open`, `nvidia-driver-580-server(-open)`, `nvidia-driver-595`, `nvidia-driver-595-server`.
- PyTorch del proyecto (`.venv`): 2.7.1+cu126; con el driver actual `torch.cuda.is_available()` da `False`.

## Fase A — Driver de NVIDIA (requiere `sudo` y reinicio)
**Ejecutar en una terminal normal del sistema (Ctrl+Alt+T), no desde el prompt de Claude Code:** compilar un módulo de kernel con DKMS y gestionar el arranque seguro no deben hacerse dentro de una sesión restringida.
**Driver:** `nvidia-driver-595-open`, el que `ubuntu-drivers` marca como *recommended* en este equipo. (Un primer intento con `nvidia-driver-580-open` falló, ver «Incidente 2026-10-02» abajo; el kernel es el 7.0, muy reciente, y conviene la rama que el sistema recomienda.)
1. ☑ `ubuntu-drivers devices | grep -E "driver|recommended"` → recomendado: `nvidia-driver-595-open`.
2. ☑ Limpieza del driver 580 (no hizo falta: el 595 se instaló encima) y descarga del 595 (`sudo apt install -y linux-headers-generic nvidia-driver-595-open`): librerías instaladas; `nvidia-dkms-595-open` y `nvidia-driver-595-open` quedaron **sin configurar** por la carpeta que falta.
3. ☑ **Crear la carpeta y terminar la configuración:** `sudo mkdir -p /var/lib/dkms && sudo dpkg --configure -a` (2026-10-02: compiló e instaló el módulo para los kernels 7.0.0-34 y 7.0.0-38). (`linux-headers-generic` deja las cabeceras de **todos** los kernels instalados, incluido el 7.0.0-38 que ya está en `/boot`.)
4. ☑ **Secure Boot:** no pidió contraseña nueva. Los módulos compilados salen firmados por la clave «VirtualBox», que **ya está inscrita** en el MOK de este equipo (de la instalación de VirtualBox; `mokutil --list-enrolled`, `modinfo -F signer …/nvidia.ko.zst` → `VirtualBox`). Por eso se espera que carguen sin pasar por la pantalla azul; si el arranque la muestra, seguir el paso 6.
5. ☑ `dkms status` → `nvidia/595.91.07, 7.0.0-34-generic, x86_64: installed` y lo mismo para `7.0.0-38-generic`.
6. ☑ Reiniciar (2026-10-03, arrancó en el kernel 7.0.0-38). No apareció la pantalla azul del MOK: la clave ya inscrita bastó. (Si apareciera: *Enroll MOK → Continue → Yes*, contraseña y reiniciar.)
7. ☑ `nvidia-smi` → GTX 1650 Ti, driver 595.91.07, CUDA 13.2, 4096 MiB de VRAM.
8. ☑ Verificado (`True NVIDIA GeForce GTX 1650 Ti`). Comando: `.venv/bin/python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"` → `True NVIDIA GeForce GTX 1650 Ti`.

## Fase B — Reranker en la GPU, directo en Python (hecha el 2026-10-03)
7. ☑ Evaluación completa (dev, 335 consultas × 20 candidatos, `bge-reranker-v2-m3`, e5-small + híbrido + vigencia dura, corpus actual). Dos corridas:
   - fp16: `python pipeline/15_embeddings_con_reranker.py --modelos e5-small --dispositivo cuda --fp16 --lote 16 --sufijo=-gpu-local` → **4.777 s** (14,3 s por consulta).
   - fp32: `python pipeline/15_embeddings_con_reranker.py --modelos e5-small --dispositivo cuda --lote 8 --sufijo=-gpu-local-fp32` → **1.155 s** (3,4 s por consulta).
   Salidas: `rag-bocc/evaluacion/fase3a/embeddings-reranker-dev-gpu-local.json` y `…-gpu-local-fp32.json`.
8. ☑ Calidad: **idéntica** a la corrida en CPU sobre el mismo corpus (`…-dev-e5-corpus-actual.json`): doc@10 0,928 · cita@1 0,784 · cita@10 0,916 · MRR 0,841; variantes cita@1 0,500 · cita@10 0,821 · MRR 0,629. La GPU no cambia los resultados, solo el tiempo (ni siquiera fp16 movió una métrica).

### Latencia medida (20 pares de ~512 tokens, una consulta)
| Configuración | Segundos por consulta |
|---|---|
| CPU (medida antes) | ~16 |
| GPU GTX 1650 Ti, **fp32** (lote 4 / 8 / 16) | **3,9 / 4,0 / 4,3** (en la evaluación real, con fragmentos más cortos: 3,4) |
| GPU GTX 1650 Ti, fp16 (cualquier lote) | 16,3 (≈ CPU) |
| Voyage rerank-3 (API) | ~0,07 |

### Conclusiones de la Fase B
- **Usar fp32 en esta tarjeta.** fp16 es ~4 veces más lento: la GTX 1650 Ti (arquitectura Turing TU117) no tiene núcleos tensoriales, y en fp16 el modelo no se acelera. La causa exacta no se investigó; el dato medido es el de la tabla. El comando de `--fp16` de las notas anteriores (y de Colab T4, que sí tiene núcleos tensoriales) no aplica a esta GPU.
- La GPU local da **~4–5× de mejora** frente a la CPU, pero 3,4–4 s por consulta sigue siendo **mucho** para un asesor en línea (Voyage: 0,07 s, unas 50 veces menos). Sirve para evaluar y desarrollar sin depender de terceros, no para atender clientes.
- Temperatura de la GPU durante la carga: ~81 °C a 1.860 MHz, sin limitación de reloj reportada (`clocks_event_reasons.active` = 0). Con 4 GB cabe el modelo (≈2,8 GB en fp16 con lote 16; fp32 con lote 8 funcionó sin quedarse sin memoria).
- Una evaluación completa de 335 consultas son ~20 min en fp32; el script no imprime progreso, por eso conviene lanzarlo con `nohup … > _raw/<log> &`.

## Fase C — Docker con acceso a la GPU
9. ☐ Instalar `nvidia-container-toolkit` (repositorio oficial de NVIDIA para Ubuntu/Debian):
   ```
   curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
   curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
   sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
   ```
   (comandos tomados de la guía de instalación de NVIDIA; confirmar contra su documentación vigente antes de ejecutarlos)
10. ☐ Configurar Docker: `sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker`.
11. ☐ Probar: `docker run --rm --gpus all ubuntu nvidia-smi` → debe mostrar la misma tarjeta dentro del contenedor.

## Fase D — Reranker como servicio (contenedor)
12. ☐ Elegir el servidor: el servidor de inferencia de Hugging Face (Text Embeddings Inference, TEI) que, según su documentación, admite modelos de reranking como `bge-reranker`, **a confirmar**; o un servicio propio con FastAPI.
13. ☐ Levantarlo con la GPU, descargar el modelo, medir latencia y calidad con el mismo golden set (endpoint tipo `POST /rerank` con la consulta y los 20 fragmentos).
14. ☐ Documentar el comando exacto, los puertos, el volumen del modelo y los resultados aquí.

## Notas de diseño
- Esta GPU (4 GB) sirve para **pruebas y desarrollo**. Para producción conviene un servidor con GPU dedicada o el servicio de reranking de un proveedor (el banco ya aceptó un reranker externo con enmascaramiento de datos personales; Voyage rerank-3 fue el mejor medido).
- La GPU no se usa para los embeddings de Voyage/OpenAI (corren en su infraestructura). Sí acelera los embeddings locales grandes (`bge-m3`, `e5-large`) y el reranker.
- Mientras la GPU local no esté lista, `pipeline/colab/reranker_colab.ipynb` ejecuta la misma evaluación en una GPU T4 de Colab.

## Incidente 2026-10-02 (primer intento con el driver 580)
`sudo apt install nvidia-driver-580-open`, ejecutado desde el prompt de Claude Code, terminó con `Error! No write access to DKMS tree at /var/lib/dkms` y los paquetes `nvidia-dkms-580-open` y `nvidia-driver-580-open` quedaron **sin configurar** (el resto de librerías sí se instaló). Observaciones:
- **Causa confirmada (2026-10-02):** la carpeta `/var/lib/dkms` **no existe** en el equipo. El script `/usr/sbin/dkms` (3.0.11) ejecuta `check_rw_dkms_tree` (`[[ -w /var/lib/dkms ]]`) y, si falla, termina con «No write access to DKMS tree». No era una limitación de la sesión de Claude Code: el error se repitió igual en una terminal normal con el driver 595. Por qué faltaba la carpeta: no se sabe. Solución: `sudo mkdir -p /var/lib/dkms && sudo dpkg --configure -a`.
- Esa misma instalación generó el *initramfs* del kernel 7.0.0-38 (ya instalado, pero el equipo sigue arrancado en el 7.0.0-34).
- El aviso `NO_PUBKEY FC9CA96ACA026560` de `apt.releases.hashicorp.com` es de otro repositorio (HashiCorp) y no afecta a esta instalación.
- Se cambió a la rama 595 porque es la recomendada por el sistema y la 580 es más antigua que el kernel.
Si en una terminal normal vuelve a salir «No write access to DKMS tree»: `ls -ld /var/lib/dkms`, `sudo mkdir -p /var/lib/dkms` y `sudo dpkg --configure -a`.

## Problemas frecuentes
- **`nvidia-smi` dice «NVIDIA-SMI has failed…» tras reiniciar:** casi siempre es Secure Boot sin inscribir la clave. Repetir el paso 4 o revisar `mokutil --sb-state` y `sudo mokutil --list-new`.
- **El sistema arranca en pantalla negra:** en el menú de arranque elegir un kernel anterior (Opciones avanzadas) y desinstalar el driver: `sudo apt purge 'nvidia-*' && sudo apt autoremove`.
- **`CUDA out of memory`:** reducir el tamaño de lote o usar fp16; cerrar otras aplicaciones que usen la GPU (`nvidia-smi` lista los procesos).
- **Portátil con dos GPU:** el escritorio puede seguir usando la Intel; para que un programa use la NVIDIA, el reranker basta con elegir `cuda` (PyTorch ve la NVIDIA directamente).
