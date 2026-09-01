import pytest
from pathlib import Path

from sshfind import (
    _block_matches,
    _extract_match_host_patterns,
    _parse_host_line,
    _short_source,
    parse_config_file,
)


# ---------------------------------------------------------------------------
# _parse_host_line
# ---------------------------------------------------------------------------

class TestParseHostLine:
    def test_single_pattern(self):
        patterns, options = _parse_host_line("myserver")
        assert patterns == ["myserver"]
        assert options == {}

    def test_wildcard_patterns(self):
        patterns, options = _parse_host_line("web* api*")
        assert patterns == ["web*", "api*"]
        assert options == {}

    def test_inline_single_option(self):
        patterns, options = _parse_host_line("myserver Hostname 192.168.1.1")
        assert patterns == ["myserver"]
        assert options == {"Hostname": "192.168.1.1"}

    def test_inline_multiple_options(self):
        patterns, options = _parse_host_line("myserver User admin Port 22")
        assert patterns == ["myserver"]
        assert options == {"User": "admin", "Port": "22"}

    def test_option_keyword_case_insensitive(self):
        patterns, options = _parse_host_line("myserver hostname 10.0.0.1")
        assert patterns == ["myserver"]
        assert options == {"hostname": "10.0.0.1"}

    def test_empty_string(self):
        patterns, options = _parse_host_line("")
        assert patterns == []
        assert options == {}

    def test_wildcard_only(self):
        patterns, options = _parse_host_line("*")
        assert patterns == ["*"]
        assert options == {}


# ---------------------------------------------------------------------------
# _extract_match_host_patterns
# ---------------------------------------------------------------------------

class TestExtractMatchHostPatterns:
    def test_host_with_localnetwork(self):
        result = _extract_match_host_patterns("Host web* localnetwork 192.168.0.0/24")
        assert result == ["web*"]

    def test_host_only(self):
        result = _extract_match_host_patterns("Host myserver")
        assert result == ["myserver"]

    def test_all_criterion(self):
        result = _extract_match_host_patterns("all")
        assert result == []

    def test_multiple_host_criteria(self):
        # "Match Host pat1 Host pat2" is unusual but the parser handles it
        result = _extract_match_host_patterns("Host web* Host api*")
        assert result == ["web*", "api*"]

    def test_wildcard_host(self):
        result = _extract_match_host_patterns("Host * localnetwork 10.0.0.0/8")
        assert result == ["*"]


# ---------------------------------------------------------------------------
# parse_config_file
# ---------------------------------------------------------------------------

class TestParseConfigFile:
    def test_missing_file_returns_empty(self, tmp_path):
        result = parse_config_file(tmp_path / "nonexistent")
        assert result == []

    def test_basic_host_block(self, tmp_path):
        config = tmp_path / "config"
        config.write_text(
            "Host myserver\n"
            "  Hostname 10.0.0.1\n"
            "  User deploy\n"
            "  Port 2222\n"
        )
        blocks = parse_config_file(config)
        assert len(blocks) == 1
        b = blocks[0]
        assert b["type"] == "Host"
        assert b["patterns"] == ["myserver"]
        assert b["options"]["Hostname"] == "10.0.0.1"
        assert b["options"]["User"] == "deploy"
        assert b["options"]["Port"] == "2222"

    def test_multiple_host_blocks(self, tmp_path):
        config = tmp_path / "config"
        config.write_text(
            "Host alpha\n"
            "  User alice\n"
            "\n"
            "Host beta\n"
            "  User bob\n"
        )
        blocks = parse_config_file(config)
        assert len(blocks) == 2
        assert blocks[0]["patterns"] == ["alpha"]
        assert blocks[1]["patterns"] == ["beta"]

    def test_match_block(self, tmp_path):
        config = tmp_path / "config"
        config.write_text(
            "Match Host staging* localnetwork 10.0.0.0/8\n"
            "  ProxyCommand ssh bastion nc %h %p\n"
        )
        blocks = parse_config_file(config)
        assert len(blocks) == 1
        b = blocks[0]
        assert b["type"] == "Match"
        assert b["patterns"] == ["staging*"]
        assert b["options"]["ProxyCommand"] == "ssh bastion nc %h %p"

    def test_inline_option_on_host_line(self, tmp_path):
        config = tmp_path / "config"
        config.write_text("Host myserver Hostname 10.0.0.5\n")
        blocks = parse_config_file(config)
        assert len(blocks) == 1
        assert blocks[0]["patterns"] == ["myserver"]
        assert blocks[0]["options"]["Hostname"] == "10.0.0.5"

    def test_comments_and_blank_lines_ignored(self, tmp_path):
        config = tmp_path / "config"
        config.write_text(
            "# Top comment\n"
            "\n"
            "Host myserver\n"
            "  # inline comment\n"
            "  User alice\n"
        )
        blocks = parse_config_file(config)
        assert len(blocks) == 1
        assert blocks[0]["options"] == {"User": "alice"}

    def test_first_occurrence_wins(self, tmp_path):
        config = tmp_path / "config"
        config.write_text(
            "Host myserver\n"
            "  User first\n"
            "  User second\n"
        )
        blocks = parse_config_file(config)
        assert blocks[0]["options"]["User"] == "first"

    def test_include_relative_path(self, tmp_path):
        extra = tmp_path / "extra"
        extra.write_text("Host extra\n  Port 22\n")
        config = tmp_path / "config"
        config.write_text("Include extra\n")
        blocks = parse_config_file(config)
        assert len(blocks) == 1
        assert blocks[0]["patterns"] == ["extra"]

    def test_include_glob(self, tmp_path):
        conf_d = tmp_path / "conf.d"
        conf_d.mkdir()
        (conf_d / "alpha").write_text("Host alpha\n  User a\n")
        (conf_d / "beta").write_text("Host beta\n  User b\n")
        config = tmp_path / "config"
        config.write_text("Include conf.d/*\n")
        blocks = parse_config_file(config)
        patterns = [b["patterns"][0] for b in blocks]
        assert sorted(patterns) == ["alpha", "beta"]

    def test_include_tilde_path(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        extra = tmp_path / "extra_config"
        extra.write_text("Host remote\n  User ops\n")
        config = tmp_path / "config"
        config.write_text("Include ~/extra_config\n")
        blocks = parse_config_file(config)
        assert len(blocks) == 1
        assert blocks[0]["patterns"] == ["remote"]

    def test_cycle_detection(self, tmp_path):
        config = tmp_path / "config"
        config.write_text(f"Include {config}\nHost direct\n  User u\n")
        blocks = parse_config_file(config)
        assert len(blocks) == 1

    def test_dotfiles_not_matched_by_glob(self, tmp_path):
        conf_d = tmp_path / "conf.d"
        conf_d.mkdir()
        (conf_d / "server").write_text("Host server\n  User u\n")
        (conf_d / ".swp").write_text("garbage\x00data")
        config = tmp_path / "config"
        config.write_text("Include conf.d/*\n")
        blocks = parse_config_file(config)
        assert len(blocks) == 1
        assert blocks[0]["patterns"] == ["server"]


# ---------------------------------------------------------------------------
# _block_matches
# ---------------------------------------------------------------------------

class TestBlockMatches:
    def _block(self, *patterns):
        return {"type": "Host", "patterns": list(patterns), "options": {}, "source": ""}

    def test_substring_match(self):
        assert _block_matches(self._block("myserver"), "server", False)

    def test_substring_case_insensitive(self):
        assert _block_matches(self._block("MyServer"), "myserver", False)

    def test_substring_no_match(self):
        assert not _block_matches(self._block("alpha"), "beta", False)

    def test_matches_any_pattern(self):
        assert _block_matches(self._block("alpha", "beta"), "beta", False)

    def test_regex_match(self):
        assert _block_matches(self._block("webserver01"), r"web.*\d+", True)

    def test_regex_no_match(self):
        assert not _block_matches(self._block("webserver"), r"^api", True)

    def test_regex_case_insensitive(self):
        assert _block_matches(self._block("WebServer"), r"webserver", True)

    def test_empty_patterns(self):
        assert not _block_matches(self._block(), "anything", False)


# ---------------------------------------------------------------------------
# _short_source
# ---------------------------------------------------------------------------

class TestShortSource:
    def test_strips_home_and_ssh_prefix(self):
        home = str(Path.home())
        result = _short_source(f"{home}/.ssh/config.d/myfile")
        assert result == "config.d/myfile"

    def test_keeps_tilde_for_non_ssh_paths(self):
        home = str(Path.home())
        result = _short_source(f"{home}/.orbstack/ssh/config")
        assert result == "~/.orbstack/ssh/config"
