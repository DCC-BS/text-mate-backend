from typing import Any


def get_language_instruction(language: str | None) -> str:
    if language is None or language == "auto":
        return """
        ## WICHTIGE SPRACHREGEL (STRIKT EINHALTEN):
        - Behalte zwingend die Sprache des Ausgangstextes bei (z. B. Deutsch, Englisch, Französisch, Italienisch usw.).
        - Übersetze den Text keinesfalls in eine andere Sprache (insbesondere nicht ins Deutsche), es sei denn, dies wird ausdrücklich verlangt.
        - Setze alle inhaltlichen, stilistischen und formatierenden Anweisungen direkt in der Originalsprache des Ausgangstextes um.
        """
    else:
        return f"Schreibe das Ergebnis ausschliesslich in folgender Sprache: {language}."


def build_agent_metadata(
    component: str,
    *,
    enable_thinking: bool = False,
    output_type: str = "",
    **extra: Any,
) -> dict[str, Any]:
    """Build a static metadata dict recorded on the agent run span by Logfire.

    Keeps metadata consistent across agents: every span carries `component` and
    `enable_thinking`, plus any extra per-agent fields and `output_type`.
    """
    metadata: dict[str, Any] = {"component": component, "enable_thinking": enable_thinking}
    if output_type:
        metadata["output_type"] = output_type
    metadata.update(extra)
    return metadata
