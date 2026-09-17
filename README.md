# sshfind

Search SSH host configurations by pattern.

`sshfind` reads `~/.ssh/config` and recursively follows every `Include` directive it contains. It displays the SSH options of every `Host` (and `Match Host`) block whose name matches the query.

[![asciicast](https://asciinema.org/a/rjutVWHjPo53xVCB.svg)](https://asciinema.org/a/rjutVWHjPo53xVCB)

## Usage

```
sshfind <query> [-r] [-a] [-s]
```

| Argument          | Description                                                        |
| ----------------- | ------------------------------------------------------------------ |
| `query`           | String to search for in Host patterns (case-insensitive substring) |
| `-r`, `--regex`   | Treat the query as a regular expression                            |
| `-a`, `--all`     | Include `Host *` catch-all blocks in results                       |
| `-s`, `--simple`  | Print plain, copy-pasteable `ssh_config` blocks instead of a table |

Returns exit code `1` when no results are found.

## Examples

```bash
# Find all hosts matching "prod"
sshfind prod

# Find hosts starting with "web" using a regex
sshfind '^web' --regex

# Include the global Host * block
sshfind prod --all

# Simple, copy-pasteable output
sshfind prod --simple
```

### Output

`Host` blocks and `Match Host` blocks are displayed in separate tables.

```
╭──────────────┬────────────────────────────────╮
│ Host         │ Options                        │
├──────────────┼────────────────────────────────┤
│ prod-server  │ Hostname 10.0.1.42             │
│ config.d/prod│ User deploy                    │
│              │ IdentityFile ~/.ssh/id_ed25519 │
╰──────────────┴────────────────────────────────╯
```

With `--simple`, each block is printed as valid `ssh_config` text you can copy straight into a config file, with no table formatting:

```
Host prod-server
    Hostname 10.0.1.42
    User deploy
    IdentityFile ~/.ssh/id_ed25519
```

## Installation

Requires Python 3.9+.

**With pipx** (recommended for CLI tools — isolated environment):

```bash
pipx install git+https://github.com/samgrcia/sshfind.git
```

**With pip**:

```bash
pip install git+https://github.com/samgrcia/sshfind.git
```

**From source with poetry**:

```bash
git clone git@github.com:samgrcia/sshfind.git
cd sshfind
poetry install
poetry run sshfind <query>
```

## Update

**With pipx**:
```bash
pipx upgrade sshfind
```

**With pip**:
```bash
pip install --upgrade git+https://github.com/samgrcia/sshfind.git
```

**From source**:
```bash
cd sshfind
git pull
poetry install
```

## Development

```bash
poetry install        # install dependencies
poetry run pytest     # run tests
```
