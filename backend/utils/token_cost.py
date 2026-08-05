def estimate_cost(
    input_tokens: int,
    output_tokens: int,
) -> float:
    """
    Temporary estimate.
    Update pricing later if model changes.
    """

    INPUT_PRICE_PER_MILLION = 0.15
    OUTPUT_PRICE_PER_MILLION = 0.60

    input_cost = (
        input_tokens / 1_000_000
    ) * INPUT_PRICE_PER_MILLION

    output_cost = (
        output_tokens / 1_000_000
    ) * OUTPUT_PRICE_PER_MILLION

    return input_cost + output_cost