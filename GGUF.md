# Local GGUF analysis

AI Walkthrough defaults to **Local GGUF**. The Python app sends its reviewed diagnostic projection to a llama.cpp server on **127.0.0.1** on the backend computer. It does not load GGUF weights inside Python or the browser. No cloud key is required, and local failures never trigger an OpenAI request.

## Setup

1. Install a llama.cpp build appropriate for the backend computer and obtain a compatible GGUF chat/instruction model with a supported chat template. Keep the model outside the project and check its licence. The app does not download a model.
2. Start the model server in a separate terminal:

   ```sh
   llama-server -m "/path/to/model.gguf" --host 127.0.0.1 --port 8080 --alias nelsonict-gguf -c 16384
   ```

   On Windows, use `llama-server.exe` and a Windows model path. The context value is an example: choose a value the model and available memory support.
3. Leave llama-server running, then start Router Manager normally (`python3 server.py` or the packaged application).
4. Open **AI walkthrough**, collect a fresh snapshot or import an export, and choose **Local GGUF · this computer**.
5. Inspect the projected evidence, confirm consent and request analysis. Review every proposed repair before applying. Imported evidence cannot authorize router writes.

The integration uses llama.cpp's chat-completions endpoint and schema-constrained JSON. See the [official llama.cpp server documentation](https://github.com/ggml-org/llama.cpp/tree/master/tools/server) for installation, supported models, chat templates and server options.

## Settings

| Backend environment setting | Default | Purpose |
|---|---|---|
| `NELSONICT_GGUF_PORT` | `8080` | Local server port, 1–65535 |
| `NELSONICT_GGUF_MODEL` | `nelsonict-gguf` | Match the server's model alias |
| `NELSONICT_AI_PROVIDER` | `gguf` | Default for API callers that omit a provider: `gguf` or `openai` |

Set overrides before launching the backend. The browser explicitly sends its selected provider; it starts with Local GGUF. OpenAI remains available only when selected, with `OPENAI_API_KEY` and `OPENAI_MODEL` configured. Selecting OpenAI sends the projection to that cloud service.

## Behavior and limits

- The endpoint is fixed to numeric loopback. No remote model URLs, DNS resolution, HTTP redirects or proxy environment settings are used by this adapter.
- One local analysis runs at a time. Additional local requests receive a busy message. Local inference uses a 120-second socket timeout, while the existing owner-operation lock remains released during analysis.
- The request is non-streaming, with a 4,000-output-token cap. Incomplete output, malformed JSON, unsupported fix IDs and oversized responses are rejected.
- The 300 KB application evidence limit is not a promise that the model context can fit it. Narrow profile/batch filters for large routers. A context error does not silently trim records.
- Model quality and speed depend on the model, quantization, memory and hardware. No specific GGUF model is bundled or certified.
- Model recommendations cannot supply executable router commands. Existing supported fixes, backup confirmation, stale-review checks and permission checks remain in force.
- Local inference stays on the backend host when using the intended local llama-server. Protect that server's logs and local OS account. Model downloads require connectivity; inference can operate offline once the runtime and weights are present.
- Desktop packages do not bundle llama.cpp or model weights. When migrating computers, install/copy them separately, start the model server, and repeat a sample diagnostic review. App JSON backups do not include models.
- This implementation was authored without an available execution environment. Mocked regression tests are included in CI; real GGUF inference, performance and physical-router acceptance still need testing.

## Troubleshooting

**Connection refused:** start llama-server on the backend computer and match its port to `NELSONICT_GGUF_PORT`. A phone accessing the dashboard still uses the computer's model server.

**Model loading or context error:** wait for the model to load, check its server log, narrow the evidence, and choose a supported context size.

**Timeout:** use a smaller compatible model or a narrower review. The app does not fall back to cloud processing.

**Invalid or incomplete JSON:** verify the chat template and schema-output support. A truncated response is rejected; try a narrower review or a better-suited instruction model.

**Model alias mismatch:** match `--alias` to `NELSONICT_GGUF_MODEL`.

**OpenAI selected accidentally:** switch back to Local GGUF, inspect the consent text and run a fresh analysis.
