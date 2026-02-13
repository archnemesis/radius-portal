import secrets
import string


_ALPHABET = string.ascii_uppercase + string.digits


def generate_code(length: int = 8) -> str:
    # Avoid confusing characters if you want: remove O/0, I/1, etc.
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))

