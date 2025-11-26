#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import db

print("\n[TEST] Normalization and Search Tests\n")
print("="*60)

# Test 1: Case insensitive
print("Test 1: Case insensitive normalization")
assert db.normalize_text('HELLO') == 'hello', "Failed: lowercase"
assert db.normalize_text('СУП') == 'cyp', "Failed: cyrillic normalization"
assert db.normalize_text('CYP') == 'cyp', "Failed: latin normalization"
print("  PASS: Lowercase and bidirectional conversion works")

# Test 2: Cyrillic symbols
print("Test 2: Cyrillic symbol mapping")
mappings = {
    'С': 'c', 'Р': 'p', 'А': 'a', 'В': 'b', 'Е': 'e', 
    'К': 'k', 'М': 'm', 'Н': 'h', 'О': 'o', 'Т': 't', 'У': 'y', 'Х': 'x'
}
for cyrillic, latin in mappings.items():
    assert db.normalize_text(cyrillic) == latin, f"Failed: {cyrillic} -> {latin}"
print("  PASS: All Cyrillic-to-Latin mappings correct")

# Test 3: Mixed text
print("Test 3: Mixed Cyrillic and Latin text")
assert db.normalize_text('СУП') == 'cyp', "Failed: СУП (mapped symbols)"
assert db.normalize_text('СР') == 'cp', "Failed: СР (both mapped)"
print("  PASS: Mixed text normalization works")

# Test 3.5: Bidirectional conversion (Latin finding Cyrillic)
print("Test 3.5: Bidirectional normalization")
# CP можем найти только по частичному совпадению с СП (обе нормализуются в cp-like значения)
assert db.normalize_text('CA') == 'ca', "Failed: CA (latin to normalized)"
assert db.normalize_text('СА') == 'ca', "Failed: СА (cyrillic to normalized)"
assert db.normalize_text('CA') == db.normalize_text('СА'), "Failed: C↔С normalization"
print("  PASS: Latin and Cyrillic normalize to same value")

# Test 4: Empty strings
print("Test 4: Empty and None handling")
assert db.normalize_text('') == '', "Failed: empty string"
assert db.normalize_text(None) == '', "Failed: None"
print("  PASS: Empty/None handled correctly")

print("\n" + "="*60)
print("SUCCESS: All tests passed!")
print("="*60 + "\n")
