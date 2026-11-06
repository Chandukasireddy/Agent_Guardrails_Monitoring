# Token Vault

> Break AI guards. Learn why they fail. Build them stronger.

---

## Requirements

<table><tr><td>

- **Git**: [Windows](https://git-scm.com/download/win) · macOS: `xcode-select --install`
- **uv**: installs Python 3.12 for you
- **Keys** (free, optional): NVIDIA and Langfuse, see step 3

</td></tr></table>

---

## Setup

### 1 · Install uv

**Windows** (PowerShell):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS / Linux**:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2 · Clone and install

```bash
git clone https://github.com/Chandukasireddy/Agent_Guardrails_Monitoring.git
cd Agent_Guardrails_Monitoring
uv sync --extra langfuse
```

### 3 · Add your keys

Get the keys:

| Key | Where |
|---|---|
| **NVIDIA** | [build.nvidia.com](https://build.nvidia.com) → **Generate API Key** |
| **Langfuse** | [cloud.langfuse.com](https://cloud.langfuse.com) → your project → **Settings → API Keys** |

Run the game once so it creates `.env`:

```bash
uv run token-vault serve
```

Then open `.env` in the project folder and add:

```bash
NVIDIA_API_KEY=nvapi-your-key
LLM_PROVIDER=nvidia

LANGFUSE_PUBLIC_KEY=pk-lf-your-public-key
LANGFUSE_SECRET_KEY=sk-lf-your-secret-key
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

### 4 · Run

Start the game with `uv run token-vault serve` (from step 3), then open:

**http://localhost:8000**

You'll understand the rest from the link.
