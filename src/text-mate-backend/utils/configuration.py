import os


class Configuration:
    def __init__(self) -> None:
        self.isDev: bool = os.getenv("ENV", "dev") == "true"
        self.api_port: int = int(os.getenv("API_PORT", 8090))
        self.openai_api_base_url: str = os.getenv("OPENAI_API_BASE_URL", "http://localhost:8000/v1")
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "none")
        self.llm_model: str = os.getenv("LLM_MODEL", "ollama_chat/llama3.2")
        self.language_tool_api_url: str = os.getenv("LANGUAGE_TOOL_API_URL", "http://localhost:8010/")
        self.client_url: str = os.getenv("CLIENT_URL", "http://localhost:3000")

    def __str__(self) -> str:
        return f"""
        Configuration(
            isDev={self.isDev},
            api_port={self.api_port},
            client_url={self.client_url},
            openai_api_base_url={self.openai_api_base_url},
            openai_api_key={self.openai_api_key},
            llm_model={self.llm_model},
            language_tool_api_url={self.language_tool_api_url})
        """


config = Configuration()
