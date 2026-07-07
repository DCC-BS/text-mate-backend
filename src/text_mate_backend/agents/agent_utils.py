from typing import Any


def get_language_instruction(langauge: str | None):
    if langauge is None or langauge == "auto":
        return "Schreibe das Ergebnis in derselben Sprache wie der Eingabetext."
    else:
        return f"Schreibe das Ergebnis in folgender Sprache: {langauge}."


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
