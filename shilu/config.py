"""Private local configuration, independent from project data and exports."""
import os
from pathlib import Path

ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
ARK_MODEL = "deepseek-v4-1-flash-260910"
CONFIG_KEYS = {
    "SHILU_PROVIDER", "SHILU_API_KEY", "SHILU_BASE_URL", "SHILU_MODEL",
    "SHILU_MAX_TOKENS", "SHILU_REASONING_EFFORT", "SHILU_THINKING",
}


def load_env(path):
    """Read a simple env file; never execute shell code. Process env takes precedence."""
    path = Path(path)
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if key not in CONFIG_KEYS:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)


def model_config():
    provider = os.environ.get("SHILU_PROVIDER", "compatible")
    if provider not in ("compatible", "ark"):
        raise ValueError("SHILU_PROVIDER 须为 compatible 或 ark")
    return {
        "provider": provider,
        "key": os.environ.get("SHILU_API_KEY", ""),
        "base": os.environ.get("SHILU_BASE_URL", ARK_BASE_URL if provider == "ark" else ""),
        "model": os.environ.get("SHILU_MODEL", ARK_MODEL if provider == "ark" else ""),
        "max_tokens": int(os.environ.get("SHILU_MAX_TOKENS", "8192")),
        "effort": os.environ.get("SHILU_REASONING_EFFORT", "low" if provider == "ark" else ""),
        "thinking": os.environ.get("SHILU_THINKING", "enabled" if provider == "ark" else ""),
    }


def public_model_config():
    config = model_config()
    return {"model_ready": all(config[k] for k in ("key", "base", "model")),
            "model": config["model"], "provider": config["provider"]}
