import time
from typing import final

from fastapi.responses import StreamingResponse
from returns.result import safe

from text_mate_backend.models.quick_actions_models import Actions, QuickActionContext
from text_mate_backend.services.actions.bullet_points_action import bullet_points
from text_mate_backend.services.actions.custom_action import custom_prompt
from text_mate_backend.services.actions.formality_action import formality
from text_mate_backend.services.actions.medium_action import medium
from text_mate_backend.services.actions.plain_language_action import plain_language
from text_mate_backend.services.actions.social_media_action import social_mediafy
from text_mate_backend.services.actions.summarize_action import summarize
from text_mate_backend.services.llm_facade import LLMFacade
from text_mate_backend.utils.configuration import Configuration
from text_mate_backend.utils.logger import get_logger

logger = get_logger("quick_action_service")


@final
class QuickActionService:
    def __init__(self, llm_facade: LLMFacade, config: Configuration) -> None:
        self.llm_facade = llm_facade
        self.config = config

    @safe
    def run(self, action: Actions, text: str, options: str) -> StreamingResponse:
        """
        Execute the requested quick action on the provided text.

        Args:
            action: The type of quick action to perform
            text: The text to apply the action to

        Returns:
            A StreamingResponse containing the processed text

        Raises:
            ValueError: If the action type is unknown
        """
        text_length = len(text)
        text_preview = text[:50] + ("..." if text_length > 50 else "")
        language = next(filter(lambda x: "language code" in x, options.split(";")), None)
        language = language.replace("language code:", "") if language else None

        logger.debug("Text preview", preview=text_preview)

        context = QuickActionContext(
            text=text, options=options.replace(f";language code:{language}", "").strip(), language=language
        )

        start_time = time.time()
        try:
            app_config = self.config
            response = None
            match action:
                case Actions.PlainLanguage:
                    response = plain_language(context, app_config, self.llm_facade)
                case Actions.BulletPoints:
                    response = bullet_points(context, app_config, self.llm_facade)
                case Actions.Summarize:
                    response = summarize(context, app_config, self.llm_facade)
                case Actions.SocialMediafy:
                    response = social_mediafy(context, app_config, self.llm_facade)
                case Actions.FORMALITY:
                    response = formality(context, app_config, self.llm_facade)
                case Actions.MEDIUM:
                    response = medium(context, app_config, self.llm_facade)
                case Actions.CUSTOM:
                    response = custom_prompt(context, app_config, self.llm_facade)

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
