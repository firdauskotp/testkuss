from werkzeug.security import generate_password_hash

raw_password = "@dmin@KE00@@dmin"

new_pass = "Asyraf"

test_pass="test"
hashed_password = generate_password_hash(new_pass, method="pbkdf2:sha256", salt_length=16)
print(hashed_password)
