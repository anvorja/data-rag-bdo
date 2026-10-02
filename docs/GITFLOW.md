# Estrategia de ramas, PR y CI — RAG Banco de Occidente

> Adaptada de la guía GitFlow/CI-CD del proyecto Lazarus (`GitFlow_CICD.md`) y de sus rulesets de GitHub. Aquí no hay aplicación desplegable ni imágenes Docker: el «producto» es **el corpus, el golden set y el pipeline**.

## Ramas (GitFlow)

| Rama | Origen | Destino | Uso |
|---|---|---|---|
| `main` | — | — | Versiones publicadas del corpus/pipeline. Solo recibe `release/*` y `hotfix/*`; cada merge lleva etiqueta `vX.Y.Z`. |
| `develop` | `main` | — | Integración. Solo recibe PR de `feature/*` con CI en verde. |
| `feature/<descripcion>` | `develop` | `develop` | Una por tarea (`feature/fase2-golden-set`, `feature/rastreo-empresas`). Minúsculas y guiones. |
| `release/vX.Y.Z` | `develop` | `main` y `develop` | Estabilización de un hito: revisión de la muestra, notas de versión. |
| `hotfix/<descripcion>` | `main` | `main` y `develop` | Corrección urgente (p. ej. un dato erróneo en una versión publicada). |

**Versionado:** `v0.x` mientras el golden set y la línea base no estén aprobados; `v1.0.0` al pasar a piloto. Los **datos** se versionan además con **etiquetas de instantánea** (no con ramas): `corpus-AAAA-MM-DD` y `golden-vN`.

## Integración y protecciones

- **`feature/*` → `develop`: Squash and merge** (un commit por tarea; la rama se borra).
- **`release/*` y `hotfix/*` → `main`: merge commit** (conserva el historial de la versión y permite la etiqueta). Es lo que traen los rulesets base. Si prefieres squash también en `main`, cambia `allowed_merge_methods` a `["squash"]` en `.github/rulesets/main.json`.
- `main` y `develop`: PR obligatorio, sin push directo, sin force-push, sin borrado (`.github/rulesets/`).

### `required_status_checks`: cómo manejarlo

Los rulesets base exigían `Lint`, `Calidad y build` e `Imagen Docker`. Aquí **no hay build ni imagen**, así que ese requisito dejaría los PR bloqueados para siempre (un check requerido que nunca se ejecuta no se cumple). Decisión:

1. Se **mantiene** el requisito, pero con los checks que sí existen en este repositorio (`.github/workflows/ci.yml`):
   - **`Lint`**: `ruff check pipeline`.
   - **`Calidad de datos y secretos`**: `pipeline/validate.py` (coherencia corpus ↔ índice, frontmatter, golden set, tamaños, patrones de secretos) + `gitleaks`.
2. **Orden de activación** (importante): (a) crear el remoto y subir `main` y `develop`; (b) abrir un primer PR para que los dos checks se ejecuten y GitHub los reconozca; (c) recién entonces aplicar los rulesets. Si se aplican antes, el primer PR queda bloqueado.
3. Si no quieres exigir checks (p. ej. repositorio privado sin Actions disponibles), usa las variantes `*.sin-checks.json`: mantienen PR obligatorio, squash en `develop`, sin force-push ni borrado.
4. `integration_id: 15368` corresponde a la aplicación **GitHub Actions**.

Aplicación con la CLI (cuando exista el remoto):
```bash
gh api -X POST repos/<usuario>/<repo>/rulesets --input .github/rulesets/develop.json
gh api -X POST repos/<usuario>/<repo>/rulesets --input .github/rulesets/main.json
```

## Convenciones

- **Commits:** en español, verbo en presente, una idea por commit: `Agrega auditoría automática del corpus`. (No hay clave Jira en este proyecto; si se adopta una, anteponerla: `RAG-12 …`.)
- **Autoría:** todos los commits van con la autoría del propietario del repositorio; **no** se incluyen líneas `Co-Authored-By` ni autoría de terceros o de herramientas.
- **PR:** usar la plantilla (`.github/pull_request_template.md`). Título breve; descripción con qué cambia, cómo probarlo y el checklist.
- **Secretos:** nunca en el repositorio ni en los datos. `.env.example` documenta las variables **sin valores**; los valores viven en un `.env` local (ignorado) o en GitHub Secrets. CI revisa patrones de claves y corre `gitleaks`.

## Qué se versiona y qué no

| Sí | No (ver `.gitignore`) |
|---|---|
| `pipeline/`, `docs/`, `.github/` | `_raw/` (≈ 1,8 GB de originales) → guardar fuera del repo (disco/objeto) con un manifiesto de hashes |
| `rag-bocc/documentos/**/*.md`, `indice.json`, `auditoria/`, `README.md`, `omitidos-lote2.json`, `enlaces-pendientes.*` | `rag-bocc/corpus.jsonl` (≈ 130 MB, se regenera con el pipeline; GitHub rechaza archivos > 100 MB) |
| Guías (`RAG en producción …`), `enlaces-*.txt|json` | `.env`, claves, credenciales |
| Golden set (`rag-bocc/golden/`) cuando exista | |

## Flujo de una tarea

1. `git switch develop && git pull` → `git switch -c feature/<descripcion>`.
2. Commits pequeños; `python pipeline/validate.py` antes de subir.
3. PR a `develop` con la plantilla; CI en verde; **Squash and merge**; se borra la rama.
4. Al cerrar un hito: `release/vX.Y.Z` (muestra de revisión humana, notas), merge a `main` con etiqueta y retro-merge a `develop`.
