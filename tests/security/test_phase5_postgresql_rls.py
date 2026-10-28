# tests/security/test_phase5_postgresql_rls.py
"""
Suite de Pruebas de Seguridad Ofensiva y Defensiva - FASE 5:
Aislamiento Multi-Tenant con PostgreSQL Row-Level Security (RLS).

Valida que el motor PostgreSQL imponga aislamiento estricto e inquebrantable
entre clínicas (tenants) incluso frente a fallos en la capa de aplicación,
consultas sin cláusulas WHERE o inyecciones SQL simuladas.
"""
import uuid
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.core.tenant_context import (
    apply_db_tenant_context,
    reset_db_tenant_context,
    TenantDBScope,
)


async def create_test_clinic(session: AsyncSession, clinic_id: uuid.UUID, name: str):
    """Inserta una clínica de prueba en la tabla tenants en modo bypass."""
    await session.execute(text(f"""
        INSERT INTO tenants (id, name, is_active)
        VALUES ('{clinic_id}', '{name}', true)
        ON CONFLICT (id) DO NOTHING
    """))


async def delete_test_clinic(session: AsyncSession, clinic_id: uuid.UUID):
    """Elimina una clínica de prueba y sus dependencias en cascada."""
    await session.execute(text(f"DELETE FROM tenants WHERE id = '{clinic_id}'"))


@pytest.mark.asyncio
async def test_rls_fail_closed_posture_blocks_reads_when_context_unset():
    """
    Defensa en Profundidad:
    Si una conexión ejecuta una consulta sin haber definido 'app.current_tenant_id'
    y sin bandera de bypass, PostgreSQL debe adoptar postura Fail-Closed (Default Deny),
    devolviendo CERO filas y ocultando cualquier registro médico.
    """
    async with AsyncSessionLocal() as session:
        # Aseguramos contexto limpio y rol no privilegiado
        await apply_db_tenant_context(session, tenant_id=None, bypass=False)
        
        # Consulta sin filtro WHERE sobre pacientes
        result = await session.execute(text("SELECT id, first_name FROM patients"))
        rows = result.fetchall()
        
        # En postura Fail-Closed, ninguna fila debe ser visible
        assert len(rows) == 0, f"Vulnerabilidad RLS: Se expusieron {len(rows)} pacientes con contexto vacío"
        await reset_db_tenant_context(session)


@pytest.mark.asyncio
async def test_rls_fail_closed_posture_blocks_inserts_when_context_unset():
    """
    Defensa en Profundidad:
    Cualquier intento de inserción sin un contexto de tenant explícito debe ser
    bloqueado por la cláusula WITH CHECK de PostgreSQL RLS.
    """
    tenant_id = uuid.uuid4()
    patient_id = uuid.uuid4()
    
    async with AsyncSessionLocal() as session:
        # Creamos la clínica en tenants primero
        await apply_db_tenant_context(session, bypass=True)
        await create_test_clinic(session, tenant_id, "Clinica Fail Closed")
        await session.commit()

        # Cambiamos a contexto NO configurado (Fail-Closed)
        await apply_db_tenant_context(session, tenant_id=None, bypass=False)
        
        with pytest.raises(Exception) as exc_info:
            await session.execute(text(f"""
                INSERT INTO patients (id, tenant_id, first_name, last_name, is_active)
                VALUES ('{patient_id}', '{tenant_id}', 'Intruder', 'Patient', true)
            """))
            await session.commit()
            
        error_msg = str(exc_info.value).lower()
        assert "row-level security" in error_msg or "policy" in error_msg
        await session.rollback()

        # Limpieza
        await apply_db_tenant_context(session, bypass=True)
        await delete_test_clinic(session, tenant_id)
        await session.commit()
        await reset_db_tenant_context(session)


@pytest.mark.asyncio
async def test_rls_cross_tenant_isolation_reads():
    """
    Prueba Ofensiva de Aislamiento Horizontal:
    Se crean dos clínicas distintas (Tenant A y Tenant B).
    Se verifica que una consulta sin cláusula WHERE ejecutada en la sesión del Tenant A
    JAMÁS retorne pacientes pertenecientes al Tenant B.
    """
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    p_a_id = uuid.uuid4()
    p_b_id = uuid.uuid4()

    # 1. Crear clínicas y pacientes para cada clínica dentro de sus respectivos contextos
    async with AsyncSessionLocal() as session:
        await apply_db_tenant_context(session, bypass=True)
        await create_test_clinic(session, tenant_a, "Clinica Alfa")
        await create_test_clinic(session, tenant_b, "Clinica Beta")
        await session.commit()

        # Sesión Tenant A
        await apply_db_tenant_context(session, tenant_id=tenant_a)
        await session.execute(text(f"""
            INSERT INTO patients (id, tenant_id, first_name, last_name, is_active)
            VALUES ('{p_a_id}', '{tenant_a}', 'Paciente', 'Clinica A', true)
        """))
        await session.commit()

        # Sesión Tenant B
        await apply_db_tenant_context(session, tenant_id=tenant_b)
        await session.execute(text(f"""
            INSERT INTO patients (id, tenant_id, first_name, last_name, is_active)
            VALUES ('{p_b_id}', '{tenant_b}', 'Paciente', 'Clinica B', true)
        """))
        await session.commit()
        await reset_db_tenant_context(session)

    # 2. Verificar lectura desde Tenant A
    async with AsyncSessionLocal() as session:
        await apply_db_tenant_context(session, tenant_id=tenant_a)
        # Consulta cruda sin WHERE
        result = await session.execute(text("SELECT id, first_name, last_name FROM patients"))
        rows_a = result.fetchall()
        ids_a = [r[0] for r in rows_a]

        assert p_a_id in ids_a, "Tenant A no puede ver su propio paciente"
        assert p_b_id not in ids_a, "CRÍTICO: Tenant A puede ver el paciente del Tenant B!"
        await reset_db_tenant_context(session)

    # 3. Verificar lectura desde Tenant B
    async with AsyncSessionLocal() as session:
        await apply_db_tenant_context(session, tenant_id=tenant_b)
        result = await session.execute(text("SELECT id, first_name, last_name FROM patients"))
        rows_b = result.fetchall()
        ids_b = [r[0] for r in rows_b]

        assert p_b_id in ids_b, "Tenant B no puede ver su propio paciente"
        assert p_a_id not in ids_b, "CRÍTICO: Tenant B puede ver el paciente del Tenant A!"
        await reset_db_tenant_context(session)

    # 4. Limpieza en modo bypass
    async with AsyncSessionLocal() as session:
        await apply_db_tenant_context(session, bypass=True)
        await session.execute(text(f"DELETE FROM patients WHERE id IN ('{p_a_id}', '{p_b_id}')"))
        await delete_test_clinic(session, tenant_a)
        await delete_test_clinic(session, tenant_b)
        await session.commit()
        await reset_db_tenant_context(session)


@pytest.mark.asyncio
async def test_rls_cross_tenant_insertion_blocked_by_with_check():
    """
    Vector de Ataque de Inyección / Manipulación de IDs:
    Un usuario autenticado en la Clínica A intenta insertar un registro forzando
    el tenant_id de la Clínica B en el payload.
    PostgreSQL RLS WITH CHECK debe abortar la transacción a nivel de motor.
    """
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    malicious_patient_id = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        await apply_db_tenant_context(session, bypass=True)
        await create_test_clinic(session, tenant_a, "Clinica A Inyeccion")
        await create_test_clinic(session, tenant_b, "Clinica B Inyeccion")
        await session.commit()

        # Contexto activo = Clínica A
        await apply_db_tenant_context(session, tenant_id=tenant_a)

        # Intento de insertar paciente para Clínica B
        with pytest.raises(Exception) as exc_info:
            await session.execute(text(f"""
                INSERT INTO patients (id, tenant_id, first_name, last_name, is_active)
                VALUES ('{malicious_patient_id}', '{tenant_b}', 'Injected', 'CrossTenant', true)
            """))
            await session.commit()

        error_message = str(exc_info.value).lower()
        assert "row-level security" in error_message or "violates" in error_message or "policy" in error_message
        await session.rollback()

        # Limpieza
        await apply_db_tenant_context(session, bypass=True)
        await delete_test_clinic(session, tenant_a)
        await delete_test_clinic(session, tenant_b)
        await session.commit()
        await reset_db_tenant_context(session)


@pytest.mark.asyncio
async def test_rls_cross_tenant_update_and_delete_tampering_blocked():
    """
    Vector de Manipulación Directa (Tampering):
    La Clínica A intenta ejecutar un UPDATE o DELETE especificando el ID de un paciente
    de la Clínica B. RLS debe hacer que la fila sea invisible, resultando en 0 filas afectadas.
    """
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    p_b_id = uuid.uuid4()

    # 1. Crear clínicas y paciente para Clínica B en modo bypass
    async with AsyncSessionLocal() as session:
        await apply_db_tenant_context(session, bypass=True)
        await create_test_clinic(session, tenant_a, "Clinica A Tamper")
        await create_test_clinic(session, tenant_b, "Clinica B Tamper")
        await session.execute(text(f"""
            INSERT INTO patients (id, tenant_id, first_name, last_name, is_active)
            VALUES ('{p_b_id}', '{tenant_b}', 'Original', 'PatientB', true)
        """))
        await session.commit()
        await reset_db_tenant_context(session)

    # 2. Clínica A intenta modificar el paciente de Clínica B
    async with AsyncSessionLocal() as session:
        await apply_db_tenant_context(session, tenant_id=tenant_a)
        res_update = await session.execute(text(f"""
            UPDATE patients SET first_name = 'HACKED' WHERE id = '{p_b_id}'
        """))
        await session.commit()
        # RLS oculta la fila para el Tenant A: 0 filas modificadas
        assert res_update.rowcount == 0, "CRÍTICO: Tenant A pudo modificar datos del Tenant B!"

        # Clínica A intenta eliminar el paciente de Clínica B
        res_delete = await session.execute(text(f"""
            DELETE FROM patients WHERE id = '{p_b_id}'
        """))
        await session.commit()
        assert res_delete.rowcount == 0, "CRÍTICO: Tenant A pudo eliminar un registro del Tenant B!"
        await reset_db_tenant_context(session)

    # 3. Verificar que el paciente de Clínica B sigue intacto
    async with AsyncSessionLocal() as session:
        await apply_db_tenant_context(session, tenant_id=tenant_b)
        res = await session.execute(text(f"SELECT first_name FROM patients WHERE id = '{p_b_id}'"))
        name = res.scalar()
        assert name == "Original", "Los datos del paciente fueron alterados"

        # Limpieza
        await apply_db_tenant_context(session, bypass=True)
        await session.execute(text(f"DELETE FROM patients WHERE id = '{p_b_id}'"))
        await delete_test_clinic(session, tenant_a)
        await delete_test_clinic(session, tenant_b)
        await session.commit()
        await reset_db_tenant_context(session)


@pytest.mark.asyncio
async def test_rls_medical_and_financial_tables_isolation():
    """
    Aislamiento Multi-Tenant en Tablas Críticas de Salud y Facturación:
    Verifica que 'odontograms' (PHI) y 'accounts_receivable' (Financiero)
    estén igualmente protegidas por las políticas RLS.
    """
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    patient_a = uuid.uuid4()
    odontogram_a = uuid.uuid4()
    billing_a = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        # Preparamos clínicas, paciente, odontograma y cuenta para Tenant A en bypass
        await apply_db_tenant_context(session, bypass=True)
        await create_test_clinic(session, tenant_a, "Clinica A PHI")
        await create_test_clinic(session, tenant_b, "Clinica B PHI")
        await session.execute(text(f"""
            INSERT INTO patients (id, tenant_id, first_name, last_name, is_active)
            VALUES ('{patient_a}', '{tenant_a}', 'PacienteSalud', 'ClinicaA', true)
        """))
        await session.execute(text(f"""
            INSERT INTO odontograms (id, tenant_id, patient_id, doctor_id, description, is_active)
            VALUES ('{odontogram_a}', '{tenant_a}', '{patient_a}', '{uuid.uuid4()}', 'Odontograma Privado', true)
        """))
        await session.execute(text(f"""
            INSERT INTO accounts_receivable (id, tenant_id, patient_id, total_amount, balance_due, status, description, is_active)
            VALUES ('{billing_a}', '{tenant_a}', '{patient_a}', 500.00, 500.00, 'PENDING', 'Tratamiento Corona', true)
        """))
        await session.commit()
        await reset_db_tenant_context(session)

    # Verificar desde Tenant B
    async with AsyncSessionLocal() as session:
        await apply_db_tenant_context(session, tenant_id=tenant_b)

        # Odontograma
        res_odont = await session.execute(text(f"SELECT id FROM odontograms WHERE id = '{odontogram_a}'"))
        assert res_odont.fetchall() == [], "Fuga de PHI: Tenant B pudo leer odontograma de Tenant A"

        # Facturación
        res_bill = await session.execute(text(f"SELECT id FROM accounts_receivable WHERE id = '{billing_a}'"))
        assert res_bill.fetchall() == [], "Fuga Financiera: Tenant B pudo leer cobranza de Tenant A"
        await reset_db_tenant_context(session)

    # Limpieza en bypass
    async with AsyncSessionLocal() as session:
        await apply_db_tenant_context(session, bypass=True)
        await session.execute(text(f"DELETE FROM accounts_receivable WHERE id = '{billing_a}'"))
        await session.execute(text(f"DELETE FROM odontograms WHERE id = '{odontogram_a}'"))
        await session.execute(text(f"DELETE FROM patients WHERE id = '{patient_a}'"))
        await delete_test_clinic(session, tenant_a)
        await delete_test_clinic(session, tenant_b)
        await session.commit()
        await reset_db_tenant_context(session)


@pytest.mark.asyncio
async def test_rls_superadmin_bypass_allows_global_visibility():
    """
    Comprobación de Bypass para SUPER_ADMIN:
    Cuando 'app.bypass_rls' es 'true', los procesos administrativos legítimos
    (auditoría global, exportación de plataforma, migraciones) deben tener
    visibilidad completa de las tablas.
    """
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    p_a = uuid.uuid4()
    p_b = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        await apply_db_tenant_context(session, bypass=True)
        await create_test_clinic(session, tenant_a, "Clinica A SA")
        await create_test_clinic(session, tenant_b, "Clinica B SA")
        await session.execute(text(f"""
            INSERT INTO patients (id, tenant_id, first_name, last_name, is_active)
            VALUES ('{p_a}', '{tenant_a}', 'SA_A', 'Test', true),
                   ('{p_b}', '{tenant_b}', 'SA_B', 'Test', true)
        """))
        await session.commit()

        # Consulta con bypass=True
        res = await session.execute(text(f"SELECT id FROM patients WHERE id IN ('{p_a}', '{p_b}')"))
        found_ids = [r[0] for r in res.fetchall()]
        assert p_a in found_ids and p_b in found_ids, "SuperAdmin en bypass debe ver registros de ambas clínicas"

        # Limpieza
        await session.execute(text(f"DELETE FROM patients WHERE id IN ('{p_a}', '{p_b}')"))
        await delete_test_clinic(session, tenant_a)
        await delete_test_clinic(session, tenant_b)
        await session.commit()
        await reset_db_tenant_context(session)


@pytest.mark.asyncio
async def test_tenant_db_scope_context_manager():
    """
    Verifica la ergonomía y seguridad del context manager TenantDBScope:
    Asegura que establezca el contexto al entrar y lo restablezca determinísticamente al salir.
    """
    target_tenant = uuid.uuid4()

    async with AsyncSessionLocal() as session:
        async with TenantDBScope(session, tenant_id=target_tenant):
            res = await session.execute(text("SELECT current_setting('app.current_tenant_id', true)"))
            assert res.scalar() == str(target_tenant)

        # Fuera del context manager, debe haberse restablecido
        res = await session.execute(text("SELECT current_setting('app.current_tenant_id', true)"))
        val = res.scalar()
        assert val == "" or val is None, f"El contexto no fue limpiado al salir de TenantDBScope: {val}"
