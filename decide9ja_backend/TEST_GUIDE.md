# Tade Integration Test Guide

## Quick Test (Syntax Only)
```bash
cd /Volumes/Admin/Decide9ja/decide9ja_backend
python3 -m py_compile app/services/working_memory_enhanced.py
python3 -m py_compile app/services/error_recovery_enhanced.py
python3 -m py_compile app/services/supermemory_integration.py
python3 -m py_compile app/services/tade_unified.py
python3 -m py_compile app/services/test_tade_integration.py
echo "✅ All files syntax OK"
```

## Full Test Suite (Requires venv)

### 1. Create virtual environment
```bash
cd /Volumes/Admin/Decide9ja/decide9ja_backend
python3 -m venv .testvenv
source .testvenv/bin/activate
```

### 2. Install dependencies
```bash
pip install pytest pytest-asyncio httpx
```

### 3. Run tests
```bash
python -m pytest app/services/test_tade_integration.py -v
```

## Expected Test Results

### ✅ Working Memory Tests (7 tests)
- [x] Initialization
- [x] Stage transitions
- [x] Location setting
- [x] Query setting
- [x] Clarification flow
- [x] Error tracking
- [x] Compression recovery
- [x] Serialization

### ✅ Location Identification Tests (8 tests)
- [x] Exact state match
- [x] Fuzzy state match
- [x] Pidgin patterns
- [x] LGA identification
- [x] Alias matching
- [x] Cross-state LGA matching
- [x] Unknown location handling
- [x] With current state

### ✅ Error Recovery Tests (6 tests)
- [x] Ambiguous location
- [x] Unknown location
- [x] Vague query
- [x] No results
- [x] General error escalation
- [x] Handle error function

### ✅ Query Classification Tests (4 tests)
- [x] Representative queries
- [x] Budget queries
- [x] News queries
- [x] Archive queries

### ✅ Progressive Disclosure Tests (4 tests)
- [x] First interaction
- [x] Second interaction
- [x] Third interaction
- [x] Regular user (no message)

### ✅ Stage Transition Tests (3 tests)
- [x] New user flow
- [x] Returning user flow
- [x] Reset command

### ✅ Integration Tests (2 tests)
- [x] Full conversation flow
- [x] Escape commands

**Total: 34 tests**

## Manual Testing

### Test 1: Location Identification
```python
from app.services.tade_unified import LocationIdentifier

locator = LocationIdentifier()

# Test Pidgin
result = locator.identify("I dey Lagos")
assert result["state"] == "Lagos"

# Test fuzzy
result = locator.identify("I stay Surulere")
assert result["state"] == "Lagos"
assert result["lga"] == "Surulere"

print("✅ Location tests passed")
```

### Test 2: Working Memory
```python
from app.services.working_memory_enhanced import WorkingMemory, ConversationStage

memory = WorkingMemory(user_phone="+2348012345678")
memory.set_location(state="Lagos", lga="Ikeja")
memory.transition_to(ConversationStage.QUERY_UNDERSTANDING, "location_complete")

assert memory.location["state"] == "Lagos"
assert memory.stage == ConversationStage.QUERY_UNDERSTANDING
assert len(memory.stage_history) == 1

print("✅ Working memory tests passed")
```

### Test 3: Error Recovery
```python
from app.services.error_recovery_enhanced import ErrorRecoveryHandler

response = ErrorRecoveryHandler.ambiguous_location(
    attempted="Surulere",
    suggestions=["Surulere, Lagos", "Surulere, Oyo"]
)

assert "Surulere, Lagos" in response
assert "number (1-2)" in response

print("✅ Error recovery tests passed")
```

## Production Readiness Checklist

- [ ] All syntax tests pass
- [ ] All unit tests pass
- [ ] Manual tests pass
- [ ] Supermemory API key configured
- [ ] Database migration applied
- [ ] Staged deployment plan ready

## Next Steps

1. **Run full test suite** (see above)
2. **Deploy to staging** if tests pass
3. **Test with real WhatsApp** in staging
4. **Deploy to production** with monitoring

---

**Status: ✅ Code ready, tests written, awaiting execution** 🦉
