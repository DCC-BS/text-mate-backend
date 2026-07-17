import asyncio
import json
import re
from collections.abc import Iterator
from difflib import SequenceMatcher
from pathlib import Path
from typing import cast, final

from dcc_backend_common.logger import get_logger
from fastapi_azure_auth.user import User
from typing_extensions import AsyncIterator

from text_mate_backend.agents.agent_types.proposal_agent import ProposalAgent
from text_mate_backend.agents.agent_types.violation_detection_agent import ViolationDetectionAgent
from text_mate_backend.models.error_codes import CHECK_TEXT_ERROR, LOADING_FILES_ERROR
from text_mate_backend.models.error_response import ApiErrorException
from text_mate_backend.models.rule_models import (
    DetectionResult,
    DetectionViolation,
    ProposalRequest,
    ResolvedDetection,
    Rule,
    RuleDocumentDescription,
    RulesContainer,
    RulesValidationContainer,
    ViolationRange,
    ViolationResult,
)
from text_mate_backend.utils.configuration import Configuration

logger = get_logger("advisor_service")
MAX_RULES_PER_REQUEST = 5
MAX_RULES = 60
DETECTION_TIMEOUT_SECONDS = 300
PROPOSAL_TIMEOUT_SECONDS = 60
BATCH_TIMEOUT_SECONDS = 200
FUZZY_MATCH_THRESHOLD = 0.85


@final
class AdvisorService:
    def __init__(self, config: Configuration) -> None:
        logger.debug("Initializing AdvisorService")

        self.config = config
        self.rule_container = self._merge_rules_files(Path("assets/docs/rules"))
        self.doc_descriptions = self._merge_meta_files(Path("assets/docs/meta"))
        self.detection_agent = ViolationDetectionAgent(config)
        self.proposal_agent = ProposalAgent(config)

    def _merge_rules_files(self, directory: Path) -> RulesContainer:
        """
        Merge all rules JSON files from the specified directory.
        Each file must be a valid RulesContainer with a 'rules' key.
        """
        if not directory.exists() or not directory.is_dir():
            logger.error("Rules directory not found", directory=str(directory))
            raise ApiErrorException(
                {
                    "status": 500,
                    "errorId": LOADING_FILES_ERROR,
                    "debugMessage": f"Rules directory not found: {directory}",
                }
            )

        all_rules: list[Rule] = []
        json_files = sorted(directory.glob("*.json"))

        if not json_files:
            logger.warning("No JSON files found in rules directory", directory=str(directory))
            return RulesContainer(rules=[])

        logger.debug("Loading rules files", file_count=len(json_files), directory=str(directory))

        for json_file in json_files:
            try:
                container = RulesContainer.model_validate_json(json_file.read_text())
                all_rules.extend(container.rules)
                logger.debug("Loaded rules from file", rule_count=len(container.rules), file=json_file.name)
            except Exception as e:
                logger.exception("Error loading rules file", file=str(json_file))
                raise ApiErrorException(
                    {
                        "status": 500,
                        "errorId": LOADING_FILES_ERROR,
                        "debugMessage": f"Error loading rules from {json_file}: {str(e)}",
                    }
                ) from e

        logger.debug("Total rules loaded", rule_count=len(all_rules))
        return RulesContainer(rules=all_rules)

    def _merge_meta_files(self, directory: Path) -> list[RuleDocumentDescription]:
        """
        Merge all meta JSON files from the specified directory.
        Each file must be a JSON array of RuleDocumentDescription objects.
        Raises an error if duplicate file names are found.
        """
        if not directory.exists() or not directory.is_dir():
            logger.error("Meta directory not found", directory=str(directory))
            raise ApiErrorException(
                {
                    "status": 500,
                    "errorId": LOADING_FILES_ERROR,
                    "debugMessage": f"Meta directory not found: {directory}",
                }
            )

        all_descriptions: list[RuleDocumentDescription] = []
        seen_files: set[str] = set()
        json_files = sorted(directory.glob("*.json"))

        if not json_files:
            logger.warning("No JSON files found in meta directory", directory=str(directory))
            return []

        logger.debug("Loading meta files", file_count=len(json_files), directory=str(directory))

        for json_file in json_files:
            try:
                json_data = cast(list[dict[str, object]], json.loads(json_file.read_text()))
                descriptions: list[RuleDocumentDescription] = [
                    RuleDocumentDescription.model_validate(doc) for doc in json_data
                ]

                for doc in descriptions:
                    if doc.id in seen_files:
                        logger.error("Duplicate document file found", doc_id=doc.id, file=json_file.name)
                        raise ApiErrorException(
                            {
                                "status": 500,
                                "errorId": LOADING_FILES_ERROR,
                                "debugMessage": f"Duplicate document file found: {doc.id}",
                            }
                        )
                    seen_files.add(doc.id)

                all_descriptions.extend(descriptions)
                logger.debug(
                    "Loaded document descriptions from file", description_count=len(descriptions), file=json_file.name
                )
            except ApiErrorException:
                raise
            except Exception as e:
                logger.exception("Error loading meta file", file=str(json_file))
                raise ApiErrorException(
                    {
                        "status": 500,
                        "errorId": LOADING_FILES_ERROR,
                        "debugMessage": f"Error loading meta from {json_file}: {str(e)}",
                    }
                ) from e

        logger.debug("Total document descriptions loaded", description_count=len(all_descriptions))
        return all_descriptions

    def get_docs(self, user: User | None) -> list[RuleDocumentDescription]:
        """
        Returns the documentation file names available for the advisor service.
        """
        doc_descriptions = list(filter(lambda doc: self._has_access(user, doc), self.doc_descriptions))

        doc_names = self.rule_container.document_names

        return list(
            filter(
                lambda doc: doc.id in doc_names,
                doc_descriptions,
            )
        )

    def filter_rules(self, docs: set[str]) -> list[Rule]:
        filtered_rules: list[Rule] = []
        for doc in docs:
            doc_rules = [rule for rule in self.rule_container.rules if rule.collection == doc]
            filtered_rules.extend(doc_rules)
        return filtered_rules

    async def check_text_stream(self, text: str, docs: set[str]) -> AsyncIterator[RulesValidationContainer]:
        """
        Checks the text for any violations of the rules and yields validation results
        batch-by-batch. This is intended for streaming (SSE) responses.
        """

        if len(docs) > 5:
            raise ApiErrorException(
                {
                    "status": 400,
                    "errorId": CHECK_TEXT_ERROR,
                    "debugMessage": "A maximum of 5 documents can be selected",
                }
            )

        try:
            async for result in self._check_text_stream(text, docs):
                yield result
        except asyncio.CancelledError:
            logger.info("check_text_stream cancelled (client disconnect)")
            raise
        except Exception as e:
            logger.exception("Error checking text (stream)")
            raise ApiErrorException(
                {
                    "status": 500,
                    "errorId": CHECK_TEXT_ERROR,
                    "debugMessage": str(e),
                }
            ) from e

    def _has_access(self, user: User | None, doc: RuleDocumentDescription) -> bool:
        if "all" in doc.access:
            return True

        if user is None:
            if self.config.disable_auth:
                return True
            else:
                raise ValueError("User is none when authentification is expected")

        for roles in user.roles:
            for access in doc.access:
                if roles == access:
                    return True

        return False

    async def _check_text_stream(self, text: str, docs: set[str]) -> AsyncIterator[RulesValidationContainer]:
        rules = self.filter_rules(docs)

        if not rules:
            logger.warning("No rules found for the selected documents", docs=list(docs))
            # Maintain parity with the non-streaming API by yielding a single empty container
            yield RulesValidationContainer(violations=[], checked=0, total=0)
            return

        total_rules = len(rules)
        rule_lookup: dict[str, Rule] = {rule.name: rule for rule in rules}

        batches = list(self._batched_rules(rules, MAX_RULES_PER_REQUEST, max_rules=len(rules)))

        # Run all batches concurrently. Each batch carries its own per-batch
        # dedup state (see _process_batch), so there is no shared mutable state
        # between them. The wrapper folds timeouts/errors into an empty result
        # while returning the batch's rule count, so as_completed consumers can
        # update progress without needing to map futures back to batches.
        async def run_batch(batch: list[Rule]) -> tuple[int, list[ViolationResult]]:
            batch_size = len(batch)
            try:
                result = await asyncio.wait_for(
                    self._process_batch(text, batch, rule_lookup),
                    timeout=BATCH_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                logger.error(f"Batch timed out after {BATCH_TIMEOUT_SECONDS}s, batch_size={batch_size}")
                result = []
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Batch failed: {e}")
                result = []
            return batch_size, result

        tasks = [asyncio.ensure_future(run_batch(batch)) for batch in batches]

        try:
            checked_rules = 0
            for completed in asyncio.as_completed(tasks):
                batch_size, new_violations = await completed
                checked_rules += batch_size
                yield RulesValidationContainer(
                    violations=new_violations,
                    checked=checked_rules,
                    total=total_rules,
                )
        finally:
            # If the consumer stops iterating (client disconnect → CancelledError),
            # cancel any still-running batches so in-flight LLM calls don't keep
            # running (and costing) after nobody is listening.
            for task in tasks:
                if not task.done():
                    task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    def _resolve_and_dedup(
        self,
        violations: list[DetectionViolation],
        text: str,
        rule_lookup: dict[str, Rule],
    ) -> list[ResolvedDetection]:
        """Resolve detection snippets to character positions and drop duplicates.

        Repeated identical snippets are tracked per rule via consumed offsets so
        that the second occurrence resolves to a distinct position instead of
        being collapsed onto the first (and then dropped as a duplicate).
        """
        survivors: list[ResolvedDetection] = []
        consumed_by_rule: dict[str, list[tuple[int, int]]] = {}
        for violation in violations:
            consumed = consumed_by_rule.get(violation.rule_name)
            resolved = self._resolve_detection(violation, text, rule_lookup, consumed_ranges=consumed)
            if resolved is None:
                continue
            if self._is_duplicate(resolved, survivors):
                continue
            survivors.append(resolved)
            consumed_by_rule.setdefault(violation.rule_name, []).append((resolved.range.start, resolved.range.end))
        return survivors

    async def _process_batch(
        self,
        text: str,
        rule_batch: list[Rule],
        rule_lookup: dict[str, Rule],
    ) -> list[ViolationResult]:
        """Run step 1 (detection) then step 2 (parallel proposals) for one rule batch.

        Dedup is intentionally local to this batch: rule names are globally unique,
        so the cross-batch dedup performed previously never triggered. Keeping it
        per-batch removes shared mutable state and makes batches safe to run in
        parallel.
        """

        # --- Step 1: detection -------------------------------------------------
        try:
            detection_result: DetectionResult = await asyncio.wait_for(
                self.detection_agent.run(text, deps=RulesContainer(rules=rule_batch)),
                timeout=DETECTION_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.error(f"Detection timed out after {DETECTION_TIMEOUT_SECONDS}s")
            return []

        # Resolve positions + dedup before requesting proposals (skip wasted calls).
        survivors = self._resolve_and_dedup(detection_result.violations, text, rule_lookup)

        if not survivors:
            return []

        # --- Step 2: parallel proposal generation ------------------------------
        proposal_tasks = [
            asyncio.wait_for(
                self.proposal_agent.run(None, deps=self._build_proposal_request(text, resolved, rule_lookup)),
                timeout=PROPOSAL_TIMEOUT_SECONDS,
            )
            for resolved in survivors
        ]
        proposals = await asyncio.gather(*proposal_tasks, return_exceptions=True)

        results: list[ViolationResult] = []
        for resolved, proposal in zip(survivors, proposals, strict=True):
            if isinstance(proposal, BaseException):
                logger.error(
                    f"Proposal generation failed for rule '{resolved.rule_name}' "
                    f"at [{resolved.range.start}:{resolved.range.end}]: {proposal}. Dropping violation."
                )
                continue
            results.append(self._build_violation_result(resolved, proposal, text))
        return results

    def _build_proposal_request(
        self, text: str, resolved: ResolvedDetection, rule_lookup: dict[str, Rule]
    ) -> ProposalRequest:
        rule = rule_lookup.get(resolved.rule_name)
        if rule is None:
            rule = Rule(
                name=resolved.rule_name,
                description="",
                file_name=resolved.file_name,
                page_number=resolved.page_number,
                example="",
                collection=resolved.collection,
            )
        return ProposalRequest(
            rule=rule,
            source=resolved.source,
            reason=resolved.reason,
            context_sentence=self._surrounding_sentence(text, resolved.range),
        )

    def _surrounding_sentence(self, text: str, range_: ViolationRange) -> str:
        """Return the sentence/segment unit that contains the violating range."""
        units = self._split_into_search_units(text)
        for unit_text, unit_start in units:
            unit_end = unit_start + len(unit_text)
            if unit_start <= range_.start < unit_end:
                return unit_text
        # Fallback: widen around the range.
        start = max(0, range_.start - 80)
        end = min(len(text), range_.end + 80)
        return text[start:end]

    def _resolve_detection(
        self,
        violation: DetectionViolation,
        text: str,
        rule_lookup: dict[str, Rule],
        consumed_ranges: list[tuple[int, int]] | None = None,
    ) -> ResolvedDetection | None:
        """Resolve a detection's source snippet to character positions in the original text."""
        source = violation.source.strip()
        if not source or len(source) < 1:
            logger.warn(f"Empty source for violation: {violation.rule_name}")
            return None

        found = self._find_source(source, text, consumed=consumed_ranges)
        if found is None:
            logger.warn(f"Could not locate source in text: '{source[:80]}' (rule: {violation.rule_name})")
            return None
        pos, match_len = found

        end = min(pos + match_len, len(text))

        rule = rule_lookup.get(violation.rule_name)

        return ResolvedDetection(
            rule_name=violation.rule_name,
            reason=self._to_swiss_german(violation.reason),
            source=text[pos:end],
            range=ViolationRange(start=pos, end=end),
            file_name=rule.file_name if rule else "",
            page_number=rule.page_number if rule else 0,
            collection=rule.collection if rule else "",
        )

    def _build_violation_result(self, resolved: ResolvedDetection, proposal: str, text: str) -> ViolationResult:
        # API boundary: the frontend is JavaScript, which indexes strings by
        # UTF-16 code units. All internal work (resolution, dedup, slicing) runs
        # on Python code points, so we translate the range to UTF-16 here, on the
        # way out. See ``_to_utf16_offset`` for the rationale.
        return ViolationResult(
            rule_name=resolved.rule_name,
            reason=resolved.reason,
            proposal=self._to_swiss_german(proposal),
            source=resolved.source,
            file_name=resolved.file_name,
            page_number=resolved.page_number,
            range=ViolationRange(
                start=self._to_utf16_offset(text, resolved.range.start),
                end=self._to_utf16_offset(text, resolved.range.end),
            ),
            collection=resolved.collection,
        )

    @staticmethod
    def _to_utf16_offset(text: str, codepoint_offset: int) -> int:
        """Translate a Python code-point index into a JavaScript UTF-16 code-unit index.

        Python ``str`` is a sequence of Unicode code points; ``str.find`` /
        slicing / regex offsets are therefore code-point based. JavaScript, by
        contrast, stores strings as UTF-16 and indexes them by **code unit**.
        The two indexing schemes agree for every Basic Multilingual Plane (BMP)
        character — that covers all of Latin, umlauts, ``ß``, accented letters,
        Cyrillic, CJK, etc. They diverge only for code points >= U+10000
        (supplementary plane: emoji, some symbols, historic scripts), which are
        a single Python code point but two UTF-16 code units (a surrogate pair).

        For each character before ``codepoint_offset`` we add 2 when it lies
        outside the BMP and 1 otherwise, yielding the offset a JS consumer would
        compute. This keeps UTF-16 translation at the API boundary only; all
        internal resolution logic continues to operate on code points.
        """
        return sum(2 if ord(ch) >= 0x10000 else 1 for ch in text[:codepoint_offset])

    def _find_source(
        self, source: str, text: str, consumed: list[tuple[int, int]] | None = None
    ) -> tuple[int, int] | None:
        """Try to locate source in text. Returns (position, length) or None.

        All offsets here are **Python code points** (the native ``str`` indexing
        unit), not UTF-8 bytes and not UTF-16 code units. This is deliberate:
        the result feeds back into Python slicing (``text[pos:end]``), regex
        offsets, dedup and the ``consumed`` loop, which all operate on code
        points. Translation to JavaScript UTF-16 code-unit indices happens once,
        at the API boundary, in ``_build_violation_result``.

        When ``consumed`` ranges are given, the first match that does not overlap
        any consumed range is returned. This lets repeated identical snippets
        resolve to distinct occurrences instead of all collapsing onto the first
        (which would then be dropped as a duplicate by ``_is_duplicate``).
        """
        if not consumed:
            return self._find_source_first(source, text, 0)

        min_start = 0
        last_pos = -1
        while True:
            found = self._find_source_first(source, text, min_start)
            if found is None:
                return None
            pos, match_len = found
            if not self._overlaps_any((pos, pos + match_len), consumed):
                return found
            # Match overlaps an already-consumed span: advance and look for the next.
            if pos <= last_pos:
                # No progress possible (normalized/fuzzy paths ignore ``start``);
                # return the best we have rather than loop forever.
                return found
            last_pos = pos
            min_start = pos + 1

    def _find_source_first(self, source: str, text: str, start: int = 0) -> tuple[int, int] | None:
        """Single-pass search cascade from a minimum start offset.

        The exact and case-insensitive paths honour ``start``; the normalized and
        fuzzy fallbacks do not (they are rare edge cases) and return the first
        match instead.
        """
        pos = text.find(source, start)
        if pos != -1:
            return pos, len(source)

        lower_text = text.lower()
        lower_source = source.lower()
        pos = lower_text.find(lower_source, start)
        if pos != -1:
            return pos, len(source)

        normalized_text = self._normalize_whitespace(text)
        normalized_source = self._normalize_whitespace(source)
        pos = normalized_text.find(normalized_source)
        if pos != -1:
            orig_start = self._map_normalized_to_original(text, normalized_text, pos)
            if orig_start is not None:
                # Map the end of the normalized match back to original coords so
                # collapsed-whitespace runs are reflected in the span length. Only
                # apply the corrected length when it is at least as long as the
                # (possibly whitespace-rich) source; otherwise fall back to be safe.
                orig_end = self._map_normalized_to_original(text, normalized_text, pos + len(normalized_source))
                if orig_end is not None and orig_end - orig_start >= len(source):
                    return orig_start, orig_end - orig_start
                return orig_start, len(source)

        return self._fuzzy_find(source, text)

    @staticmethod
    def _overlaps_any(rng: tuple[int, int], ranges: list[tuple[int, int]]) -> bool:
        for r in ranges:
            if min(rng[1], r[1]) > max(rng[0], r[0]):
                return True
        return False

    def _normalize_whitespace(self, text: str) -> str:
        return re.sub(r"\s+", " ", text)

    def _map_normalized_to_original(self, original: str, normalized: str, norm_pos: int) -> int | None:
        """Map a position in whitespace-normalized text back to the original text.

        Whitespace normalization collapses each run of whitespace to a single
        space, so one normalized space corresponds to a run of 1+ whitespace chars
        in the original. This walks both in lockstep, consuming whole original
        whitespace runs so the mapping is correct even across collapsed runs.
        """
        orig_pos = 0
        norm_idx = 0
        while norm_idx < norm_pos and orig_pos < len(original):
            if normalized[norm_idx] == original[orig_pos] and not original[orig_pos].isspace():
                norm_idx += 1
                orig_pos += 1
            elif normalized[norm_idx].isspace() and original[orig_pos].isspace():
                norm_idx += 1
                orig_pos += 1
                # Consume the remainder of this original whitespace run.
                while orig_pos < len(original) and original[orig_pos].isspace():
                    orig_pos += 1
            else:
                return None
        return orig_pos if norm_idx == norm_pos else None

    def _fuzzy_find(self, needle: str, haystack: str) -> tuple[int, int] | None:
        """Find the best fuzzy match for needle in haystack."""
        if len(needle) < 2:
            return None

        best_ratio = 0.0
        best_pos = -1
        best_len = len(needle)

        candidates = self._split_into_search_units(haystack)

        for candidate_text, candidate_start in candidates:
            if len(candidate_text) < 2:
                continue

            search_window = candidate_text
            if len(needle) < len(candidate_text):
                window_start = max(0, candidate_text.lower().find(needle[:5].lower()))
                window = max(len(needle), 10)
                search_window = candidate_text[max(0, window_start - 5) : window_start + window + 10]
                offset = max(0, window_start - 5)
            else:
                offset = 0

            ratio = SequenceMatcher(None, needle.lower(), search_window.lower()).find_longest_match(
                0, len(needle), 0, len(search_window)
            )
            if ratio.size > 0:
                matched_text = needle[ratio.a : ratio.a + ratio.size]
                full_ratio = SequenceMatcher(None, needle.lower(), matched_text.lower()).ratio()
                if full_ratio > best_ratio:
                    best_ratio = full_ratio
                    best_pos = candidate_start + offset + ratio.b
                    best_len = max(ratio.size, len(needle) // 2)

        if best_ratio >= FUZZY_MATCH_THRESHOLD and best_pos >= 0:
            return best_pos, best_len

        return None

    def _split_into_search_units(self, text: str) -> list[tuple[str, int]]:
        """Split text into sentences/segments with their character offsets."""
        units: list[tuple[str, int]] = []
        for match in re.finditer(r"[^.!?\n]+[.!?\n]?", text):
            units.append((match.group(), match.start()))
        if not units and text:
            units.append((text, 0))
        return units

    def _is_duplicate(self, detection: ResolvedDetection, seen: list[ResolvedDetection]) -> bool:
        """Check if a detection duplicates an already-seen one."""
        for s in seen:
            if s.rule_name != detection.rule_name:
                continue
            overlap = min(s.range.end, detection.range.end) - max(s.range.start, detection.range.start)
            if overlap > 0:
                return True
            if s.range.start == detection.range.start:
                return True
        return False

    def _to_swiss_german(self, text: str) -> str:
        """Replace ß with ss for Swiss German convention."""
        return text.replace("ß", "ss")

    def _batched_rules(self, rules: list[Rule], batch_size: int, max_rules: int = MAX_RULES) -> Iterator[list[Rule]]:
        sorted_rules = sorted(rules, key=lambda r: r.collection)
        for i in range(0, min(len(sorted_rules), max_rules), batch_size):
            yield sorted_rules[i : i + batch_size]
