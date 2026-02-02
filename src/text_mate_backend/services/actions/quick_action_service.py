import time
from typing import final

from dcc_backend_common.logger import get_logger
from fastapi.responses import StreamingResponse

from text_mate_backend.agents import QuickActionBaseAgent
from text_mate_backend.agents.agent_types.quick_actions.bullet_point_agent import BulletPointAgent
from text_mate_backend.agents.agent_types.quick_actions.character_speech_agent import CharacterSpeechAgent
from text_mate_backend.agents.agent_types.quick_actions.custom_agent import CustomAgent
from text_mate_backend.agents.agent_types.quick_actions.formality_agent import FormalityAgent
from text_mate_backend.agents.agent_types.quick_actions.medium_agent import MediumAgent
from text_mate_backend.agents.agent_types.quick_actions.plain_language_agent import PlainLanguageAgent
from text_mate_backend.agents.agent_types.quick_actions.proof_read_agent import ProofReadAgent
from text_mate_backend.agents.agent_types.quick_actions.social_media_agent import SocialMediaAgent
from text_mate_backend.agents.agent_types.quick_actions.summarize_agent import SummarizeAgent
from text_mate_backend.models.quick_actions_models import Actions, CurrentUser, QuickActionContext
from text_mate_backend.services.actions.action_utils import create_streaming_response
from text_mate_backend.utils.configuration import Configuration

logger = get_logger("quick_action_service")


@final
class QuickActionService:
    def __init__(self, config: Configuration) -> None:
        self.config = config

        self.agent_mapping: dict[Actions, QuickActionBaseAgent] = {
            Actions.BulletPoints: BulletPointAgent(config),
            Actions.Custom: CustomAgent(config),
            Actions.Formality: FormalityAgent(config),
            Actions.Medium: MediumAgent(config),
            Actions.PlainLanguage: PlainLanguageAgent(config),
            Actions.SocialMediafy: SocialMediaAgent(config),
            Actions.Summarize: SummarizeAgent(config),
            Actions.Proofread: ProofReadAgent(config),
            Actions.CharacterSpeech: CharacterSpeechAgent(config),
        }

    async def run(self, action: Actions, text: str, options: str, current_user: CurrentUser) -> StreamingResponse:
        """
        Perform the specified quick action on a given text and return a streaming response.

        Parameters:
            action (Actions): The quick action to execute.
            text (str): The input text to process.
            options (str): Semicolon-delimited option segments. If a segment begins with
                "language code:" its value is extracted as the request language and removed
                from the options passed to the action.

        Returns:
            StreamingResponse: A streaming response containing the processed text.

        Raises:
            ValueError: If action is unknown or action returned None.
        """
        segments = [seg.strip() for seg in options.split(";") if seg.strip()]
        lang_segment = next((s for s in segments if s.startswith("language code:")), None)
        language = lang_segment.split(":", 1)[1].strip() if lang_segment else None
        filtered_segments = [s for s in segments if s is not lang_segment]
        context = QuickActionContext(
            text=text,
            options=";".join(filtered_segments),
            language=language,
        )

        if action == Actions.Medium:
            context = QuickActionContext[CurrentUser](
                text=context.text, options=context.options, extras=current_user, language=context.language
            )

        start_time = time.time()
        try:
            agent = self.agent_mapping[action]

            generator = agent.run_stream_text(user_prompt=context.text, deps=context)
            response = await create_streaming_response(generator)

            process_time = time.time() - start_time
            if response is None:
                raise ValueError(f"Quick action {action} returned None")
            return response
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"Quick action {action} failed",
                error=str(e),
                error_type=type(e).__name__,
                processing_time_ms=round(process_time * 1000),
            )
            raise
