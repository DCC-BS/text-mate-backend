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

from text_mate_backend.agents.agent_types.advisor_agent import AdvisorAgent
from text_mate_backend.models.error_codes import CHECK_TEXT_ERROR, LOADING_FILES_ERROR
from text_mate_backend.models.error_response import ApiErrorException
from text_mate_backend.models.rule_models import (
    Rule,
    RuleDocumentDescription,
    RulesContainer,
    RulesValidationContainer,
    Violation,
    ViolationResult,
)
from text_mate_backend.utils.configuration import Configuration

logger = get_logger("advisor_service")
MAX_RULES_PER_REQUEST = 5
MAX_RULES = 60
AGENT_TIMEOUT_SECONDS = 60
FUZZY_MATCH_THRESHOLD = 0.85


@final
class AdvisorService:
    def __init__(self, config: Configuration) -> None:
        logger.info("Initializing AdvisorService")

        self.config = config
        self.rule_container = self._merge_rules_files(Path("assets/docs/rules"))
        self.agent = AdvisorAgent(config)

    def _merge_rules_files(self, directory: Path) -> RulesContainer:
        """
        Merge all rules JSON files from the specified directory.
        Each file must be a valid RulesContainer with a 'rules' key.
        """
        if not directory.exists() or not directory.is_dir():
            logger.error(f"Rules directory not found: {directory}")
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
            logger.warn(f"No JSON files found in rules directory: {directory}")
            return RulesContainer(rules=[])

        logger.info(f"Loading {len(json_files)} rules files from {directory}")

        for json_file in json_files:
            try:
                container = RulesContainer.model_validate_json(json_file.read_text())
                all_rules.extend(container.rules)
                logger.info(f"Loaded {len(container.rules)} rules from {json_file.name}")
            except Exception as e:
                logger.error(f"Error loading rules from {json_file}: {e}")
                raise ApiErrorException(
                    {
                        "status": 500,
                        "errorId": LOADING_FILES_ERROR,
                        "debugMessage": f"Error loading rules from {json_file}: {str(e)}",
                    }
                ) from e

        logger.info(f"Total rules loaded: {len(all_rules)}")
        return RulesContainer(rules=all_rules)

    def _merge_meta_files(self, directory: Path) -> list[RuleDocumentDescription]:
        """
        Merge all meta JSON files from the specified directory.
        Each file must be a JSON array of RuleDocumentDescription objects.
        Raises an error if duplicate file names are found.
        """
        if not directory.exists() or not directory.is_dir():
            logger.error(f"Meta directory not found: {directory}")
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
            logger.warn(f"No JSON files found in meta directory: {directory}")
            return []

        logger.info(f"Loading {len(json_files)} meta files from {directory}")

        for json_file in json_files:
            try:
                json_data = cast(list[dict[str, object]], json.loads(json_file.read_text()))
                descriptions: list[RuleDocumentDescription] = [
                    RuleDocumentDescription.model_validate(doc) for doc in json_data
                ]

                for doc in descriptions:
                    if doc.id in seen_files:
                        logger.error(f"Duplicate file found: {doc.id} in {json_file.name}")
                        raise ApiErrorException(
                            {
                                "status": 500,
                                "errorId": LOADING_FILES_ERROR,
                                "debugMessage": f"Duplicate document file found: {doc.id}",
                            }
                        )
                    seen_files.add(doc.id)

                all_descriptions.extend(descriptions)
                logger.info(f"Loaded {len(descriptions)} document descriptions from {json_file.name}")
            except Exception as e:
                logger.error(f"Error loading meta from {json_file}: {e}")
                raise ApiErrorException(
                    {
                        "status": 500,
                        "errorId": LOADING_FILES_ERROR,
                        "debugMessage": f"Error loading meta from {json_file}: {str(e)}",
                    }
                ) from e

        logger.info(f"Total document descriptions loaded: {len(all_descriptions)}")
        return all_descriptions

    def get_docs(self, user: User | None) -> list[RuleDocumentDescription]:
        """
        Returns the documentation file names available for the advisor service.
        """
        doc_descriptions = self._merge_meta_files(Path("assets/docs/meta"))

        doc_descriptions = list(filter(lambda doc: self._has_access(user, doc), doc_descriptions))

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
            logger.error(f"Error checking text (stream): {e}")
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
            logger.warn(f"No rules found for the documents {docs}")
            yield RulesValidationContainer(violations=[], checked=0, total=0)
            return

        total_rules = len(rules)
        checked_rules = 0
        seen_violations: list[ViolationResult] = []
        rule_lookup: dict[str, Rule] = {rule.name: rule for rule in rules}

        for rule_batch in self._batched_rules(rules, MAX_RULES_PER_REQUEST, max_rules=len(rules)):
            try:
                validation_result = await asyncio.wait_for(
                    self.agent.run(text, deps=RulesContainer(rules=rule_batch)),
                    timeout=AGENT_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                logger.error(
                    f"Agent timed out after {AGENT_TIMEOUT_SECONDS}s, checked {checked_rules}/{total_rules} rules"
                )
                break
            checked_rules += len(rule_batch)

            new_violations: list[ViolationResult] = []
            for violation in validation_result.violations:
                resolved = self._resolve_violation(violation, text, rule_lookup)
                if resolved is None:
                    continue
                if self._is_duplicate(resolved, seen_violations):
                    continue
                new_violations.append(resolved)
                seen_violations.append(resolved)

            yield RulesValidationContainer(
                violations=new_violations,
                checked=checked_rules,
                total=total_rules,
            )

    def _resolve_violation(
        self, violation: Violation, text: str, rule_lookup: dict[str, Rule]
    ) -> ViolationResult | None:
        """Resolve a violation's source snippet to character positions in the original text."""
        source = violation.source.strip()
        if not source or len(source) < 1:
            logger.warn(f"Empty source for violation: {violation.rule_name}")
            return None

        found = self._find_source(source, text)
        if found is None:
            logger.warn(f"Could not locate source in text: '{source[:80]}' (rule: {violation.rule_name})")
            return None
        pos, match_len = found

        end = min(pos + match_len, len(text))

        rule = rule_lookup.get(violation.rule_name)

        return ViolationResult(
            rule_name=violation.rule_name,
            reason=self._to_swiss_german(violation.reason),
            proposal=self._to_swiss_german(violation.proposal),
            source=text[pos:end],
            file_name=rule.file_name if rule else "",
            page_number=rule.page_number if rule else 0,
            start=pos,
            end=end,
        )

    def _find_source(self, source: str, text: str) -> tuple[int, int] | None:
        """Try to locate source in text. Returns (position, length) or None."""
        pos = text.find(source)
        if pos != -1:
            return pos, len(source)

        lower_text = text.lower()
        lower_source = source.lower()
        pos = lower_text.find(lower_source)
        if pos != -1:
            return pos, len(source)

        normalized_text = self._normalize_whitespace(text)
        normalized_source = self._normalize_whitespace(source)
        pos = normalized_text.find(normalized_source)
        if pos != -1:
            orig_pos = self._map_normalized_to_original(text, normalized_text, pos)
            if orig_pos is not None:
                return orig_pos, len(source)

        return self._fuzzy_find(source, text)

    def _normalize_whitespace(self, text: str) -> str:
        return re.sub(r"\s+", " ", text)

    def _map_normalized_to_original(self, original: str, normalized: str, norm_pos: int) -> int | None:
        orig_pos = 0
        norm_idx = 0
        while norm_idx < norm_pos and orig_pos < len(original):
            if normalized[norm_idx] == original[orig_pos]:
                norm_idx += 1
                orig_pos += 1
            elif normalized[norm_idx] == " " and original[orig_pos].isspace():
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

    def _is_duplicate(self, violation: ViolationResult, seen: list[ViolationResult]) -> bool:
        """Check if a violation duplicates an already-seen one."""
        for s in seen:
            if s.rule_name != violation.rule_name:
                continue
            overlap = min(s.end, violation.end) - max(s.start, violation.start)
            if overlap > 0:
                return True
            if s.start == violation.start:
                return True
        return False

    def _to_swiss_german(self, text: str) -> str:
        """Replace ß with ss for Swiss German convention."""
        return text.replace("ß", "ss")

    def _batched_rules(self, rules: list[Rule], batch_size: int, max_rules: int = MAX_RULES) -> Iterator[list[Rule]]:
        sorted_rules = sorted(rules, key=lambda r: r.collection)
        for i in range(0, min(len(sorted_rules), max_rules), batch_size):
            yield sorted_rules[i : i + batch_size]
