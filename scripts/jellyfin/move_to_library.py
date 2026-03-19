#!/usr/bin/env python3
"""
Move media from downloads to library and update Jellyfin via API.

Uses POST /Library/Media/Updated to notify Jellyfin of file relocations,
preventing duplicate entries.

Runs locally and uses kubectl exec to perform file operations in the Jellyfin pod.
"""

import os
import subprocess
from typing import List

import httpx
import typer
from pydantic import BaseModel

from jellyfin.helper import get_logger, configure_log_level

log = get_logger(__name__)
app = typer.Typer(help="Move media from downloads to library and update Jellyfin")

CATEGORY_MAPPINGS = {
    "documentaries": "documentaries",
    "movies": "movies",
    "shows": "shows",
    "stand-up": "stand-up",
    "tv-programs": "tv-programs",
    "tv-shows": "tv-shows",
}


class MediaUpdate(BaseModel):
    Path: str
    UpdateType: str  # "Created" or "Deleted"


class MediaUpdateRequest(BaseModel):
    Updates: List[MediaUpdate]


class JellyfinMover:
    def __init__(self, base_url: str, api_key: str, namespace: str, pod_label: str):
        self.http = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"MediaBrowser Token={api_key}"},
            timeout=30,
        )
        self.namespace = namespace
        self.pod_label = pod_label
        self.log = get_logger().bind(component="jellyfin_mover")

    def _kubectl_exec(self, *cmd: str) -> subprocess.CompletedProcess:
        kubectl_cmd = [
            "kubectl",
            "exec",
            "-n",
            self.namespace,
            f"deployment/{self.pod_label}",
            "-c",
            "jellyfin",
            "--",
            *cmd,
        ]
        return subprocess.run(kubectl_cmd, capture_output=True, text=True, check=True)

    def path_exists(self, path: str) -> bool:
        result = subprocess.run(
            [
                "kubectl",
                "exec",
                "-n",
                self.namespace,
                f"deployment/{self.pod_label}",
                "-c",
                "jellyfin",
                "--",
                "test",
                "-e",
                path,
            ],
            capture_output=True,
        )
        return result.returncode == 0

    def list_dir(self, path: str) -> List[str]:
        try:
            result = self._kubectl_exec(
                "find", path, "-maxdepth", "1", "-mindepth", "1", "!", "-name", ".*"
            )
            items = result.stdout.strip().split("\n") if result.stdout.strip() else []
            return [item for item in items if item]
        except subprocess.CalledProcessError:
            return []

    def get_item_by_path(self, path: str):
        resp = self.http.get(
            "/Items",
            params={"Recursive": "true", "Path": path, "Fields": "ProviderIds,Path"},
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("Items", [])
        return items[0] if items else None

    def copy_provider_ids(self, item_id: str, provider_ids: dict) -> None:
        resp = self.http.post(f"/Items/{item_id}", json={"ProviderIds": provider_ids})
        resp.raise_for_status()
        self.log.info("provider_ids_copied", item_id=item_id, ids=provider_ids)

    def wait_for_library_scan(self, path: str, max_wait: int = 60):
        import time

        start_time = time.time()
        while time.time() - start_time < max_wait:
            item = self.get_item_by_path(path)
            if item:
                return item
            time.sleep(5)
        return None

    def delete_item(self, item_id: str) -> None:
        resp = self.http.delete(
            f"/Items/{item_id}",
            timeout=httpx.Timeout(timeout=120.0),
        )
        resp.raise_for_status()
        self.log.info("item_deleted", item_id=item_id)

    def trigger_library_scan(self) -> None:
        resp = self.http.post("/Library/Refresh")
        resp.raise_for_status()
        self.log.info("library_scan_triggered")

    def notify_media_updated(self, updates: List[MediaUpdate]) -> None:
        request = MediaUpdateRequest(Updates=updates)

        resp = self.http.post("/Library/Media/Updated", json=request.model_dump())
        resp.raise_for_status()
        self.log.info("media_update_sent", count=len(updates))

    def move_file(self, src: str, dest: str) -> None:
        dest_parent = "/".join(dest.split("/")[:-1])

        self._kubectl_exec("mkdir", "-p", dest_parent)
        self.log.info("moving_file", src=src, dest=dest)
        self._kubectl_exec("mv", src, dest)

    def close(self):
        self.http.close()


@app.command()
def main(
    download_root: str = typer.Option(
        "/media/downloads", help="Download root directory"
    ),
    library_root: str = typer.Option("/media/videos", help="Library root directory"),
    host: str = typer.Option("http://jellyfin.home.arpa", help="Jellyfin base URL"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Preview moves without executing"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
):
    configure_log_level(verbose)

    api_key = os.environ.get("JELLYFIN_API_KEY")
    if not api_key:
        log.error(
            "missing_api_key",
            message="JELLYFIN_API_KEY environment variable is required",
        )
        raise typer.Exit(code=1)

    mover = JellyfinMover(
        host.rstrip("/"), api_key, namespace="media-center", pod_label="jellyfin"
    )

    updates = []
    moves = []

    for src_subdir, dest_subdir in CATEGORY_MAPPINGS.items():
        src_dir = f"{download_root}/{src_subdir}"
        dest_dir = f"{library_root}/{dest_subdir}"

        items = mover.list_dir(src_dir)
        if not items:
            log.debug("skip_empty", src=src_dir)
            continue

        log.info("processing", src=src_dir, dest=dest_dir)

        for item_path in items:
            item_name = item_path.split("/")[-1]

            if item_name.startswith("."):
                continue

            dest_item = f"{dest_dir}/{item_name}"

            if mover.path_exists(dest_item):
                log.warning(
                    "destination_exists",
                    dest=dest_item,
                    message="Skipping - destination already exists",
                )
                continue

            moves.append((item_path, dest_item))

            updates.append(MediaUpdate(Path=item_path, UpdateType="Deleted"))
            updates.append(MediaUpdate(Path=dest_item, UpdateType="Created"))

    if not moves:
        log.info("no_files_to_move")
        raise typer.Exit(code=0)

    log.info("files_to_move", count=len(moves))

    if dry_run:
        log.info("dry_run_mode", total=len(moves))
        for src, dest in moves:
            log.info("would_move", src=src, dest=dest)
        raise typer.Exit(code=0)

    log.info("starting_moves", total=len(moves))

    for src, dest in moves:
        try:
            old_item = mover.get_item_by_path(src)
            old_provider_ids = old_item.get("ProviderIds", {}) if old_item else {}

            if old_item:
                log.info(
                    "captured_metadata",
                    src=src,
                    provider_ids=old_provider_ids,
                )

            mover.move_file(src, dest)
            log.info("file_moved", src=src, dest=dest)

            if old_item:
                mover.delete_item(old_item["Id"])
                log.info("old_item_deleted", item_id=old_item["Id"])

            mover.trigger_library_scan()
            log.info("scan_triggered", waiting_for=dest)

            new_item = mover.wait_for_library_scan(dest, max_wait=90)
            if not new_item:
                log.error(
                    "new_item_not_found",
                    dest=dest,
                    message="New item not found after library scan",
                )
                continue

            log.info("new_item_found", dest=dest, new_id=new_item["Id"])

            if old_provider_ids:
                mover.copy_provider_ids(new_item["Id"], old_provider_ids)

            log.info("move_complete_for_item", dest=dest)

        except Exception as e:
            log.error("move_failed", src=src, dest=dest, error=str(e))
            raise

    log.info("move_complete", total=len(moves))

    mover.close()


if __name__ == "__main__":
    app()
