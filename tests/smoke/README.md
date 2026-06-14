# Database Smoke Tests

Esta suite verifica la integridad estructural de la base de datos PostgreSQL, la configuración de SQLAlchemy 2.0 y las reglas de arquitectura Multi-Tenant.

## Ejecución vía Pytest (Recomendado para desarrollo)

```bash
pytest tests/smoke/ -v
