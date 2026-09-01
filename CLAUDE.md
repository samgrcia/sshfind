# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
poetry install           # set up virtualenv and install deps (incl. dev)
poetry run sshfind <query>   # run the CLI
poetry run pytest tests/ -v  # run all tests
pipx install . --force   # install globally after changes
```

CLI flags: `--regex` (`-r`) for regex mode, `--all` (`-a`) to include `Host *` blocks.

## Architecture

Everything lives in `sshfind.py`. The flow is:

1. **Parsing** — `parse_all_configs()` starts from `~/.ssh/config` and calls `parse_config_file()` recursively. Each `Include` directive is glob-expanded relative to the parent file's directory (tilde expanded first). The `visited` set prevents cycles. Each `Host` or `Match` block becomes a dict:
   ```python
   {"type": "Host"|"Match", "patterns": [...], "options": {...}, "source": "/path/to/file"}
   # Match blocks also carry: "match_conditions": "<raw rest of Match line>"
   ```

2. **Host line parsing** — `_parse_host_line()` handles a non-standard inline format found in the user's configs (`Host foo Hostname 1.2.3.4` on one line). It scans tokens left-to-right: anything before a known `SSH_OPTION_KEYWORDS` token is a host pattern; once a keyword is hit, remaining tokens are consumed as `key value` pairs.

3. **Match block parsing** — `_extract_match_host_patterns()` extracts only the `Host <pattern>` part from a `Match` line, stopping at other Match criteria keywords (`localnetwork`, `user`, etc.) defined in `MATCH_KEYWORDS`.

4. **Matching** — `_block_matches()` does a case-insensitive substring search (or regex with `-r`) against each pattern in the block. `Host *` blocks are excluded unless `--all` is passed.

5. **Display** — `display_results_rich()` renders two separate `rich` tables: one for `Host` blocks (cyan), one for `Match Host` blocks (yellow). Match conditions are shown dimmed inside the Options column to avoid blowing out the table width. Falls back to `display_results_plain()` if `rich` is not installed.

## Key edge cases

- `SSH_OPTION_KEYWORDS` is what separates host patterns from inline options on a `Host` line — if a new SSH option is missing from this set, it will be misread as a pattern.
- First-occurrence-wins for duplicate options (matches OpenSSH behavior).
- Swap files (`.swp`) in `config.d/` are silently skipped by the `glob` — Python's `*` doesn't match dotfiles.
