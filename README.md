# GitHub Repository Investigator MCP

V0.1 is one read-only MCP server. It clones a public GitHub repository into a workspace and lets a client list directories, read a bounded slice of a file, and search the text. There is no agent, database, or web UI in this version.

The only host tools you need are Docker Engine, the Docker Compose plugin, and a browser.

## Start the server

From this directory:

```bash
docker compose up --build
```

- MCP endpoint: `http://127.0.0.1:8000/mcp`
- Health check: `http://127.0.0.1:8000/health`

Optional settings live in [.env.example](.env.example). Compose picks them up if you copy that file to `.env`. A `GITHUB_TOKEN` is optional. Git uses it only as an HTTP header inside the container. Tools never return it, and logs never include it.

## Try the tools

The MCP Inspector runs as a second container. It is not part of the default `docker compose up`.

```bash
docker compose --profile inspect up --build
```

Open `http://127.0.0.1:6274`. If the page asks for a token, copy it from:

```bash
docker compose logs mcp-inspector
```

In the inspector, choose Streamable HTTP and set the server URL to:

```text
http://repository-mcp:8000/mcp
```

That hostname is the Compose service name. The inspector container can resolve it. `127.0.0.1` from inside the inspector container is the inspector itself, not the MCP server.

Then call the tools in this order:

1. `clone_repository` with a public `https://github.com/owner/name` URL. `ref` can be a branch, a tag, or a full 40-character commit SHA. Omit `ref` to use the default branch.
2. `get_repository_info` with the returned `repository_id`.
3. `list_directory` with `path` set to `.`.
4. `search_code` with a word you expect to find.
5. `read_file` with the `path` and `line` from one search hit.

The same URL and ref always map to the same `repository_id`. Calling `clone_repository` again refreshes that workspace.

## How one search_code call moves through the code

1. The inspector sends a tool call to the streamable HTTP app in [mcp-servers/repository-mcp/src/repository_mcp/server.py](mcp-servers/repository-mcp/src/repository_mcp/server.py). That file only registers tools and adds `GET /health`.
2. [mcp-servers/repository-mcp/src/repository_mcp/tools/search_code.py](mcp-servers/repository-mcp/src/repository_mcp/tools/search_code.py) checks the query and the optional glob.
3. [mcp-servers/repository-mcp/src/repository_mcp/logging.py](mcp-servers/repository-mcp/src/repository_mcp/logging.py) wraps every tool. It writes one JSON log line with the tool name, duration, status, and result count. It does not log arguments.
4. [mcp-servers/repository-mcp/src/repository_mcp/workspace/registry.py](mcp-servers/repository-mcp/src/repository_mcp/workspace/registry.py) loads `/workspaces/registry.json` and finds the workspace for that `repository_id`.
5. [mcp-servers/repository-mcp/src/repository_mcp/workspace/paths.py](mcp-servers/repository-mcp/src/repository_mcp/workspace/paths.py) checks that the workspace stays under `WORKSPACE_ROOT`. Search does not take a user path, but file reads and directory listings use the same jail.
6. [mcp-servers/repository-mcp/src/repository_mcp/search/ripgrep.py](mcp-servers/repository-mcp/src/repository_mcp/search/ripgrep.py) runs `rg` inside the repository, skips `.git`, and stops after the hit limit.

`clone_repository` is the exception to the path jail. It is the tool that creates `/workspaces/<repository_id>` and the registry record. The id comes from [mcp-servers/repository-mcp/src/repository_mcp/workspace/ids.py](mcp-servers/repository-mcp/src/repository_mcp/workspace/ids.py). The git commands live in [mcp-servers/repository-mcp/src/repository_mcp/workspace/clone.py](mcp-servers/repository-mcp/src/repository_mcp/workspace/clone.py).

## Tools

| Tool | Purpose |
| --- | --- |
| `clone_repository` | Shallow-clone a public GitHub repository (depth 50), or refresh an existing one |
| `get_repository_info` | Return the stored URL, owner, name, ref, and commit SHA |
| `list_directory` | List one directory, not its children |
| `read_file` | Read a line range, with size and line caps |
| `search_code` | Search file contents and return path, line, and a short snippet |
| `find_symbol` | Python function, method, and class definitions |
| `find_references` | Import sites and same-file uses of a Python symbol |
| `find_dependencies` | `requirements.txt`, `requirements-*.txt`, and `pyproject.toml` dependencies |
| `detect_project_type` | Languages from file suffixes, and FastAPI, Flask, or Django |
| `detect_services` | Top-level Python packages and obvious entry files |

Errors look like this:

```json
{
  "error": {
    "code": "FILE_NOT_FOUND",
    "message": "src/missing.py was not found",
    "retryable": false,
    "request_id": "req_123"
  }
}
```

Codes in this version: `INVALID_REPOSITORY_URL`, `REPOSITORY_NOT_FOUND`, `CLONE_FAILED`, `INVALID_PATH`, `FILE_NOT_FOUND`, `FILE_TOO_LARGE`, `TOOL_TIMEOUT`, `GITHUB_RATE_LIMIT`, `INTERNAL_ERROR`, `SYMBOL_NOT_FOUND`, `UNSUPPORTED_LANGUAGE`, `GIT_REF_NOT_FOUND`.

## Limits

| Variable | Default |
| --- | --- |
| `MAX_READ_LINES` | 200 |
| `MAX_FILE_BYTES` | 1048576 |
| `MAX_SEARCH_HITS` | 50 |
| `MAX_DIRECTORY_ENTRIES` | 200 |
| `CLONE_TIMEOUT_SECONDS` | 60 |
| `TOOL_TIMEOUT_SECONDS` | 30 |
| `MAX_PYTHON_FILES` | 200 |
| `MAX_SYMBOLS` | 500 |
| `MAX_REFERENCES` | 50 |
| `INDEX_TIMEOUT_SECONDS` | 30 |
| `GIT_CLONE_DEPTH` | 50 |
| `DEFAULT_PAGE_SIZE` | 20 |
| `MAX_PAGE_SIZE` | 50 |
| `MAX_DIFF_LINES` | 200 |
| `MAX_BRANCHES` | 50 |

A file larger than `MAX_FILE_BYTES` is refused with `FILE_TOO_LARGE`. A read that asks for more than `MAX_READ_LINES` returns the first allowed lines and `"truncated": true`.

## How find_symbol moves through the code

V0.2 adds Python structure on the same server. Browse and search from V0.1 are unchanged.

1. `find_symbol` is registered in [mcp-servers/repository-mcp/src/repository_mcp/server.py](mcp-servers/repository-mcp/src/repository_mcp/server.py).
2. [mcp-servers/repository-mcp/src/repository_mcp/tools/find_symbol.py](mcp-servers/repository-mcp/src/repository_mcp/tools/find_symbol.py) asks for the index, then filters definitions by name. No definitions is `SYMBOL_NOT_FOUND`.
3. [mcp-servers/repository-mcp/src/repository_mcp/intelligence/index.py](mcp-servers/repository-mcp/src/repository_mcp/intelligence/index.py) loads `/workspaces/<repository_id>.index.json` when the commit SHA and analyzer version match. Otherwise it rebuilds that file beside the clone, not inside the git checkout.
4. [mcp-servers/repository-mcp/src/repository_mcp/intelligence/python_index.py](mcp-servers/repository-mcp/src/repository_mcp/intelligence/python_index.py) parses Python with the standard-library `ast` module. It records functions, async functions, classes, and methods. A syntax error becomes a warning and does not fail the tool.

`find_references` does not follow aliases. A reference is a use of the exact name in a file that defines it, or an import line that names it. `import create_user as make_user` counts that import line. Later uses of `make_user` do not.

A repository with Python and other languages still indexes the Python files and adds a warning for skipped source files. Structural tools return `UNSUPPORTED_LANGUAGE` only when there are no Python files. JavaScript and TypeScript are not parsed.

## How get_file_history moves through the code

V0.3 adds a second MCP server, `git-mcp`, on port 8001. It answers history questions. It does not clone, and it does not return file contents. `read_file` stays on port 8000.

1. `get_file_history` is registered in [mcp-servers/git-mcp/src/git_mcp/server.py](mcp-servers/git-mcp/src/git_mcp/server.py). That file only registers the eight read-only git tools and adds `GET /health`.
2. [mcp-servers/git-mcp/src/git_mcp/tools/get_file_history.py](mcp-servers/git-mcp/src/git_mcp/tools/get_file_history.py) checks the page size, then asks for the commits that touched one path.
3. [mcp-servers/git-mcp/src/git_mcp/git/commands.py](mcp-servers/git-mcp/src/git_mcp/git/commands.py) is the only place git runs. Every command is an argument list with `GIT_OPTIONAL_LOCKS=0`, so a read-only `.git` does not take a lock. Commit, push, checkout, reset, merge, rebase, and clean are not tools.
4. [shared/investigator_shared/registry.py](shared/investigator_shared/registry.py) reads `/workspaces/registry.json`, the same file Repository MCP writes. [shared/investigator_shared/paths.py](shared/investigator_shared/paths.py) keeps the requested path inside that workspace.

The patch is a separate `get_diff` call. `get_diff` includes both resolved SHAs and cuts the patch at `MAX_DIFF_LINES`. Point the inspector at `http://git-mcp:8001/mcp` to call these tools. The `workspaces` volume is mounted read-only on `git-mcp`.

## Tests

Tests run inside the image. Nothing is installed on the host.

```bash
docker compose --profile test run --rm tests
docker compose --profile test-git run --rm git-tests
```

Repository tests cover browse, search, and Python structure. Git tests use a three-commit fixture and do not contact GitHub. The running repository server does not set `ALLOW_LOCAL_GIT`, so a non-GitHub URL is rejected.

After both servers are up, the health smoke test calls them over the Compose network:

```bash
docker compose --profile smoke run --rm smoke
```

## What this version does not do

A separate Analysis MCP, an agent, resources, prompts, PostgreSQL, Redis, accounts, and a web UI are later versions. JavaScript, TypeScript, Java, and Go are not parsed. git-mcp cannot commit, push, or check out a branch. See [VERSION_ROADMAP.md](VERSION_ROADMAP.md).

## Logs and shutdown

```bash
docker compose logs -f repository-mcp
docker compose logs -f git-mcp
docker compose down
```

`docker compose down -v` also deletes cloned workspaces.
