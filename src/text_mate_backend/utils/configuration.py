import os

from text_mate_backend.utils.load_env import load_env


class Configuration:
    def __init__(self) -> None:
        self.openai_api_base_url: str = os.getenv("OPENAI_API_BASE_URL", "http://localhost:8000/v1")
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "none")
        self.llm_model: str = os.getenv("LLM_MODEL", "ollama_chat/llama3.2")
        self.language_tool_api_url: str = os.getenv("LANGUAGE_TOOL_API_URL", "http://localhost:8010/")
        self.client_url: str = os.getenv("CLIENT_URL", "http://localhost:3000")

    def __str__(self) -> str:
        return f"""
        Configuration(
            client_url={self.client_url},
            openai_api_base_url={self.openai_api_base_url},
            openai_api_key={self.openai_api_key},
            llm_model={self.llm_model},
            language_tool_api_url={self.language_tool_api_url})
        """


_config: Configuration | None = None


def get_config() -> Configuration:
    """Get the configuration."""
    load_env()

    global _config
    if _config is None:
        _config = Configuration()
    return _config
