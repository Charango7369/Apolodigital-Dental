# app/core/csrf.py
"""
Módulo de Protección Criptográfica Anti-CSRF (Double Submit Cookie).
Mitiga ataques de falsificación de peticiones en sitios cruzados (Cross-Site Request Forgery)
para sesiones basadas en cookies HttpOnly cross-origin.
"""
import hmac
import secrets


def generate_csrf_token(length_bytes: int = 32) -> str:
    """Genera un token CSRF criptográfico de alta entropía (256 bits)."""
    return secrets.token_urlsafe(length_bytes)


def verify_csrf_token(header_token: str | None, cookie_token: str | None) -> bool:
    """
    Verifica que el token enviado en la cabecera HTTP (X-CSRF-Token)
    coincida exactamente con el token almacenado en la cookie 'csrf_token'.
    Utiliza comparación en tiempo constante contra timing attacks.
    """
    if not header_token or not cookie_token:
        return False
    
    clean_header = header_token.strip()
    clean_cookie = cookie_token.strip()
    
    if len(clean_header) < 16 or len(clean_cookie) < 16:
        return False
        
    return hmac.compare_digest(clean_header, clean_cookie)
