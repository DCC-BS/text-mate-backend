def get_language_instruction(langauge: str | None):
    if langauge is None or langauge == "auto":
        return "Schreibe das Ergebnis in derselben Sprache wie der Eingabetext."
    else:
        return f"Schreibe das Ergebnis in folgender Sprache: {langauge}."
