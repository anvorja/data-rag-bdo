## Qué cambia
<!-- Resumen breve y por qué -->

## Cómo probarlo
<!-- Comandos o pasos: `python pipeline/validate.py`, etc. -->

## Checklist
- [ ] CI en verde (Lint, Calidad de datos y secretos).
- [ ] Sin secretos, claves ni variables de entorno en el código ni en los datos.
- [ ] Si cambia el corpus: regenerado con `pipeline/` y `auditoria/` actualizada.
- [ ] Si cambia el golden set: `split` de prueba intacto (no se modifica `test` sin una versión nueva) y `cita_literal` verificada.
- [ ] Documentación actualizada (README / guía).
