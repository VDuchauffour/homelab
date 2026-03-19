from unittest.mock import MagicMock, patch
import pytest
from jellyfin.move_to_library import JellyfinMover, CATEGORY_MAPPINGS


@pytest.fixture
def mover():
    with patch("jellyfin.move_to_library.httpx.Client"):
        return JellyfinMover(
            base_url="http://test.local",
            api_key="test-key",
            namespace="test-ns",
            pod_label="test-pod",
        )


class TestMetadataPreservation:
    def test_get_item_by_path_returns_item_with_provider_ids(self, mover):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Items": [
                {
                    "Id": "abc123",
                    "Name": "Test Movie",
                    "Path": "/media/downloads/movies/test.mkv",
                    "ProviderIds": {"Tmdb": "12345", "Imdb": "tt67890"},
                }
            ],
            "TotalRecordCount": 1,
        }
        mover.http.get.return_value = mock_response

        item = mover.get_item_by_path("/media/downloads/movies/test.mkv")

        assert item is not None
        assert item["Id"] == "abc123"
        assert item["ProviderIds"]["Tmdb"] == "12345"
        assert item["ProviderIds"]["Imdb"] == "tt67890"
        mover.http.get.assert_called_once()

    def test_get_item_by_path_returns_none_when_not_found(self, mover):
        mock_response = MagicMock()
        mock_response.json.return_value = {"Items": [], "TotalRecordCount": 0}
        mover.http.get.return_value = mock_response

        item = mover.get_item_by_path("/media/nonexistent.mkv")

        assert item is None

    def test_delete_item_removes_old_entry(self, mover):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mover.http.delete.return_value = mock_response

        mover.delete_item("old_item_id")

        mover.http.delete.assert_called_once()
        call_args = mover.http.delete.call_args
        assert call_args[0][0] == "/Items/old_item_id"
        assert call_args[1]["timeout"].read == 120.0

    def test_copy_provider_ids_via_update_item(self, mover):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mover.http.post.return_value = mock_response

        provider_ids = {"Tmdb": "12345", "Imdb": "tt67890"}

        mover.copy_provider_ids("new_item_id", provider_ids)

        mover.http.post.assert_called_once()
        call_args = mover.http.post.call_args
        assert call_args[0][0] == "/Items/new_item_id"
        assert call_args[1]["json"]["ProviderIds"] == provider_ids

    def test_wait_for_library_scan_polls_until_item_found(self, mover):
        call_count = 0

        def get_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_resp = MagicMock()
            if call_count < 3:
                mock_resp.json.return_value = {"Items": [], "TotalRecordCount": 0}
            else:
                mock_resp.json.return_value = {
                    "Items": [{"Id": "new123", "Path": "/media/videos/test.mkv"}],
                    "TotalRecordCount": 1,
                }
            mock_resp.raise_for_status = MagicMock()
            return mock_resp

        mover.http.get = MagicMock(side_effect=get_side_effect)

        with patch("time.sleep"):
            item = mover.wait_for_library_scan("/media/videos/test.mkv", max_wait=30)

        assert item is not None
        assert item["Id"] == "new123"
        assert call_count == 3

    def test_wait_for_library_scan_times_out(self, mover):
        mock_response = MagicMock()
        mock_response.json.return_value = {"Items": [], "TotalRecordCount": 0}
        mover.http.get.return_value = mock_response

        with patch("time.sleep"):
            item = mover.wait_for_library_scan("/media/videos/test.mkv", max_wait=1)

        assert item is None


class TestFileOperations:
    @patch("subprocess.run")
    def test_kubectl_exec_constructs_correct_command(self, mock_run, mover):
        mock_run.return_value = MagicMock(stdout="output", returncode=0)

        mover._kubectl_exec("ls", "-la", "/tmp")

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd == [
            "kubectl",
            "exec",
            "-n",
            "test-ns",
            "deployment/test-pod",
            "-c",
            "jellyfin",
            "--",
            "ls",
            "-la",
            "/tmp",
        ]

    @patch("subprocess.run")
    def test_path_exists_returns_true_when_exists(self, mock_run, mover):
        mock_run.return_value = MagicMock(returncode=0)

        result = mover.path_exists("/media/videos/test.mkv")

        assert result is True

    @patch("subprocess.run")
    def test_path_exists_returns_false_when_missing(self, mock_run, mover):
        mock_run.return_value = MagicMock(returncode=1)

        result = mover.path_exists("/media/nonexistent.mkv")

        assert result is False

    @patch("subprocess.run")
    def test_list_dir_returns_items(self, mock_run, mover):
        mock_run.return_value = MagicMock(
            stdout="/media/downloads/file1.mkv\n/media/downloads/file2.mkv\n",
            returncode=0,
        )

        items = mover.list_dir("/media/downloads")

        assert len(items) == 2
        assert "/media/downloads/file1.mkv" in items
        assert "/media/downloads/file2.mkv" in items

    @patch("subprocess.run")
    def test_list_dir_returns_empty_on_error(self, mock_run, mover):
        from subprocess import CalledProcessError

        mock_run.side_effect = CalledProcessError(1, "find")

        items = mover.list_dir("/media/nonexistent")

        assert items == []


class TestCategoryMappings:
    def test_category_mappings_complete(self):
        expected_categories = {
            "documentaries",
            "movies",
            "shows",
            "stand-up",
            "tv-programs",
            "tv-shows",
        }
        assert set(CATEGORY_MAPPINGS.keys()) == expected_categories
        assert set(CATEGORY_MAPPINGS.values()) == expected_categories
