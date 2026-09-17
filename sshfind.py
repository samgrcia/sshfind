#!/usr/bin/env python3
"""sshfind - Search SSH configurations by host pattern."""

import argparse
import glob
import os
import re
import sys
from pathlib import Path

try:
    from rich.console import Console
    from rich.table import Table
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# Match criteria keywords (other than Host) — used to delimit host patterns on a Match line
MATCH_KEYWORDS = {
    "all", "canonical", "exec", "localnetwork", "localuser", "originalhost",
    "user", "host", "address", "tagged",
}

# Valid ssh_config option keywords — detected on a Host line for inline option syntax.
# e.g. "Host myserver Hostname 1.2.3.4"  →  pattern=myserver, option Hostname=1.2.3.4
SSH_OPTION_KEYWORDS = {
    "addressfamily", "batchmode", "bindaddress", "canonicaldomains",
    "canonicalizefallbacklocal", "canonicalizehostname", "canonicalizemaxdots",
    "canonicalizepermittedcnames", "certificatefile", "checkhostip",
    "ciphers", "compression", "connectionattempts", "connecttimeout",
    "controlmaster", "controlpath", "controlpersist", "dynamicforward",
    "escapechar", "exitonforwardfailure", "fingerprinthash", "forwardagent",
    "forwardx11", "forwardx11timeout", "forwardx11trusted", "gatewayports",
    "globalknownhostsfile", "gssapiauthentication", "gssapidelegatecredentials",
    "hashknownhosts", "hostbasedauthentication", "hostkeyalgorithms",
    "hostkeyalias", "hostname", "identitiesonly", "identityagent",
    "identityfile", "ignoreunknown", "ipqos", "kbdinteractiveauthentication",
    "kexalgorithms", "localcommand", "localforward", "loglevel", "macs",
    "nohostauthenticationforlocalhost", "numberofpasswordprompts",
    "passwordauthentication", "permitlocalcommand", "pkcs11provider", "port",
    "preferredauthentications", "proxycommand", "proxyjump", "proxyusefdpass",
    "pubkeyauthentication", "rekeylimit", "remotecommand", "remoteforward",
    "requesttty", "revokedhostkeys", "sendenv", "serveralivecountmax",
    "serveraliveinterval", "setenv", "stricthostkeychecking", "tcpkeepalive",
    "tunnel", "tunneldevice", "updatehostkeys", "user", "userknownhostsfile",
    "visualhostkey", "xauthlocation",
}


def _parse_host_line(rest: str) -> tuple[list[str], list[tuple[str, str]]]:
    """Parse a Host line value into host patterns and optional inline options."""
    tokens = rest.split()
    patterns: list[str] = []
    options: list[tuple[str, str]] = []
    i = 0
    while i < len(tokens):
        if tokens[i].lower() in SSH_OPTION_KEYWORDS:
            # remaining tokens are key-value pairs
            while i + 1 < len(tokens):
                options.append((tokens[i], tokens[i + 1]))
                i += 2
            break
        patterns.append(tokens[i])
        i += 1
    return patterns, options


def _extract_match_host_patterns(conditions: str) -> list[str]:
    """Extract host patterns from a Match line (everything after the 'Match' keyword)."""
    tokens = conditions.split()
    patterns = []
    i = 0
    while i < len(tokens):
        if tokens[i].lower() == "host":
            i += 1
            while i < len(tokens) and tokens[i].lower() not in MATCH_KEYWORDS:
                patterns.append(tokens[i])
                i += 1
        else:
            i += 1
    return patterns


def parse_config_file(path: str | Path, visited: set | None = None) -> list[dict]:
    """Parse an SSH config file, resolving Include directives recursively."""
    if visited is None:
        visited = set()

    path = Path(path).expanduser().resolve()
    if path in visited or not path.exists() or not path.is_file():
        return []
    visited.add(path)

    blocks = []
    current_block: dict | None = None

    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        keyword, _, rest = stripped.partition(" ")
        keyword_lower = keyword.lower()
        rest = rest.strip()

        if keyword_lower == "include":
            if current_block:
                blocks.append(current_block)
                current_block = None
            include_pattern = os.path.expanduser(rest)
            if not os.path.isabs(include_pattern):
                include_pattern = str(path.parent / include_pattern)
            for include_file in sorted(glob.glob(include_pattern)):
                blocks.extend(parse_config_file(include_file, visited))

        elif keyword_lower == "host":
            if current_block:
                blocks.append(current_block)
            patterns, inline_options = _parse_host_line(rest)
            current_block = {
                "type": "Host",
                "patterns": patterns,
                "options": inline_options,
                "source": str(path),
            }

        elif keyword_lower == "match":
            if current_block:
                blocks.append(current_block)
            host_patterns = _extract_match_host_patterns(rest)
            current_block = {
                "type": "Match",
                "patterns": host_patterns,
                "match_conditions": rest,
                "options": [],
                "source": str(path),
            }

        elif current_block is not None:
            current_block["options"].append((keyword, rest))

    if current_block:
        blocks.append(current_block)

    return blocks


def parse_all_configs() -> list[dict]:
    """Parse ~/.ssh/config and all included files."""
    return parse_config_file("~/.ssh/config")


def _block_matches(block: dict, query: str, use_regex: bool) -> bool:
    """Return True if any host pattern in the block matches the query."""
    for pattern in block["patterns"]:
        if use_regex:
            if re.search(query, pattern, re.IGNORECASE):
                return True
        else:
            if query.lower() in pattern.lower():
                return True
    return False


def _short_source(source: str) -> str:
    """Shorten an absolute config file path for display."""
    home = str(Path.home())
    source = source.replace(home, "~")
    ssh_prefix = "~/.ssh/"
    if source.startswith(ssh_prefix):
        source = source[len(ssh_prefix):]
    return source


def _options_cell(block: dict) -> str:
    """Format a block's options as a multi-line rich string."""
    if not block["options"]:
        return "[dim](no options)[/dim]"
    return "\n".join(f"[green]{k}[/green] {v}" for k, v in block["options"])


def _host_cell(block: dict) -> str:
    """Format the host pattern(s) and source path for the Host column."""
    patterns = "\n".join(block["patterns"])
    source = f"\n[dim]{_short_source(block['source'])}[/dim]"
    return patterns + source


def _match_cell(block: dict) -> str:
    """Format the host pattern(s) and source path for the Match Host column."""
    patterns = "\n".join(block["patterns"]) if block["patterns"] else "[dim]*[/dim]"
    source = _short_source(block["source"])
    return f"{patterns}\n[dim]{source}[/dim]"


def _match_options_cell(block: dict) -> str:
    """Format the options and Match conditions for the Options column of a Match block."""
    lines = []
    conditions = block.get("match_conditions", "")
    if conditions:
        lines.append(f"[dim]match {conditions}[/dim]")
    lines.extend(f"[green]{k}[/green] {v}" for k, v in block["options"])
    return "\n".join(lines) if lines else "[dim](no options)[/dim]"


def display_results_rich(matches: list[dict]) -> None:
    console = Console()

    host_blocks = [b for b in matches if b["type"] == "Host"]
    match_blocks = [b for b in matches if b["type"] == "Match"]

    if host_blocks:
        table = Table(box=box.ROUNDED, show_header=True, header_style="bold magenta", show_lines=True)
        table.add_column("Host", style="cyan bold", no_wrap=True)
        table.add_column("Options")
        for block in host_blocks:
            table.add_row(_host_cell(block), _options_cell(block))
        console.print(table)
        console.print()

    if match_blocks:
        table = Table(
            title="Match Host",
            title_style="bold yellow",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
            show_lines=True,
        )
        table.add_column("Match Host", style="yellow bold", no_wrap=True)
        table.add_column("Options")
        for block in match_blocks:
            table.add_row(_match_cell(block), _match_options_cell(block))
        console.print(table)
        console.print()


def display_results_plain(matches: list[dict]) -> None:
    sep = "-" * 60
    host_blocks = [b for b in matches if b["type"] == "Host"]
    match_blocks = [b for b in matches if b["type"] == "Match"]

    def _print_table(blocks: list[dict], col1: str) -> None:
        print(f"  {col1:<30}  Options")
        print(sep)
        for block in blocks:
            patterns = " ".join(block["patterns"])
            options = block["options"]
            first_opt = f"{options[0][0]} {options[0][1]}" if options else "(no options)"
            print(f"  {patterns:<30}  {first_opt}")
            for k, v in options[1:]:
                print(f"  {'':<30}  {k} {v}")
            print(f"  {_short_source(block['source'])}")
            print()

    if host_blocks:
        print(sep)
        _print_table(host_blocks, "Host")

    if match_blocks:
        print(sep)
        print("  Match Host")
        print(sep)
        _print_table(match_blocks, "Match Host")


def display_results_simple(matches: list[dict]) -> None:
    """Print each block as valid, copy-pasteable ssh_config text."""
    for i, block in enumerate(matches):
        if i > 0:
            print()
        if block["type"] == "Host":
            name = " ".join(block["patterns"]) if block["patterns"] else "*"
            print(f"Host {name}")
        else:
            print(f"Match {block.get('match_conditions', '')}".rstrip())
        for k, v in block["options"]:
            print(f"    {k} {v}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="sshfind",
        description=(
            "Search SSH host configurations. Reads ~/.ssh/config and "
            "recursively follows every Include directive it contains."
        ),
    )
    parser.add_argument("query", help="String to search for in Host patterns")
    parser.add_argument(
        "-r", "--regex",
        action="store_true",
        help="Treat the query as a regular expression",
    )
    parser.add_argument(
        "-a", "--all",
        action="store_true",
        dest="include_wildcard",
        help="Include 'Host *' catch-all blocks in results",
    )
    parser.add_argument(
        "-s", "--simple",
        action="store_true",
        help="Print plain copy-pasteable ssh_config blocks instead of a table",
    )
    args = parser.parse_args()

    if args.regex:
        try:
            re.compile(args.query)
        except re.error as e:
            print(f"sshfind: invalid regular expression: {e}", file=sys.stderr)
            sys.exit(2)

    blocks = parse_all_configs()

    matches = [
        b for b in blocks
        if _block_matches(b, args.query, args.regex)
        and (args.include_wildcard or b["patterns"] != ["*"])
    ]

    if not matches:
        print(f"No results for '{args.query}'.")
        sys.exit(1)

    if args.simple:
        display_results_simple(matches)
    elif RICH_AVAILABLE:
        display_results_rich(matches)
    else:
        display_results_plain(matches)


if __name__ == "__main__":
    main()
