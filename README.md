# sshfind

Search SSH host configurations by pattern.

`sshfind` reads `~/.ssh/config` and recursively follows every `Include` directive it contains. It displays the SSH options of every `Host` (and `Match Host`) block whose name matches the query.

## Usage

```
sshfind <query> [-r] [-a]
```

| Argument        | Description                                                        |
| --------------- | ------------------------------------------------------------------ |
| `query`         | String to search for in Host patterns (case-insensitive substring) |
| `-r`, `--regex` | Treat the query as a regular expression                            |
| `-a`, `--all`   | Include `Host *` catch-all blocks in results                       |

Returns exit code `1` when no results are found.

## Examples

```bash
# Find all hosts matching "prod"
sshfind prod

# Find hosts starting with "web" using a regex
sshfind '^web' --regex

# Include the global Host * block
sshfind prod --all
```

### Output

`Host` blocks and `Match Host` blocks are displayed in separate tables.

```
╭──────────────┬───────────────────────────────╮
│ Host         │ Options                       │
├──────────────┼───────────────────────────────┤
│ prod-server  │ Hostname 10.0.1.42            │
│ config.d/prod│ User deploy                   │
│              │ IdentityFile ~/.ssh/id_ed25519 │
╰──────────────┴───────────────────────────────╯
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

## Development

```bash
poetry install        # install dependencies
poetry run pytest     # run tests
```
