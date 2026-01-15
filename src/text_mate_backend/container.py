from dependency_injector import containers, providers

from text_mate_backend.services.actions.quick_action_service import QuickActionService
from text_mate_backend.services.advisor import AdvisorService
from text_mate_backend.services.azure_service import AzureService
from text_mate_backend.services.document_conversion_service import DocumentConversionService
from text_mate_backend.services.language_tool_service import LanguageToolService
from text_mate_backend.services.pydantic_ai_facade import PydanticAIAgent
from text_mate_backend.services.rewrite_text import TextRewriteService
from text_mate_backend.services.sentence_rewrite_service import SentenceRewriteService
from text_mate_backend.services.text_correction_language_tool import TextCorrectionService
from text_mate_backend.services.word_synonym_service import WordSynonymService
from text_mate_backend.utils.auth_settings import AuthSettings
from text_mate_backend.utils.configuration import Configuration


class Container(containers.DeclarativeContainer):
    config: providers.Singleton[Configuration] = providers.Singleton(Configuration)
    auth_settings: providers.Singleton[AuthSettings] = providers.Singleton(AuthSettings, config=config)

    language_tool_service: providers.Singleton[LanguageToolService] = providers.Singleton(
        LanguageToolService, config=config
    )
    text_correction_service: providers.Singleton[TextCorrectionService] = providers.Singleton(
        TextCorrectionService, config=config, language_tool_Service=language_tool_service
    )

    pydantic_ai: providers.Singleton[PydanticAIAgent] = providers.Singleton(
        PydanticAIAgent,
        config=config,
    )

    advisor_service: providers.Singleton[AdvisorService] = providers.Singleton(AdvisorService, llm_facade=pydantic_ai)

    document_conversion_service: providers.Singleton[DocumentConversionService] = providers.Singleton(
        DocumentConversionService, config=config
    )

    quick_action_service: providers.Singleton[QuickActionService] = providers.Singleton(
        QuickActionService, llm_facade=pydantic_ai, config=config
    )

    text_rewrite_service: providers.Singleton[TextRewriteService] = providers.Singleton(
        TextRewriteService, llm_facade=pydantic_ai
    )

    word_synonym_service: providers.Singleton[WordSynonymService] = providers.Singleton(
        WordSynonymService,
        llm_facade=pydantic_ai,
    )

    sentence_rewrite_service: providers.Singleton[SentenceRewriteService] = providers.Singleton(
        SentenceRewriteService,
        llm_facade=pydantic_ai,
    )

    azure_service: providers.Singleton[AzureService] = providers.Singleton(AzureService, auth_settings=auth_settings)
