#!/usr/bin/env python3
"""
Apolodigital Dental SaaS - Cryptographic Secret Generator
Generates high-entropy secrets for JWT, refresh tokens, and internal signatures.
"""
import secrets


def generate_secure_secrets():
    jwt_secret = secrets.token_hex(32)         # 256 bits of entropy
    jwt_refresh_secret = secrets.token_hex(32) # 256 bits of entropy
    ci_token = secrets.token_hex(32)           # 256 bits of entropy

    print("=" * 70)
    print("🔐 CLAVES CRIPTOGRÁFICAS GENERADAS CON ALTA ENTROPÍA (secrets.token_hex)")
    print("=" * 70)
    print(f"JWT_SECRET={jwt_secret}")
    print(f"JWT_REFRESH_SECRET={jwt_refresh_secret}")
    print(f"CI_SECRET_TOKEN={ci_token}")
    print("=" * 70)
    print("⚠️  ADVERTENCIA DE SEGURIDAD:")
    print("1. Copie estas variables en su archivo .env y en el panel de Railway / Cloudflare.")
    print("2. NUNCA las commitee en repositorios públicos o privados de Git.")
    print("3. La modificación de JWT_SECRET invalidará automáticamente todas las sesiones activas.")
    print("=" * 70)


if __name__ == "__main__":
    generate_secure_secrets()
