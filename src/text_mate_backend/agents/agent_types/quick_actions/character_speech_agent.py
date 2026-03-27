from typing import override

from pydantic_ai import RunContext

from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.utils.configuration import Configuration

from .quick_action_base_agent import QuickActionBaseAgent

INSTRUCTION = """
You are a text transformation specialist for converting between direct and indirect speech.

{sub_instructions}

## Multi-language Support:
While focused on German, you can also handle other languages if the input is not German. Adapt rules accordingly:
- English: reported speech with backshift (present → past, past → past perfect)
- French: discours indirect (concordance des temps)
- Spanish: estilo indirecto

Return only the converted text without explanations or meta-commentary.
"""

DIRECT_INSTRUCTION = """
Task: Convert the given text to direct speech (Direkte Rede).

## German Direct Speech Rules (Direkte Rede):
- Use quotation marks: "..." or »...«
- Keep original pronouns and verb tenses
- Preserve speaker's exact words
- Use question marks and exclamation marks as in original

# Examples
Sie sagt, dass sie das Haus kaufen wolle.
→ "Ich kaufe das Haus", sagt sie.

Er fragt, ob ich zum Fussball gehen möchte.
→ "Möchtest du zum Fussball gehen?", fragt er.
"""

INDIRECT_INSTRUCTIONS = """
Task: Convert the given text to indirect speech (Indirekte Rede).

## German Indirect Speech Rules (Indirekte Rede):
- Remove quotation marks
- Change pronouns: ich → er/sie, du → er/sie, mein → sein/ihr, etc.
- Use Konjunktiv I for reporting: er sage, sie gehe, er habe
- If Konjunktiv I matches indicative, use Konjunktiv II: er ginge, er hätte
- Question word for questions: ob, wann, wo, warum
- Change sentence structure to subordinate clause
- Add introductory clause: dass-Satz or w-questions

# Examples
"Ich komme morgen", sagt sie.
→ Sie sagt, dass sie morgen komme.

"Wann kommst du?", fragt er mich.
→ Er fragt mich, wann ich komme.

"Wir haben das Buch gelesen", berichten sie.
→ Sie berichten, dass sie das Buch gelesen hätten.
"""


class CharacterSpeechAgent(QuickActionBaseAgent):
    def __init__(self, config: Configuration):
        super().__init__(config)

    @override
    def create_instruction(self, ctx: RunContext[QuickActionContext]) -> str:
        sub_instructions = DIRECT_INSTRUCTION if ctx.deps.options == "direct_speech" else INDIRECT_INSTRUCTIONS

        return INSTRUCTION.format(sub_instructions=sub_instructions)
