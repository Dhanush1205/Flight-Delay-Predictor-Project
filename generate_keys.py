import os
import secrets

# Generate SECRET_KEY
secret_key = secrets.token_hex(24)
print(f"SECRET_KEY={secret_key}")

# Generate SECURITY_PASSWORD_SALT
password_salt = secrets.token_hex(24)
print(f"SECURITY_PASSWORD_SALT={password_salt}") 