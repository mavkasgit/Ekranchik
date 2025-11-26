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
cyrillic_mappings = {
    'А': 'а', 'В': 'в', 'Е': 'е', 'К': 'к', 'М': 'м',
    'Н': 'н', 'О': 'о', 'П': 'п', 'Р': 'р', 'С': 'с',
    'Т': 'т', 'У': 'у', 'Х': 'х', 'Д': 'д', 'З': 'з', 'Л': 'л'
}
for upper, lower in cyrillic_mappings.items():
    assert db.normalize_text(upper) == lower, f"Failed: {upper} -> {lower}"
print("  PASS: All Cyrillic uppercase normalized to lowercase Cyrillic")

# Test 3: Latin letters convert to Cyrillic
print("Test 3: Latin letters convert to Cyrillic")
latin_mappings = {
    'A': 'а', 'B': 'в', 'C': 'с', 'D': 'д', 'E': 'е',
    'H': 'н', 'K': 'к', 'M': 'м', 'O': 'о', 'P': 'р',
    'T': 'т', 'X': 'х', 'Y': 'у', 'Z': 'з', 'L': 'л'
}
for latin, cyrillic in latin_mappings.items():
    assert db.normalize_text(latin) == cyrillic, f"Failed: {latin} -> {cyrillic}"
assert db.normalize_text('CA') == 'са', "Failed: CA mixed"
assert db.normalize_text('ПР') == 'пр', "Failed: Cyrillic ПР"
print("  PASS: All Latin letters convert to Cyrillic correctly")

# Test 3.5: Bidirectional conversion (Latin finding Cyrillic)
print("Test 3.5: Bidirectional search (Latin finds Cyrillic)")
# CP и СР оба нормализуются в ср (C→с, P→р)
cp_norm = db.normalize_text('CP')  # 'CP' → (C→с, P→р) = 'ср'
cr_norm = db.normalize_text('СР')  # 'СР' → (С→с, Р→р) = 'ср'
assert cp_norm == 'ср', f"Failed: CP should be 'ср' but got '{cp_norm}'"
assert cr_norm == 'ср', f"Failed: СР should be 'ср' but got '{cr_norm}'"
assert cp_norm == cr_norm, "Failed: Latin и Cyrillic должны быть одинаковы"
print("  PASS: Latin и Cyrillic нормализуются одинаково")

# Test 4: Lowercase Latin letters also convert
print("Test 4: Lowercase Latin letters convert to Cyrillic")
lowercase_mappings = {
    'a': 'а', 'b': 'в', 'c': 'с', 'd': 'д', 'e': 'е',
    'h': 'н', 'k': 'к', 'm': 'м', 'o': 'о', 'p': 'р',
    't': 'т', 'x': 'х', 'y': 'у', 'z': 'з', 'l': 'л'
}
for latin, cyrillic in lowercase_mappings.items():
    assert db.normalize_text(latin) == cyrillic, f"Failed: {latin} -> {cyrillic}"
assert db.normalize_text('maldez') == 'малдез', "Failed: mixed lowercase"
print("  PASS: All lowercase Latin letters convert to Cyrillic")

# Test 5: Empty strings
print("Test 5: Empty and None handling")
assert db.normalize_text('') == '', "Failed: empty string"
assert db.normalize_text(None) == '', "Failed: None"
print("  PASS: Empty/None handled correctly")

print("\n" + "="*60)
print("SUCCESS: All tests passed!")
print("="*60 + "\n")
