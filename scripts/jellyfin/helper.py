from collections import Counter
from typing import Optional

import httpx
import structlog
from pydantic import BaseModel, Field

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=False,
)


def get_logger(name: str = __name__) -> structlog.BoundLogger:
    return structlog.get_logger(name)


def configure_log_level(verbose: bool = False):
    level = 10 if verbose else 20
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(level))


class MissingItem(BaseModel):
    model_config = {"frozen": True}

    id: str = Field(..., alias="Id")
    name: str = Field("", alias="Name")
    type: str = Field("", alias="Type")
    path: Optional[str] = Field(None, alias="Path")

    @property
    def top_level_folder(self) -> str:
        if not self.path:
            return "(no path)"
        for prefix in ("/media/videos/", "/media/downloads/"):
            if self.path.startswith(prefix):
                parts = self.path[len(prefix) :].split("/")
                return f"{prefix}{parts[0]}" if parts[0] else prefix.rstrip("/")
        return self.path.split("/")[1] if "/" in self.path else self.path


class MissingItemsResponse(BaseModel):
    total: int = Field(..., alias="TotalRecordCount")
    items: list[MissingItem] = Field(default_factory=list, alias="Items")


class FolderSummary(BaseModel):
    model_config = {"frozen": True}

    folder: str
    count: int


class JellyfinClient:
    def __init__(self, base_url: str, api_key: str):
        self.http = httpx.Client(
            base_url=base_url,
            params={"api_key": api_key},
            timeout=30,
        )
        self.log = get_logger().bind(component="jellyfin_client")

    def get_missing_items(self) -> list[MissingItem]:
        resp = self.http.get(
            "/Items",
            params={"IsMissing": "true", "Recursive": "true", "Fields": "Path"},
        )
        resp.raise_for_status()
        data = MissingItemsResponse.model_validate(resp.json())
        self.log.debug("fetched_missing_items", count=data.total)
        return data.items

    def refresh_library(self) -> None:
        resp = self.http.post("/Library/Refresh")
        resp.raise_for_status()
        self.log.info("library_refresh_triggered")

    def summarize_by_folder(self, items: list[MissingItem]) -> list[FolderSummary]:
        counts: Counter[str] = Counter()
        for item in items:
            counts[item.top_level_folder] += 1
        return [
            FolderSummary(folder=folder, count=count)
            for folder, count in sorted(counts.items(), key=lambda x: -x[1])
        ]

    def close(self):
        self.http.close()
