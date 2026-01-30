def get_language_instruction(langauge: str | None):
    if langauge is None or langauge == "auto":
        return "The text should be written in a same language as a input text."
    else:
        return f"the text should be written in {langauge}"
