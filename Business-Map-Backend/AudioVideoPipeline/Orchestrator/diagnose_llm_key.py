# Run this from AudioVideoPipeline/Orchestrator, same folder you run the backend from.
import os

print("── Step 1: is cryptography installed? ──")
try:
    import cryptography
    from cryptography.fernet import Fernet
    print("OK — cryptography is installed, version:", cryptography.__version__)
except ImportError as e:
    print("FAIL —", e)
    print("FIX: pip install -r requirements_orchestrator.txt --break-system-packages")
    raise SystemExit

print()
print("── Step 2: is .env actually being loaded, and is the key present? ──")
import database  # this triggers python-dotenv's load_dotenv(), same as the real backend
key = os.environ.get("LLM_CONFIG_ENCRYPTION_KEY", "")
if not key:
    print("FAIL — LLM_CONFIG_ENCRYPTION_KEY is not visible in this process's environment.")
    print("FIX: check the .env file this script/backend actually reads, and that the line has no typo/quotes.")
    raise SystemExit
print("OK — key found, length:", len(key), "chars")

print()
print("── Step 3: is the key a valid Fernet key? ──")
try:
    Fernet(key.encode())
    print("OK — key is valid.")
except Exception as e:
    print("FAIL —", e)
    print("FIX: regenerate with:")
    print('  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"')
    raise SystemExit

print()
print("── Final: what does the app itself report? ──")
print("llm_encryption_available() =", database.llm_encryption_available())