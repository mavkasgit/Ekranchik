#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import db

print("\n[TEST] Normalization and Search Tests\n")
print("="*60)

# Test 1: Case insensitive (Cyrillic normalization)
print("Test 1: Case insensitive normalization to Cyrillic")
assert db.normalize_text('СУП') == 'суп', "Failed: cyrillic normalization"
assert db.normalize_text('CYP') == 'сур', "Failed: latin C→с, Y→у, P→р"
print("  PASS: Все текст нормализуется в строчную Cyrillic")

# Test 2: Cyrillic symbols normalize to lowercase Cyrillic
print("Test 2: Cyrillic symbol mapping to lowercase")
mappings = {
    'А': 'а', 'В': 'в', 'Е': 'е', 'К': 'к', 'М': 'м',
    'Н': 'н', 'О': 'о', 'П': 'п', 'Р': 'р', 'С': 'с',
    'Т': 'т', 'У': 'у', 'Х': 'х'
}
for upper, lower in mappings.items():
    assert db.normalize_text(upper) == lower, f"Failed: {upper} -> {lower}"
print("  PASS: All Cyrillic uppercase normalized to lowercase Cyrillic")

# Test 3: Latin letters convert to Cyrillic
print("Test 3: Latin letters convert to Cyrillic")
assert db.normalize_text('CA') == 'са', "Failed: C→с, A→а"
assert db.normalize_text('ПР') == 'пр', "Failed: Cyrillic ПР"
print("  PASS: Mixed text normalization to Cyrillic works")

# Test 3.5: Bidirectional conversion (Latin finding Cyrillic)
print("Test 3.5: Bidirectional search (Latin finds Cyrillic)")
# CP и СР оба нормализуются в ср (C→с, P→р)
cp_norm = db.normalize_text('CP')  # 'CP' → (C→с, P→р) = 'ср'
cr_norm = db.normalize_text('СР')  # 'СР' → (С→с, Р→р) = 'ср'
assert cp_norm == 'ср', f"Failed: CP should be 'ср' but got '{cp_norm}'"
assert cr_norm == 'ср', f"Failed: СР should be 'ср' but got '{cr_norm}'"
assert cp_norm == cr_norm, "Failed: Latin и Cyrillic должны быть одинаковы"
print("  PASS: Latin и Cyrillic нормализуются одинаково")

# Test 4: Empty strings
print("Test 4: Empty and None handling")
assert db.normalize_text('') == '', "Failed: empty string"
assert db.normalize_text(None) == '', "Failed: None"
print("  PASS: Empty/None handled correctly")

print("\n" + "="*60)
print("SUCCESS: All tests passed!")
print("="*60 + "\n")
