# Code2Video Plugin for aiZee

Sandboxed Code2Video integration. Generates educational Manim videos inside an isolated Docker container.

## Architecture

```text
aiZee (Windows)
  │
  │  generate_video(topic, ...)
  ▼
plugins/code2video/code2video_plugin.py
  │
  │  docker run --rm --read-only --cap-drop=ALL ...
  ▼
code2video:latest (Linux container on WSL2)
  │
  │  /app/entrypoint.py
  │  ──► api_config.json from env
  │  ──► python /app/src/agent.py --knowledge_point "..."
  ▼
output.mp4 on host volume
```

## Configuration

Enable in `plugins.yaml`:

```yaml
plugins:
  code2video:
    enabled: true
    permissions:
      - generate_video
      - build_image
```

Set API keys in the OS secret store or environment (at least one provider):

- `CODE2VIDEO_CLAUDE_API_KEY` (+ optional `CODE2VIDEO_CLAUDE_BASE_URL`)
- `CODE2VIDEO_GPT41_API_KEY` / `CODE2VIDEO_GPT5_*` / `CODE2VIDEO_GPT4O_*` / `CODE2VIDEO_GPTO4MINI_*` (Azure-style: `*_BASE_URL`, `*_API_VERSION`, `*_MODEL`)
- `CODE2VIDEO_GEMINI_API_KEY` (+ `*_BASE_URL`, `*_MODEL`)
- `CODE2VIDEO_ICONFINDER_API_KEY` (optional — icon assets)

### Free route via NVIDIA NIM + LiteLLM

Upstream hardcodes `model="claude-4-opus"` over an OpenAI-compatible
`/v1` endpoint, so any OpenAI-compatible proxy serving that model name
works. `plugins/code2video/litellm-c2v.yaml` maps `claude-4-opus` to an
NVIDIA NIM model using your `NVIDIA_API_KEY`:

```powershell
litellm --config plugins/code2video/litellm-c2v.yaml --port 4010
[Environment]::SetEnvironmentVariable('CODE2VIDEO_CLAUDE_BASE_URL', 'http://host.docker.internal:4010/v1', 'User')
[Environment]::SetEnvironmentVariable('CODE2VIDEO_CLAUDE_API_KEY', $env:LITELLM_MASTER_KEY, 'User')
```

Edit `model:` in the yaml to pick any NIM model your key can call
(the shipped default is `moonshotai/kimi-k2.6`; swap if unavailable).

## Build image

```powershell
docker build -t code2video:latest -f plugins/code2video/Dockerfile plugins/code2video
```

## Usage

The plugin does not add a CLI command — it registers MCP tools once the
server is running (`aizee mcp serve` or an MCP-connected client):

| Tool | Purpose |
|------|---------|
| `build_image` | Build `code2video:latest` from this Dockerfile |
| `generate_video` | Generate a Manim video for a topic in the container |
| `list_videos` | List rendered videos under `state/code2video-output/` |

`aizee deps` tracks readiness end-to-end — `docker`, `docker-image-code2video`
(auto-installable via `build_image`/`docker build`), and `code2video-keys`
(manual: at least one `CODE2VIDEO_*_API_KEY`).

## Files

- `__init__.py`: plugin gate (minimal import)
- `code2video_plugin.py`: OS plugin + MCP tool
- `Dockerfile`: container image with Manim + Code2Video
- `entrypoint.py`: container command wrapper
