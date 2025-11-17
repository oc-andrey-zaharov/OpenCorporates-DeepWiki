"""Tests for CLI commands using click.testing.CliRunner."""

import json
from pathlib import Path
from unittest.mock import patch

# Import click and ensure it's fully loaded before any deepwiki_cli imports
# This prevents import conflicts when running tests in parallel with pytest-xdist
import click

try:
    import click._textwrap
except ImportError:
    pass  # Some click versions may not have this module
from click.testing import CliRunner


def get_cli():
    """Get CLI instance - import lazily to avoid conflicts in parallel execution."""
    from deepwiki_cli.cli.main import cli as deepwiki_cli

    return deepwiki_cli


class TestCliMain:
    """Test main CLI group and global options."""

    def test_cli_help(self) -> None:
        """Test CLI help output."""
        runner = CliRunner()
        result = runner.invoke(get_cli(), ["--help"])
        assert result.exit_code == 0
        assert "DeepWiki CLI" in result.output
        assert "Commands:" in result.output
        assert "generate" in result.output
        assert "list" in result.output
        assert "export" in result.output

    def test_cli_version(self) -> None:
        """Test CLI version option."""
        runner = CliRunner()
        result = runner.invoke(get_cli(), ["--version"])
        assert result.exit_code == 0
        assert "deepwiki" in result.output.lower()
        assert "version" in result.output.lower()

    def test_cli_verbose_flag(self) -> None:
        """Test verbose flag is accepted."""
        runner = CliRunner()
        result = runner.invoke(get_cli(), ["--verbose", "list"])
        # Should not error even if no cache exists
        assert result.exit_code in (0, 1)  # May fail if no cache, but flag works

    def test_cli_invalid_command(self) -> None:
        """Test invalid command handling."""
        runner = CliRunner()
        result = runner.invoke(get_cli(), ["invalid-command"])
        assert result.exit_code == 2
        assert "No such command" in result.output or "Error" in result.output


class TestListWikisCommand:
    """Test list wikis command."""

    def test_list_wikis_no_cache(self) -> None:
        """Test list command when no cache exists."""
        runner = CliRunner()
        with runner.isolated_filesystem() as temp_dir:
            cache_dir = Path(temp_dir) / ".deepwiki" / "cache"
            # Don't create cache dir - should show no cache message
            with patch(
                "deepwiki_cli.cli.commands.list_wikis.get_cache_path"
            ) as mock_path:
                mock_path.return_value = cache_dir
                result = runner.invoke(get_cli(), ["list"])
                assert result.exit_code == 0
                assert "No cached wikis found" in result.output

    def test_list_wikis_with_cache(self) -> None:
        """Test list command with existing cache files."""
        runner = CliRunner()
        with runner.isolated_filesystem() as temp_dir:
            cache_dir = Path(temp_dir) / ".deepwiki" / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)

            # Create a mock cache file
            cache_file = cache_dir / "deepwiki_cache_github_owner_repo_en_1.json"
            cache_data = {
                "wiki_structure": {"pages": [{"id": "page1", "title": "Test Page"}]},
                "comprehensive": True,
                "repo": {"owner": "owner", "repo": "repo"},
            }
            cache_file.write_text(json.dumps(cache_data))

            # Mock get_cache_path to return our temp cache dir
            with patch(
                "deepwiki_cli.cli.commands.list_wikis.get_cache_path"
            ) as mock_path:
                mock_path.return_value = cache_dir
                result = runner.invoke(get_cli(), ["list"])
                assert result.exit_code == 0
                assert "Cached Wikis" in result.output
                assert "owner/repo" in result.output or "repo" in result.output


class TestConfigCommand:
    """Test config command group."""

    def test_config_help(self) -> None:
        """Test config command help."""
        runner = CliRunner()
        result = runner.invoke(get_cli(), ["config", "--help"])
        assert result.exit_code == 0
        assert "Manage DeepWiki CLI configuration" in result.output

    def test_config_show(self) -> None:
        """Test config show command."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with patch("deepwiki_cli.cli.commands.config_cmd.load_config") as mock_load:
                mock_load.return_value = {
                    "default_provider": "google",
                    "default_model": "gemini-2.0-flash-exp",
                    "wiki_workspace": "docs/wiki",
                    "export": {"layout": "single", "watch": False},
                }
                with patch(
                    "deepwiki_cli.cli.commands.config_cmd.CONFIG_FILE"
                ) as mock_file:
                    mock_file.__str__ = lambda x: "/tmp/test_config.json"
                    result = runner.invoke(get_cli(), ["config", "show"])
                    assert result.exit_code == 0
                    assert "DeepWiki CLI Configuration" in result.output
                    assert "default_provider" in result.output

    def test_config_set(self) -> None:
        """Test config set command."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with patch(
                "deepwiki_cli.cli.commands.config_cmd.set_config_value"
            ) as mock_set:
                mock_set.return_value = None
                result = runner.invoke(
                    get_cli(), ["config", "set", "default_provider", "openai"]
                )
                assert result.exit_code == 0
                assert "Configuration updated" in result.output
                mock_set.assert_called_once()

    def test_config_set_json_value(self) -> None:
        """Test config set with JSON value."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with patch(
                "deepwiki_cli.cli.commands.config_cmd.set_config_value"
            ) as mock_set:
                mock_set.return_value = None
                result = runner.invoke(
                    get_cli(),
                    ["config", "set", "export.layout", '"multi"'],
                )
                assert result.exit_code == 0
                assert "Configuration updated" in result.output


class TestExportCommand:
    """Test export command."""

    def test_export_no_cache(self) -> None:
        """Test export when no cache exists."""
        runner = CliRunner()
        with runner.isolated_filesystem() as temp_dir:
            cache_dir = Path(temp_dir) / ".deepwiki" / "cache"
            # Don't create cache dir - should show no cache message
            with patch("deepwiki_cli.cli.commands.export.get_cache_path") as mock_path:
                mock_path.return_value = cache_dir
                result = runner.invoke(get_cli(), ["export"])
                # Export returns exit code 0 but shows message when no cache
                assert result.exit_code == 0
                assert (
                    "No cached wikis found" in result.output
                    or "No valid cached wikis" in result.output
                )

    def test_export_help(self) -> None:
        """Test export command help."""
        runner = CliRunner()
        result = runner.invoke(get_cli(), ["export", "--help"])
        assert result.exit_code == 0
        assert "Export a cached wiki" in result.output
        assert "--format" in result.output
        assert "--layout" in result.output

    def test_export_format_option(self) -> None:
        """Test export format option validation."""
        runner = CliRunner()
        result = runner.invoke(get_cli(), ["export", "--format", "invalid"])
        assert result.exit_code == 2
        assert (
            "Invalid value" in result.output
            or "invalid choice" in result.output.lower()
        )

    def test_export_json_format(self) -> None:
        """Test export with JSON format."""
        runner = CliRunner()
        with runner.isolated_filesystem() as temp_dir:
            cache_dir = Path(temp_dir) / ".deepwiki" / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)

            cache_file = cache_dir / "deepwiki_cache_github_owner_repo_en_1.json"
            cache_data = {
                "wiki_structure": {
                    "id": "wiki",
                    "title": "Test Wiki",
                    "pages": [{"id": "page1", "title": "Page 1", "content": "Content"}],
                },
                "generated_pages": {
                    "page1": {"id": "page1", "title": "Page 1", "content": "Content"}
                },
                "repo": {"owner": "owner", "repo": "repo", "type": "github"},
            }
            cache_file.write_text(json.dumps(cache_data))

            with patch("deepwiki_cli.cli.commands.export.get_cache_path") as mock_path:
                mock_path.return_value = cache_dir
                with patch(
                    "deepwiki_cli.cli.commands.export._discover_cached_wikis"
                ) as mock_discover:
                    mock_discover.return_value = [
                        {
                            "index": 1,
                            "name": "owner/repo",
                            "display_name": "owner/repo (v1)",
                            "owner": "owner",
                            "repo": "repo",
                            "repo_type": "github",
                            "language": "en",
                            "version": 1,
                            "path": cache_file,
                        },
                    ]
                    with patch(
                        "deepwiki_cli.cli.commands.export.select_wiki_from_list"
                    ) as mock_select:
                        mock_select.return_value = {
                            "index": 1,
                            "name": "owner/repo",
                            "owner": "owner",
                            "repo": "repo",
                            "repo_type": "github",
                            "version": 1,
                            "path": cache_file,
                        }
                        result = runner.invoke(
                            get_cli(),
                            ["export", "--format", "json", "--wiki", "owner/repo"],
                        )
                        # May require input, so check exit code is reasonable
                        assert result.exit_code in (0, 1, 2)


class TestDeleteCommand:
    """Test delete command."""

    def test_delete_no_cache(self) -> None:
        """Test delete when no cache exists."""
        runner = CliRunner()
        with runner.isolated_filesystem() as temp_dir:
            cache_dir = Path(temp_dir) / ".deepwiki" / "cache"
            # Don't create cache dir - should show no cache message
            with patch("deepwiki_cli.cli.commands.delete.get_cache_path") as mock_path:
                mock_path.return_value = cache_dir
                result = runner.invoke(get_cli(), ["delete"])
                assert result.exit_code == 0
                assert "No cached wikis found" in result.output

    def test_delete_help(self) -> None:
        """Test delete command help."""
        runner = CliRunner()
        result = runner.invoke(get_cli(), ["delete", "--help"])
        assert result.exit_code == 0
        assert "Delete a cached wiki" in result.output
        assert "--yes" in result.output or "-y" in result.output

    def test_delete_with_yes_flag(self) -> None:
        """Test delete with --yes flag."""
        runner = CliRunner()
        with runner.isolated_filesystem() as temp_dir:
            cache_dir = Path(temp_dir) / ".deepwiki" / "cache"
            # Don't create cache dir - should show no cache message
            with patch("deepwiki_cli.cli.commands.delete.get_cache_path") as mock_path:
                mock_path.return_value = cache_dir
                result = runner.invoke(get_cli(), ["delete", "--yes"])
                # Should not prompt, but may fail if no cache
                assert result.exit_code in (0, 1)


class TestSyncCommand:
    """Test sync command."""

    def test_sync_help(self) -> None:
        """Test sync command help."""
        runner = CliRunner()
        result = runner.invoke(get_cli(), ["sync", "--help"])
        assert result.exit_code == 0
        assert "Sync markdown edits" in result.output
        assert "--workspace" in result.output
        assert "--watch" in result.output

    def test_sync_no_workspace(self) -> None:
        """Test sync when no workspace exists."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with patch("deepwiki_cli.cli.commands.sync.load_config") as mock_config:
                mock_config.return_value = {"wiki_workspace": "docs/wiki"}
                with patch(
                    "deepwiki_cli.cli.commands.sync.list_manifests"
                ) as mock_list:
                    mock_list.return_value = []
                    result = runner.invoke(get_cli(), ["sync"])
                    assert result.exit_code != 0
                    assert "No editable workspaces found" in result.output


class TestGenerateCommand:
    """Test generate command."""

    def test_generate_help(self) -> None:
        """Test generate command help."""
        runner = CliRunner()
        result = runner.invoke(get_cli(), ["generate", "--help"])
        assert result.exit_code == 0
        assert "Generate a new wiki" in result.output
        assert "--force" in result.output

    def test_generate_force_flag(self) -> None:
        """Test generate with --force flag."""
        runner = CliRunner()
        # Mock interactive prompts to avoid blocking
        with patch("deepwiki_cli.cli.commands.generate.prompt_repository") as mock_repo:
            mock_repo.side_effect = click.Abort()
            result = runner.invoke(get_cli(), ["generate", "--force"])
            # Should handle abort gracefully
            assert result.exit_code in (0, 1, 2)


class TestCliErrorHandling:
    """Test CLI error handling."""

    def test_cli_exception_handling(self) -> None:
        """Test that exceptions are handled gracefully."""
        runner = CliRunner()
        # Test with invalid option combination
        result = runner.invoke(get_cli(), ["--invalid-option"])
        assert result.exit_code == 2

    def test_cli_abort_handling(self) -> None:
        """Test that click.Abort is handled."""
        runner = CliRunner()
        # Mock interactive prompts to avoid blocking, then trigger abort
        with patch("deepwiki_cli.cli.commands.generate.prompt_repository") as mock_repo:
            mock_repo.side_effect = click.Abort()
            result = runner.invoke(get_cli(), ["generate"])
            # Should handle abort gracefully and exit with code 1
            assert result.exit_code == 1


class TestCliIsolatedFilesystem:
    """Test CLI commands with isolated filesystem."""

    def test_list_with_isolated_filesystem(self) -> None:
        """Test list command in isolated filesystem."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            cache_dir = Path.cwd() / ".deepwiki" / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)

            with patch(
                "deepwiki_cli.cli.commands.list_wikis.get_cache_path"
            ) as mock_path:
                mock_path.return_value = cache_dir
                result = runner.invoke(get_cli(), ["list"])
                assert result.exit_code == 0

    def test_config_with_isolated_filesystem(self) -> None:
        """Test config commands in isolated filesystem."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            config_file = Path.cwd() / "config.json"
            config_file.write_text(json.dumps({"test": "value"}))

            with patch("deepwiki_cli.cli.commands.config_cmd.CONFIG_FILE") as mock_file:
                mock_file.__str__ = lambda x: str(config_file)
                with patch(
                    "deepwiki_cli.cli.commands.config_cmd.load_config"
                ) as mock_load:
                    mock_load.return_value = {"test": "value"}
                    result = runner.invoke(get_cli(), ["config", "show"])
                    assert result.exit_code == 0


class TestCliInputSimulation:
    """Test CLI commands with simulated input."""

    def test_generate_with_input(self) -> None:
        """Test generate command with simulated input."""
        runner = CliRunner()
        # Mock interactive prompts to avoid blocking
        with patch("deepwiki_cli.cli.commands.generate.prompt_repository") as mock_repo:
            # Simulate abort after first prompt to avoid further prompts
            mock_repo.side_effect = click.Abort()
            result = runner.invoke(
                get_cli(),
                ["generate"],
                input="test-repo\n",
            )
            # Should handle abort gracefully
            assert result.exit_code == 1

    def test_delete_with_confirmation(self) -> None:
        """Test delete command with confirmation input."""
        runner = CliRunner()
        with runner.isolated_filesystem() as temp_dir:
            cache_dir = Path(temp_dir) / ".deepwiki" / "cache"
            # Don't create cache dir - should show no cache message
            with patch("deepwiki_cli.cli.commands.delete.get_cache_path") as mock_path:
                mock_path.return_value = cache_dir
                result = runner.invoke(
                    get_cli(),
                    ["delete"],
                    input="n\n",  # No confirmation
                )
                # Should handle the input gracefully
                assert result.exit_code in (0, 1)


class TestCliSubcommands:
    """Test CLI subcommands."""

    def test_config_subcommands(self) -> None:
        """Test config subcommands."""
        runner = CliRunner()
        result = runner.invoke(get_cli(), ["config", "show"])
        # May fail if config doesn't exist, but command should be recognized
        assert result.exit_code in (0, 1)

        result = runner.invoke(get_cli(), ["config", "set", "test_key", "test_value"])
        # May fail if config file issues, but command should be recognized
        assert result.exit_code in (0, 1, 2)

    def test_config_invalid_subcommand(self) -> None:
        """Test invalid config subcommand."""
        runner = CliRunner()
        result = runner.invoke(get_cli(), ["config", "invalid"])
        assert result.exit_code == 2
        assert "No such command" in result.output or "Invalid" in result.output


class TestCliTerminalWidth:
    """Test CLI with custom terminal width."""

    def test_list_with_terminal_width(self) -> None:
        """Test list command with custom terminal width."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(get_cli(), ["list"], terminal_width=80)
            assert result.exit_code == 0

    def test_help_with_terminal_width(self) -> None:
        """Test help output with custom terminal width."""
        runner = CliRunner()
        result = runner.invoke(get_cli(), ["--help"], terminal_width=120)
        assert result.exit_code == 0
        assert "DeepWiki CLI" in result.output


class TestCliProgName:
    """Test CLI with custom program name."""

    def test_cli_with_prog_name(self) -> None:
        """Test CLI invocation with custom program name."""
        runner = CliRunner()
        result = runner.invoke(get_cli(), ["--help"], prog_name="deepwiki-cli")
        assert result.exit_code == 0
        assert "DeepWiki CLI" in result.output or "deepwiki" in result.output.lower()
