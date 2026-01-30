from dependency_injector import containers, providers

from text_mate_backend.services.actions.quick_action_service import QuickActionService
from text_mate_backend.services.advisor import AdvisorService
from text_mate_backend.services.azure_service import AzureService
from text_mate_backend.services.document_conversion_service import DocumentConversionService
from text_mate_backend.services.language_tool_service import LanguageToolService
from text_mate_backend.services.text_correction_language_tool import TextCorrectionService
from text_mate_backend.utils.auth import AuthSchema, create_auth_scheme
from text_mate_backend.utils.auth_settings import AuthSettings
from text_mate_backend.utils.configuration import Configuration


class Container(containers.DeclarativeContainer):
    config: providers.Object[Configuration] = providers.Object(Configuration.from_env())
    auth_settings: providers.Singleton[AuthSettings] = providers.Singleton(AuthSettings, config=config)

    language_tool_service: providers.Singleton[LanguageToolService] = providers.Singleton(
        LanguageToolService, config=config
    )
    text_correction_service: providers.Singleton[TextCorrectionService] = providers.Singleton(
        TextCorrectionService, config=config, language_tool_Service=language_tool_service
    )

    advisor_service: providers.Singleton[AdvisorService] = providers.Singleton(
        AdvisorService,
        config=config,
    )

    document_conversion_service: providers.Singleton[DocumentConversionService] = providers.Singleton(
        DocumentConversionService, config=config
    )

    quick_action_service: providers.Singleton[QuickActionService] = providers.Singleton(
        QuickActionService, config=config
    )

    azure_service: providers.Singleton[AzureService] = providers.Singleton(AzureService, auth_settings=auth_settings)

    auth_scheme: providers.Singleton[AuthSchema] = providers.Singleton(
        create_auth_scheme, azure_scheme=azure_service.provided.azure_scheme, disable_auth=config.provided.disable_auth
    )
