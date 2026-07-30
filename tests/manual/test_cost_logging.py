from backend.utils.cost_logger import log_cost


log_cost(
    node_name="screening",
    input_tokens=100,
    output_tokens=25,
    estimated_cost=0.00005,
)

print("Logged.")