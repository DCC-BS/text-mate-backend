# Advisor Improvement Plan

## Problem Summary
1. **Wrong ranges**: LLM returns `start`/`end` character offsets — LLMs cannot count characters reliably
2. **Poor violations**: Thinking disabled, bloated output model, generic prompt, no validation

## Changes

### 1. `models/rule_models.py` — New lean models

**Remove:** `RuelValidation` (extends Rule, forces LLM to echo full rule data + guess positions)

**Add:**
- `Violation` — LLM output model (lean): `rule_name`, `reason`, `proposal`, `source` (exact text snippet)
- `ViolationResult` — API response: same fields + backend-computed `start`, `end`

**Update:**
- `RulesValidationResult`: `rules: list[RuelValidation]` → `violations: list[Violation]`
- `RulesValidationContainer`: `rules: list[RuelValidation]` → `violations: list[ViolationResult]`
- Rename `RuelDocumentDescription` → `RuleDocumentDescription` (fix typo)

### 2. `agents/agent_types/advisor_agent.py` — Prompt + config

- **Enable thinking** (`enable_thinking=True`) — complex rule-checking needs reasoning
- **Override `_get_postprocessors`** to return `[]` — `replace_eszett` mutates `source` text, breaking position matching
- **Rewrite prompt** with:
  - Explicit instruction to copy EXACT text snippet for `source`
  - Few-shot examples showing good (minimal snippet) vs bad (whole sentence) reporting
  - Instruction to keep `source` as minimal as possible

### 3. `services/advisor.py` — Position resolution + validation

**New methods:**
- `_resolve_violation(violation, text)` → `ViolationResult | None`
  - Try exact match: `text.find(source)`
  - Try case-insensitive match
  - Try whitespace-normalized match
  - If all fail → discard violation (log warning)
  - Clamp positions to text bounds
- `_is_duplicate(violation, seen)` → bool
  - Same rule_name + overlapping range = duplicate
- `_apply_swiss_spelling(text)` → apply ss/ß to `reason`/`proposal` only (not `source`)

**Update `_check_text_stream`:**
- After each batch, resolve positions for each `Violation`
- Filter out phantom violations (source not found)
- Deduplicate against previous batches
- Group rules by `collection` before batching (related rules together)
- Apply Swiss spelling (ß→ss) to `reason`/`proposal` fields only

### 4. `routers/advisor.py` — No changes needed
SSE serialization uses `model_dump_json()` which adapts automatically.

## API Contract Change
**Before:**
```json
{"rules": [{name, description, file_name, page_number, example, collection, reason, proposal, source, start, end}], "checked": 0, "total": 0}
```

**After:**
```json
{"violations": [{rule_name, reason, proposal, source, start, end}], "checked": 0, "total": 0}
```

Violations no longer carry full rule metadata. Frontend can look up rule details via the rule_name if needed.
