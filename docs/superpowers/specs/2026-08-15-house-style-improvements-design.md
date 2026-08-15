# Canton Basel-Stadt House Style Improvements & Quick Actions Alignment Design

**Date:** 2026-08-15  
**Topic:** Aligning `BASEL_STADT_HOUSE_STYLE` and Quick Action Prompts with `simplify_prompt.py` / `simplify_style.py` learnings  
**Status:** Approved by User  

---

## 1. Context & Motivation

During the simplification pipeline redesign (`docs/simplify_redesign.md`), a comprehensive audit of Zurich guidelines (`RULES_ES`), Federal Chancellery rules (`bundeskanzlei.json`), official authority letter rules (`merkblatt_behoerdenbriefe.json`), and Basel-Stadt conventions was conducted.

This audit resolved key linguistic contradictions and established a unified standard (`SIMPLIFY_STYLE_DE` in `utils/simplify_style.py`) for:
- Swiss typography (French guillemets `« »` instead of `„ “`)
- Exact currency formatting (`Fr. 327.65`, `Fr. 20.–`, currency placed *before* the amount)
- Date formatting (`1. Januar 2022`, spelled-out months)
- Time formatting (`9.25 Uhr`, `14 Uhr`, 24h clock with point separator)
- Telephone number grouping (`044 123 45 67`)
- Large number formatting (`1 000 000` with spaces)
- Strict gendering forms (forbidding `·`, `*`, `:`, `_`, `()`, `/-innen`; using `oder` in singular and `und` in plural)
- Perspective and voice («wir» for the administration, «Sie» for the citizen, no passive evasion)
- Compound word hyphenation (4+ components hyphenated, 2-3 components closed)

Currently, the shared `BASEL_STADT_HOUSE_STYLE` in `utils/house_style.py` is a 39-line partial subset that lacks these codified rules. Furthermore, quick action prompts like `emails.py` and `offical_letter.py` duplicate generic rules while missing standardized formatting guidance.

---

## 2. Goals & Non-Goals

### Goals
1. **Enrich `BASEL_STADT_HOUSE_STYLE`**: Upgrade `utils/house_style.py` with the complete, reconciled Basel-Stadt style rules covering typography, numbers, dates, times, currency, gendering, perspective, abbreviations, and fact preservation.
2. **Deduplicate Quick Action Prompts**: Refactor `EMAIL_PROMPT_TEMPLATE` (`utils/emails.py`) and `OFFICIAL_LETTER_NOTICE` (`utils/offical_letter.py`) to focus strictly on medium-specific structure, removing redundant stylistic prose already handled by the house style.
3. **Structured Prompt Framing**: Ensure prompts in `medium_agent.py` and related quick actions use clear structure (instruction vs input vs house style) and output constraints.
4. **Comprehensive Test Coverage**: Add unit tests verifying that all required house style rules, counter-examples, and formatting constraints are present, consistent, and deduplicated.

### Non-Goals
- Altering the `/simplify` endpoint or `SIMPLIFY_STYLE_DE` (which is already comprehensive and has dedicated tests).
- Re-architecting non-text quick actions.

---

## 3. Detailed Design

### 3.1 `BASEL_STADT_HOUSE_STYLE` (`src/text_mate_backend/utils/house_style.py`)

The upgraded `BASEL_STADT_HOUSE_STYLE` will be structured into 7 core sections:

1. **Ton, Anrede und Haltung**:
   - Direct address with capitalized «Sie», «Ihr», «Ihnen».
   - Institutional perspective: «wir» for the administration, «Sie» for the citizen (avoiding «die Behörde», «es wird beschlossen»).
   - Respectful, helpful, on eye-level. Concrete verb replacements (e.g. «mitteilen» instead of «in Kenntnis setzen»).
2. **Satzbau und Verständlichkeit**:
   - Short, active sentences. One thought per sentence.
   - Positive phrasing. Avoid excessive nominalizations (Substantivierungen).
3. **Geschlechtergerechte Sprache**:
   - Pair forms («Bürgerinnen und Bürger», «die Mitarbeiterin oder der Mitarbeiter») or neutral forms («die Stimmberechtigten»).
   - Strict ban on special characters: no `*`, `:`, `_`, `·`, Binnen-I, `()`, or `/-innen`.
   - Conjunction rules: singular with «oder», plural with «und», never «beziehungsweise».
   - No pair forms in the first part of compounds («Kundendienst»). Consistent order throughout text.
4. **Schweizer Rechtschreibung und Typografie**:
   - Swiss spelling: always «ss», never «ß».
   - Swiss typography: French quotation marks (« ») and single guillemets (‹ ›) for nested quotes; never German quotes („ “).
   - Compound words: 4+ components hyphenated (`Motorfahrzeug-Ausweispflicht`), 2-3 components closed.
   - Abbreviations: Spell out in running text («zum Beispiel» instead of «z. B.»); when used, use proper spacing (`z. B.`, `d. h.`).
   - Single consistent spelling variant throughout the text.
5. **Zahlen, Daten, Zeiten und Beträge**:
   - Numbers: 1–12 in words, 13+ in digits. Numbers 5+ digits grouped with spaces (`1 000 000`, no apostrophes or dots).
   - Percentages & Units: `30%` (no space), `5 t` / `10 m` (with space).
   - Currency: `Fr. 327.65`, `Fr. 20.–` (dash for missing rappen; `Fr.` before the amount; «Franken» in running text without exact digits).
   - Dates: Month spelled out (`1. Januar 2022`). Years 4 digits (`2026`).
   - Times: 24h format with period (`9.25 Uhr`, `14 Uhr`, never `9:25` or `14.00 Uhr`).
   - Phone numbers: `044 123 45 67` (no slashes or brackets).
6. **Anglizismen**:
   - Keep established loanwords («E-Mail», «Computer», «Leasing»). Replace unnecessary ones («Sitzung» instead of «Meeting»). Explain unclear technical terms.
7. **Fakten und Treue**:
   - Preserve all dates, deadlines, names, amounts, conditions, and account/identification numbers (AHV, IBAN) exactly and unchanged. Never hallucinate facts.

---

## 3.2 Medium Prompts Refactoring

#### `src/text_mate_backend/utils/emails.py`
Refactor `EMAIL_PROMPT_TEMPLATE`:
- **Role & Objective**: Digital authority communication; efficient, friendly, easy to scan on screen.
- **Medium Specifics**:
  - Clear subject line stating topic and action required.
  - Screen readability: short paragraphs (2-3 sentences), bullet points for steps/lists.
  - Tone & de-escalation: constructive, solution-oriented, polite.
  - Call to action: clear next steps and attachment references.
- **Output Format**:
  - `Betreff: [Optimierter Betreff]`
  - `Inhalt: [Optimierter E-Mail-Text]`
- **Appended**: `BASEL_STADT_HOUSE_STYLE`.

#### `src/text_mate_backend/utils/offical_letter.py`
Refactor `OFFICIAL_LETTER_NOTICE`:
- **Role & Objective**: Modern, citizen-oriented official letter ("Persönlich, Sachgerecht, Verständlich").
- **Medium Specifics**:
  - Structure: Subject line, formal greeting/salutation, structured body paragraphs, closing formula.
  - Substance: Clear answers to citizen concerns, clear instructions (who does what by when).
- **Output Format**: Clean letter structure without HTML.
- **Appended**: `BASEL_STADT_HOUSE_STYLE`.

#### `src/text_mate_backend/agents/agent_types/quick_actions/medium_agent.py`
- Refactor `MAIL_PROMPT` and `OFFICIAL_LETTER_PROMPT` to cleanly separate system instructions, medium guidelines, and house style.
- Enhance `REPORT_PROMPT` and `PRESENTATION_PROMPT` to also inherit `BASEL_STADT_HOUSE_STYLE` for orthography, gendering, numbers, and active voice.

---

## 4. Testing Strategy

1. **`tests/test_house_style.py`**:
   - Verify presence of all key Basel-Stadt rules (typography, currency, times, dates, phone numbers, gendering, active voice).
   - Test rule-example alignment (no conflicting examples like CHF or German quotes).
   - Verify Eszett constraint (only inside the negation rule).
2. **`tests/test_simplify_prompt.py`**:
   - Ensure existing tests remain fully green.
3. **`tests/test_quick_action_router.py`**:
   - Verify prompt construction and agent execution for all Medium options.
