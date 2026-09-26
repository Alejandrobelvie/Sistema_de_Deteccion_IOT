from app.core.security import (
    BiometricEncryption,
    RateLimiter,
    compute_log_hash,
    verify_log_integrity,
)


def test_biometric_encryption_round_trip_and_random_nonce():
    cipher = BiometricEncryption("1" * 64)
    payload = b"biometric-template"

    first = cipher.encrypt_biometric_template(payload)
    second = cipher.encrypt_biometric_template(payload)

    assert first != second
    assert cipher.decrypt_biometric_template(first) == payload


def test_log_hash_can_be_verified_and_detects_tampering():
    digest = compute_log_hash("event", "previous")

    assert verify_log_integrity("event", digest, "previous")
    assert not verify_log_integrity("changed", digest, "previous")


def test_rate_limiter_locks_at_limit_and_can_reset():
    limiter = RateLimiter(max_attempts=2, lockout_minutes=1)

    assert not limiter.record_attempt("client")
    assert limiter.record_attempt("client")
    assert limiter.is_locked_out("client")

    limiter.reset("client")
    assert not limiter.is_locked_out("client")


def test_biometric_key_must_be_hexadecimal():
    try:
        BiometricEncryption("z" * 64)
    except ValueError as exc:
        assert "hexadecimales" in str(exc)
    else:
        raise AssertionError("Se aceptó una clave no hexadecimal")
