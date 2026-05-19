import time
from pathlib import Path

import yaml
from dcc_backend_common.logger import get_logger
from fastapi.responses import StreamingResponse
from fastapi_azure_auth.user import User

from text_mate_backend.agents.agent_types.quick_actions.user_action_agent import UserActionAgent
from text_mate_backend.models.quick_actions_models import QuickActionContext
from text_mate_backend.models.user_action_models import UserAction
from text_mate_backend.services.actions.action_utils import create_streaming_response
from text_mate_backend.utils.configuration import Configuration

logger = get_logger("quick_action_service")

ACTIONS_DIR = Path("assets/actions")


class UserActionService:
    def __init__(self, config: Configuration) -> None:
        self.config = config
        self.actions: dict[str, UserAction] = {}

        for action in self.load_user_actions():
            self.actions[action.id] = action

    def load_user_actions(self) -> list[UserAction]:
        actions: list[UserAction] = []
        if not ACTIONS_DIR.exists():
            raise FileNotFoundError(f"Actions directory not found: {ACTIONS_DIR}")

        for file_path in sorted(ACTIONS_DIR.glob("*.md")):
            raw = file_path.read_text(encoding="utf-8")
            content = raw.strip()
            if not content.startswith("---"):
                raise ValueError(f"Missing frontmatter in {file_path}")

            parts = content.split("---", 2)
            if len(parts) < 3:
                raise ValueError(f"Malformed frontmatter in {file_path}")

            try:
                meta = yaml.safe_load(parts[1])
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML in {file_path}: {e}") from e

            if not isinstance(meta, dict):
                raise ValueError(f"Frontmatter must be a YAML mapping in {file_path}")

            if "id" not in meta or "name" not in meta:
                raise ValueError(f"Missing required fields 'id' or 'name' in {file_path}")

            actions.append(
                UserAction(
                    id=meta["id"],
                    name=meta["name"],
                    groups=meta.get("groups", []),
                    content=parts[2].strip(),
                )
            )

        return actions

    def get_actions(self, user: User) -> list[UserAction]:
        return list(
            filter(
                lambda x: len(x.groups) == 0 or len(set(x.groups).intersection(user.roles)) > 0,
                self.actions.values(),
            )
        )

    async def execute_action(self, id: str, text: str, options: str) -> StreamingResponse:
        agent = UserActionAgent(self.config)

        if id not in self.actions:
            raise ValueError(f"Quick action {id} not found")

        user_action = self.actions[id]

        segments = [seg.strip() for seg in options.split(";") if seg.strip()]
        lang_segment = next((s for s in segments if s.startswith("language code:")), None)
        language = lang_segment.split(":", 1)[1].strip() if lang_segment else None
        filtered_segments = [s for s in segments if s is not lang_segment]
        context = QuickActionContext(
            text=text, options=";".join(filtered_segments), language=language, extras=user_action
        )

        start_time = time.time()
        try:
            generator = agent.run_stream_text(user_prompt=context.text, deps=context)
            response = await create_streaming_response(generator)

            process_time = time.time() - start_time
            if response is None:
                raise ValueError(f"Quick action {user_action.id} returned None")
            return response
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"Quick action {user_action.id} failed",
                error=str(e),
                error_type=type(e).__name__,
                processing_time_ms=round(process_time * 1000),
            )
            raise

        pass
