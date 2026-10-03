class IdempotencyConflictError(Exception):
    """Same idempotency key used with a different payment payload."""
