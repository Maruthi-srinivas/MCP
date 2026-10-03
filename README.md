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

1. The inspector sends a tool call to the streamable HTTP app in [mcp-servers/repository-mcp/src/repository_mcp/server.py](mcp-servers/repository-mcp/src/repository_mcp/server.py). That file registers tools, resource templates, and prompts, and adds `GET /health`.
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

Codes in this version: `INVALID_REPOSITORY_URL`, `REPOSITORY_NOT_FOUND`, `CLONE_FAILED`, `INVALID_PATH`, `FILE_NOT_FOUND`, `FILE_TOO_LARGE`, `TOOL_TIMEOUT`, `GITHUB_RATE_LIMIT`, `INTERNAL_ERROR`, `SYMBOL_NOT_FOUND`, `UNSUPPORTED_LANGUAGE`, `GIT_REF_NOT_FOUND`, `ANALYSIS_TIMEOUT`.

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
| `ANALYSIS_TIMEOUT` | 30 |
| `MAX_FUNCTIONS` | 500 |
| `MAX_CLASSES` | 500 |
| `MAX_ENDPOINTS` | 200 |
| `MAX_EDGES` | 500 |
| `MAX_HINTS` | 200 |
| `MAX_STEPS` | 8 |
| `MAX_TOOL_CALLS` | 12 |
| `MAX_TOOL_OUTPUT_CHARS` | 4000 |
| `AGENT_TIMEOUT_SECONDS` | 60 |
| `MAX_RETRIES` | 2 |
| `RESOURCE_MAX_CHARS` | 8000 |

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

1. `get_file_history` is registered in [mcp-servers/git-mcp/src/git_mcp/server.py](mcp-servers/git-mcp/src/git_mcp/server.py). That file registers the eight read-only git tools and the `investigate_change` prompt, and adds `GET /health`.
2. [mcp-servers/git-mcp/src/git_mcp/tools/get_file_history.py](mcp-servers/git-mcp/src/git_mcp/tools/get_file_history.py) checks the page size, then asks for the commits that touched one path.
3. [mcp-servers/git-mcp/src/git_mcp/git/commands.py](mcp-servers/git-mcp/src/git_mcp/git/commands.py) is the only place git runs. Every command is an argument list with `GIT_OPTIONAL_LOCKS=0`, so a read-only `.git` does not take a lock. Commit, push, checkout, reset, merge, rebase, and clean are not tools.
4. [shared/investigator_shared/registry.py](shared/investigator_shared/registry.py) reads `/workspaces/registry.json`, the same file Repository MCP writes. [shared/investigator_shared/paths.py](shared/investigator_shared/paths.py) keeps the requested path inside that workspace.

The patch is a separate `get_diff` call. `get_diff` includes both resolved SHAs and cuts the patch at `MAX_DIFF_LINES`. Point the inspector at `http://git-mcp:8001/mcp` to call these tools. The `workspaces` volume is mounted read-only on `git-mcp`.

## How detect_api_endpoints moves through the code

V0.4 adds a third MCP server, `analysis-mcp`, on port 8002. It re-parses Python with the standard-library `ast` module. It does not read the V0.2 index, and it does not import the other servers.

1. `detect_api_endpoints` is registered in [mcp-servers/analysis-mcp/src/analysis_mcp/server.py](mcp-servers/analysis-mcp/src/analysis_mcp/server.py). That file registers the nine analysis tools, the architecture resources, and the analysis prompts, and adds `GET /health`.
2. [mcp-servers/analysis-mcp/src/analysis_mcp/tools/detect_api_endpoints.py](mcp-servers/analysis-mcp/src/analysis_mcp/tools/detect_api_endpoints.py) loads the analysis artifact and returns the endpoint list.
3. [mcp-servers/analysis-mcp/src/analysis_mcp/analysis/endpoints.py](mcp-servers/analysis-mcp/src/analysis_mcp/analysis/endpoints.py) reads FastAPI and Flask decorators, Django `path` / `re_path` calls in `urls.py`, and `@api_view`. The route path is a string literal.
4. [mcp-servers/analysis-mcp/src/analysis_mcp/analysis/artifact.py](mcp-servers/analysis-mcp/src/analysis_mcp/analysis/artifact.py) writes `/workspaces/<repository_id>.analysis.json` beside the clone when the commit SHA or analyzer version changed. The git checkout is not modified. [shared/investigator_shared/registry.py](shared/investigator_shared/registry.py) reads the same registry Repository MCP writes.

`analyze_code` returns counts and warnings. Functions, the graph, database hints, and HTTP client calls stay on their own tools. A call edge has `inferred: true` because the name matched one function. That is not a runtime trace. A file that fails to parse adds a warning and the rest of the run continues. `ANALYSIS_TIMEOUT` is retryable.

File contents stay on port 8000. History stays on port 8001. This server does not summarize the graph with a model. Point the inspector at `http://analysis-mcp:8002/mcp` to call these tools.

## How one investigation moves through the code

V0.5 adds an `agent` service on port 8003. It is an MCP client. It does not import the other servers, and it does not mount the workspace volume.

1. `POST /investigate` is handled in [agent/src/agent_app/server.py](agent/src/agent_app/server.py). The body has a question and either a `repository_id` or a GitHub `url`. A URL calls `clone_repository` on repository-mcp before the loop starts. `GET /health` stays ok when `OPENAI_API_KEY` is missing. The investigation then returns `stopped_reason` `configuration`.
2. [agent/src/agent_app/graph.py](agent/src/agent_app/graph.py) is a LangGraph loop: one model turn, then every tool call from that turn together, then the model again. The next turn waits for the whole batch. The loop stops at `MAX_STEPS`, `MAX_TOOL_CALLS`, or `AGENT_TIMEOUT_SECONDS`. A failed tool is retried only when `retryable` is true, at most `MAX_RETRIES` times.
3. [agent/src/agent_app/policy.py](agent/src/agent_app/policy.py) is the system text: search before reading a large file, anchor facts to the commit SHA, and do not invent tool results.
4. [agent/src/agent_app/mcp_client.py](agent/src/agent_app/mcp_client.py) is the only place that calls MCP over HTTP. The servers are `http://repository-mcp:8000/mcp`, `http://git-mcp:8001/mcp`, and `http://analysis-mcp:8002/mcp`.

The response includes `answer`, `evidence`, `trace`, and `stopped_reason`. Evidence with `confidence` `high` came from a tool result that included the file and line. The trace stores the server, tool, status, duration, and an argument summary. It does not store file bodies or the API key. The trace is kept in memory for the life of the process.

## How a file resource and a prompt move through the code

V0.6 adds read-only JSON resources and reusable prompts. A resource is one document for the commit already stored. A prompt is instructions that name tools. The prompt starts the investigation loop. It is not an answer.

1. A client reads `repo://{id}/file/{path}`, for example `repo://repo_abc/file/app/main.py`. [mcp-servers/repository-mcp/src/repository_mcp/server.py](mcp-servers/repository-mcp/src/repository_mcp/server.py) registers that template. The path is the remainder of the URI, so slashes inside the file path stay intact.
2. [mcp-servers/repository-mcp/src/repository_mcp/resources.py](mcp-servers/repository-mcp/src/repository_mcp/resources.py) keeps the path inside the checkout with the same rules as `read_file`. `..`, an absolute path, and `.git` return `INVALID_PATH`. An unknown `repository_id` returns `REPOSITORY_NOT_FOUND` in the JSON body.
3. [shared/investigator_shared/secrets.py](shared/investigator_shared/secrets.py) redacts the file text before it is returned. A line whose name ends with `_KEY`, `_TOKEN`, or `_SECRET` loses its value. A PEM private-key block is removed. `GITHUB_TOKEN` is never copied into a resource. [shared/investigator_shared/bounds.py](shared/investigator_shared/bounds.py) caps the JSON at `RESOURCE_MAX_CHARS`.
4. `trace_api` is registered in [mcp-servers/analysis-mcp/src/analysis_mcp/prompts.py](mcp-servers/analysis-mcp/src/analysis_mcp/prompts.py). Its text names `search_code`, `find_symbol`, `read_file`, `find_references`, and `detect_database_access` in that order. The endpoint path is an argument.
5. `POST /investigate` can send `prompt` and `arguments`. [agent/src/agent_app/server.py](agent/src/agent_app/server.py) asks [agent/src/agent_app/prompts.py](agent/src/agent_app/prompts.py) to load that prompt. [agent/src/agent_app/mcp_client.py](agent/src/agent_app/mcp_client.py) calls `get_prompt` on the server that lists the name. The returned text becomes the question for the existing loop. An unknown name returns an answer that the prompt was not found and an empty trace.

Metadata, structure, and dependencies stay on repository-mcp. Architecture and endpoints stay on analysis-mcp. git-mcp has `investigate_change` and no resources.

## Tests

Tests run inside the image. Nothing is installed on the host.

```bash
docker compose --profile test run --rm tests
docker compose --profile test-git run --rm git-tests
docker compose --profile test-analysis run --rm analysis-tests
docker compose --profile test-agent run --rm agent-tests
```

Repository tests cover browse, search, and Python structure. Git tests use a three-commit fixture and do not contact GitHub. Analysis tests use a small FastAPI fixture with a database hint, an HTTP client call, and one file that does not parse. Agent tests use a scripted model and an in-process MCP stub, so they do not call OpenAI. The running repository server does not set `ALLOW_LOCAL_GIT`, so a non-GitHub URL is rejected.

After the three MCP servers and the agent are up, the health smoke test calls them over the Compose network:

```bash
docker compose --profile smoke run --rm smoke
```

## What this version does not do

PostgreSQL, Redis, accounts, and a web UI are later versions. JavaScript, TypeScript, Java, and Go are not parsed. analysis-mcp does not summarize the graph with a model. The agent does not write to a repository. git-mcp cannot commit, push, or check out a branch. See [VERSION_ROADMAP.md](VERSION_ROADMAP.md).

## Logs and shutdown

```bash
docker compose logs -f repository-mcp
docker compose logs -f git-mcp
docker compose logs -f analysis-mcp
docker compose logs -f agent
docker compose down
```

`docker compose down -v` also deletes cloned workspaces.
