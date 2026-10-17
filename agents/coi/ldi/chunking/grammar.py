from __future__ import annotations

import re

# ==============================================================================
# REGEX GRAMMAR (STRUCTURE + TABLES)
# ==============================================================================

# HIERARCHY PATTERNS
# These regexes define the "skeleton" of the document.
ARTICLE_RE = re.compile(r"^ARTICLE[\s\-–—]*([0-9IVXLCDM]+)", re.I)
ANNEX_RE = re.compile(r"^(Annexure|Appendix|Schedule)[\s\-–—]*([A-Za-z0-9]*)", re.I)
MAIN_RE = re.compile(r"^(\d+(?:\.\d+)*)[\.\)]?\s+(.*)")

# Require an explicit bullet marker (')' or '.') so normal sentences like
# "a minimum of ..." don't get misclassified as subclauses.
ALPHA_RE = re.compile(r"^\(?([a-z])[\)\.]\s+(.*)", re.I)
ROMAN_RE = re.compile(r"^\(?([ivxlcdm]+)[\)\.]\s+(.*)", re.I)

# Numeric bullets inside subclauses (e.g., 1) Labor ... under a lettered item)
# Important: require a closing ')' so we don't misclassify top-level clauses like
# '3. Compensation and Benefits' as a nested bullet.
SUBNUM_RE = re.compile(r"^\(?([0-9]+)\)\s+(.*)")

# Definitions (e.g., "Effective Date" means ...)
DEFINITION_RE = re.compile(r'^"([^"]+)"\s+(means|shall mean|refers to)', re.I)

# GENERIC TABLE DETECTION
# Matches lines containing tabs OR sequences of 3+ spaces.
# Why 3 spaces? It's a common heuristic for visually aligned columns in plain text.
TABLE_SPLIT_RE = re.compile(r"\t+|\s{3,}")
