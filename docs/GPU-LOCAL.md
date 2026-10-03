# GPU local (NVIDIA GTX 1650 Ti) para el reranker: configuración paso a paso

Estado: **en curso** (se actualiza a medida que cada paso se ejecuta y se verifica). Equipo: Linux Mint 22.3 (base Ubuntu 24.04), kernel 7.0.0-34-generic, Secure Boot **activado**,
GPU NVIDIA GeForce GTX 1650 Ti Mobile (TU117M, 4 GB) + Intel UHD integrada. Docker 29.8.2 ya instalado y el usuario pertenece al grupo `docker`.

Objetivo: poder ejecutar el reranker abierto `BAAI/bge-reranker-v2-m3` (≈1,1 GB en fp16) en la GPU local, primero directo en Python y luego como servicio en un contenedor Docker.
Línea base medida: en CPU tarda unos 16 s por consulta (20 candidatos).

Leyenda: ☐ pendiente · ☑ hecho y verificado.

## Antes de empezar: estado inicial (verificado el 2026-10-02)
- El sistema usa el driver libre `nouveau`; no hay paquetes `nvidia-driver-*` ni `nvidia-container-toolkit` instalados. `nvidia-smi` no existe.
- `ubuntu-drivers devices` ofrece: `nvidia-driver-580-open`, `nvidia-driver-580-server(-open)`, `nvidia-driver-595`, `nvidia-driver-595-server`.
- PyTorch del proyecto (`.venv`): 2.7.1+cu126; con el driver actual `torch.cuda.is_available()` da `False`.

## Fase A — Driver de NVIDIA (requiere `sudo` y reinicio)
1. ☐ Ver qué driver recomienda el sistema: `ubuntu-drivers devices | grep -E "recommended|driver"`.
2. ☐ Instalar el driver y las cabeceras del kernel: `sudo apt update && sudo apt install -y linux-headers-$(uname -r) nvidia-driver-580-open`
   (la GTX 1650 Ti es de la generación Turing, que admite los módulos abiertos; si el sistema recomendara otro, usar ese).
3. ☐ **Secure Boot:** durante la instalación pide **crear una contraseña** (para inscribir la clave del módulo, «MOK»). Anotarla.
4. ☐ Reiniciar. En la pantalla azul «Perform MOK management» elegir *Enroll MOK → Continue → Yes*, escribir la contraseña y reiniciar.
5. ☐ Verificar: `nvidia-smi` debe mostrar la tarjeta y la versión del driver; `lsmod | grep nvidia` debe listar módulos.
6. ☐ Verificar PyTorch: `.venv/bin/python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"` → `True NVIDIA GeForce GTX 1650 Ti`.
Si algo falla: ver «Problemas frecuentes» al final.

## Fase B — Reranker en la GPU, directo en Python
7. ☐ Ejecutar la evaluación con GPU: `python pipeline/15_embeddings_con_reranker.py --modelos e5-small --dispositivo cuda --fp16 --lote 16 --sufijo=-gpu-local`
   (4 GB de VRAM alcanzan para el modelo en fp16; si se queda sin memoria, bajar `--lote` a 8 o 4).
8. ☐ Anotar el tiempo por consulta y comparar con la CPU (~16 s) y con Voyage (~0,07 s). Los resultados de calidad deben ser casi idénticos a los de CPU.

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

## Problemas frecuentes
- **`nvidia-smi` dice «NVIDIA-SMI has failed…» tras reiniciar:** casi siempre es Secure Boot sin inscribir la clave. Repetir el paso 4 o revisar `mokutil --sb-state` y `sudo mokutil --list-new`.
- **El sistema arranca en pantalla negra:** en el menú de arranque elegir un kernel anterior (Opciones avanzadas) y desinstalar el driver: `sudo apt purge 'nvidia-*' && sudo apt autoremove`.
- **`CUDA out of memory`:** reducir el tamaño de lote o usar fp16; cerrar otras aplicaciones que usen la GPU (`nvidia-smi` lista los procesos).
- **Portátil con dos GPU:** el escritorio puede seguir usando la Intel; para que un programa use la NVIDIA, el reranker basta con elegir `cuda` (PyTorch ve la NVIDIA directamente).
