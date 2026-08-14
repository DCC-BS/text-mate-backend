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
from text_mate_backend.agents.agent_types.quick_actions.proof_read_agent import ProofReadAgent
from text_mate_backend.agents.agent_types.quick_actions.social_media_agent import SocialMediaAgent
from text_mate_backend.agents.agent_types.quick_actions.summarize_agent import SummarizeAgent
from text_mate_backend.agents.agent_types.quick_actions.user_action_agent import UserActionAgent
from text_mate_backend.models.error_codes import REWRITE_TEXT_ERROR
from text_mate_backend.models.error_response import ApiErrorException
from text_mate_backend.models.quick_actions_models import Actions, CurrentUser, QuickActionContext
from text_mate_backend.services.actions.action_utils import create_streaming_response
from text_mate_backend.services.user_actions_service import UserActionService
from text_mate_backend.utils.configuration import Configuration

logger = get_logger("quick_action_service")


@final
class QuickActionService:
    def __init__(self, user_action_service: UserActionService, config: Configuration) -> None:
        self.config = config
        self.user_action_service = user_action_service

        # Actions.PlainLanguage is deliberately absent: simplification moved to
        # POST /simplify, where it is a measured, closed loop (readability gate +
        # retry) instead of a single unmeasured call. The enum member stays so an
        # old client gets a clear 400 rather than a 500.
        # See docs/simplify_redesign.md section 3, "Old action".
        self.agent_mapping: dict[Actions, QuickActionBaseAgent] = {
            Actions.BulletPoints: BulletPointAgent(config),
            Actions.Custom: CustomAgent(config),
            Actions.Formality: FormalityAgent(config),
            Actions.Medium: MediumAgent(config),
            Actions.SocialMediafy: SocialMediaAgent(config),
            Actions.Summarize: SummarizeAgent(config),
            Actions.Proofread: ProofReadAgent(config),
            Actions.CharacterSpeech: CharacterSpeechAgent(config),
        }

        self.user_agent = UserActionAgent(config)

    async def run(self, action: Actions | str, text: str, options: str, current_user: CurrentUser) -> StreamingResponse:
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

        if action not in [member.value for member in Actions]:
            logger.debug("Action is not a predefined quick action, treating as custom user action", action=str(action))
            user_action = self.user_action_service.get_action(action)
            context = QuickActionContext(
                text=text, options=";".join(filtered_segments), language=language, extras=user_action
            )

        start_time = time.time()
        try:
            agent = self.get_agent(action)

            generator = agent.run_stream_text(user_prompt=context.text, deps=context)
            response = await create_streaming_response(generator)

            process_time = time.time() - start_time
            if response is None:
                raise ValueError(f"Quick action {action} returned None")
            return response
        except Exception as e:
            process_time = time.time() - start_time
            logger.exception(
                "Quick action failed",
                action=str(action),
                error_type=type(e).__name__,
                processing_time_ms=round(process_time * 1000),
            )
            raise

    def get_agent(self, id: str | Actions) -> QuickActionBaseAgent:
        if id in [member.value for member in Actions]:
            agent = self.agent_mapping.get(Actions(id))
            if agent is None:
                # A predefined action with no agent: retired, not missing.
                raise ApiErrorException(
                    {
                        "status": 400,
                        "errorId": REWRITE_TEXT_ERROR,
                        "debugMessage": (
                            f"Quick action '{Actions(id).value}' has been retired. "
                            "Use POST /simplify for simplification."
                        ),
                    }
                )
            return agent

        return self.user_agent
