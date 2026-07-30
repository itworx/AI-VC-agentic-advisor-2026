from datetime import datetime
from pathlib import Path


LOG_FILE = Path("logs/costs.log")


def log_cost(
    node_name: str,
    input_tokens: int,
    output_tokens: int,
    estimated_cost: float,
) -> None:
    """
    Append one cost record per node execution.
    """

    LOG_FILE.parent.mkdir(exist_ok=True)

    timestamp = datetime.utcnow().isoformat()

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(
            f"{timestamp} | "
            f"{node_name} | "
            f"input={input_tokens} | "
            f"output={output_tokens} | "
            f"cost=${estimated_cost:.6f}\n"
        )