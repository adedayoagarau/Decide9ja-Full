import sys
import shutil
import importlib

print("🔍 Verifying Project Dependencies...\n")

# 1. Check Python Packages
packages = [
    ("tenacity", "Reliability"),
    ("langdetect", "Language Detection"),
    ("phonenumbers", "Phone Validation"),
    ("diffprivlib", "Differential Privacy"),
    ("jose", "JWT Security"),
    ("prometheus_fastapi_instrumentator", "Monitoring"),
    ("structlog", "Structured Logging"),
    ("pandas", "Data Analysis"),
    ("rapidfuzz", "Fuzzy Matching"),
    ("pytesseract", "OCR")
]

all_good = True

print("📦 Checking Python Libraries:")
for package, desc in packages:
    try:
        importlib.import_module(package)
        print(f"  ✅ {package:<30} ({desc}) - Installed")
    except ImportError:
        print(f"  ❌ {package:<30} ({desc}) - MISSING")
        all_good = False

# 2. Check System Binaries
print("\n🛠 Checking System Binaries:")
binaries = ["tesseract"]
for binary in binaries:
    path = shutil.which(binary)
    if path:
        print(f"  ✅ {binary:<30} - Found at {path}")
    else:
        print(f"  ⚠️ {binary:<30} - NOT FOUND (OCR features may fail)")
        # Tesseract is often optional but good to warn about
        
# 3. Functional Test
print("\n🧪 Running Functional Tests:")
try:
    from langdetect import detect
    lang = detect("Bawo ni? Kedu?")
    print(f"  ✅ Language Detect: 'Bawo ni? Kedu?' -> {lang}")
except Exception as e:
    print(f"  ❌ Language Detect Failed: {e}")
    all_good = False

try:
    import phonenumbers
    x = phonenumbers.parse("+2348031234567", None)
    valid = phonenumbers.is_valid_number(x)
    print(f"  ✅ Phone Validation: '+2348031234567' -> Valid? {valid}")
except Exception as e:
    print(f"  ❌ Phone Validation Failed: {e}")
    all_good = False

print("\n" + ("="*30))
if all_good:
    print("🎉 ALL CHECKS PASSED! The environment is ready.")
else:
    print("⚠️ SOME ISSUES FOUND. See above.")
