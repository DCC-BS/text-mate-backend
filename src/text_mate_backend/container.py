from dependency_injector import containers, providers

from text_mate_backend.services.actions.quick_action_service import QuickActionService
from text_mate_backend.services.advisor import AdvisorService
from text_mate_backend.services.dspy_facade import DspyFacade
from text_mate_backend.services.language_tool_service import LanguageToolService
from text_mate_backend.services.rewrite_text import TextRewriteService
from text_mate_backend.services.text_correction_language_tool import TextCorrectionService
from text_mate_backend.services.word_synonym_service import WordSynonymService
from text_mate_backend.utils.configuration import Configuration


class Container(containers.DeclarativeContainer):
    config: providers.Singleton[Configuration] = providers.Singleton(Configuration)
    language_tool_service: providers.Singleton[LanguageToolService] = providers.Singleton(
        LanguageToolService, config=config
    )
    text_correction_service: providers.Singleton[TextCorrectionService] = providers.Singleton(
        TextCorrectionService, config=config, language_tool_Service=language_tool_service
    )

    advisor_service: providers.Singleton[AdvisorService] = providers.Singleton(AdvisorService, config=config)
    quick_action_service: providers.Singleton[QuickActionService] = providers.Singleton(
        QuickActionService, config=config
    )

    dspy_facade_factory = providers.Factory(
        DspyFacade,
        config=config,
    )

    text_rewrite_service: providers.Singleton[TextRewriteService] = providers.Singleton(
        TextRewriteService, dspy_facade_factory=dspy_facade_factory.provider
    )

    word_synonym_service: providers.Singleton[WordSynonymService] = providers.Singleton(
        WordSynonymService,
        dspy_facade_factory=dspy_facade_factory.provider,
    )
