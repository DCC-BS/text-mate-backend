import time
from enum import Enum

from fastapi.responses import StreamingResponse
from returns.result import safe

from text_mate_backend.services.actions.bullet_points_action import bullet_points
from text_mate_backend.services.actions.shorten_action import shorten
from text_mate_backend.services.actions.simplify_action import simplify
from text_mate_backend.services.actions.social_media_action import social_mediafy
from text_mate_backend.services.actions.summarize_action import summarize
from text_mate_backend.services.actions.translate_action import translate
from text_mate_backend.services.llm_facade import LLMFacade
from text_mate_backend.utils.logger import get_logger

logger = get_logger("quick_action_service")


class Actions(str, Enum):
    Simplify = "simplify"
    Shorten = "shorten"
    BulletPoints = "bullet_points"
    Summarize = "summarize"
    SocialMediafy = "social_mediafy"
    TranslateDeCH = "translate_de-CH"
    TranslateEnUS = "translate_en-US"
    TranslateEnGB = "translate_en-GB"
    TranslateFr = "translate_fr"
    TranslateIt = "translate_it"


class QuickActionService:
    def __init__(self, llm_facade: LLMFacade) -> None:
        self.llm_facade = llm_facade

    @safe
    def run(self, action: Actions, text: str) -> StreamingResponse:
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

        logger.info(f"Running quick action: {action}", text_length=text_length)
        logger.debug("Text preview", preview=text_preview)

        start_time = time.time()
        try:
            response = None
            match action:
                case Actions.Simplify:
                    response = simplify(text, self.llm_facade)
                    logger.info("Applied simplify action")
                case Actions.Shorten:
                    response = shorten(text, self.llm_facade)
                    logger.info("Applied shorten action")
                case Actions.BulletPoints:
                    response = bullet_points(text, self.llm_facade)
                    logger.info("Applied bullet points action")
                case Actions.Summarize:
                    response = summarize(text, self.llm_facade)
                    logger.info("Applied summarize action")
                case Actions.SocialMediafy:
                    response = social_mediafy(text, self.llm_facade)
                    logger.info("Applied social media action")
                case Actions.TranslateDeCH:
                    response = translate(text, "German (CH)", self.llm_facade)
                    logger.info("Applied translate action")
                case Actions.TranslateEnUS:
                    response = translate(text, "English (US)", self.llm_facade)
                    logger.info("Applied translate action")
                case Actions.TranslateEnGB:
                    response = translate(text, "English (GB)", self.llm_facade)
                    logger.info("Applied translate action")
                case Actions.TranslateFr:
                    response = translate(text, "French", self.llm_facade)
                    logger.info("Applied translate action")
                case Actions.TranslateIt:
                    response = translate(text, "Italian", self.llm_facade)
                    logger.info("Applied translate action")

            process_time = time.time() - start_time
            logger.info(f"Quick action {action} completed", processing_time_ms=round(process_time * 1000))

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
