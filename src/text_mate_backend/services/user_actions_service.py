from pathlib import Path

import yaml
from dcc_backend_common.logger import get_logger
from fastapi_azure_auth.user import User

from text_mate_backend.models.user_action_models import UserAction
from text_mate_backend.utils.configuration import Configuration

logger = get_logger("quick_action_service")

ACTIONS_DIR = Path("assets/actions")


class UserActionService:
    def __init__(self, config: Configuration) -> None:
        self.config = config
        self.actions: dict[str, UserAction] = {}

        for action in self._load_user_actions():
            self.actions[action.id] = action

    def _load_user_actions(self) -> list[UserAction]:
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

    def get_action(self, id: str):
        return self.actions[id]
