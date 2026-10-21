import pytest

from soundline.domain.usage import Price, StageUsage, TokenUsage, Usage, price_for

SONNET = Price(input=3.0, output=15.0, cache_read=0.3, cache_write=3.75)


@pytest.mark.spec("GEN-070")
def test_cost_prices_each_kind_of_token_per_million():
    tokens = TokenUsage(input=1_000_000, output=100_000, cache_read=2_000_000, cache_write=0)

    assert SONNET.cost(tokens) == pytest.approx(3.0 + 1.5 + 0.6)


def test_token_usages_add_up():
    total = TokenUsage(input=10, output=2) + TokenUsage(input=5, output=1, cache_read=7)

    assert total == TokenUsage(input=15, output=3, cache_read=7)
    assert total.total_input == 22


@pytest.mark.spec("GEN-070")
def test_usage_totals_tokens_and_cost_across_stages():
    usage = Usage(
        (
            StageUsage("generation", "anthropic:m", TokenUsage(input=1_000_000), 3.0),
            StageUsage("generation_retry", "anthropic:m", TokenUsage(output=1_000_000), 15.0),
        )
    )

    assert usage.tokens == TokenUsage(input=1_000_000, output=1_000_000)
    assert usage.cost_usd == pytest.approx(18.0)


@pytest.mark.spec("GEN-070")
def test_an_unknown_price_makes_the_total_cost_unknown_rather_than_wrong():
    usage = Usage(
        (
            StageUsage("generation", "anthropic:m", TokenUsage(input=10), 0.1),
            StageUsage("generation_retry", "mystery:m", TokenUsage(input=10), None),
        )
    )

    assert usage.cost_usd is None


def test_no_stage_costs_nothing():
    assert Usage().cost_usd == 0.0
    assert Usage().tokens == TokenUsage()


@pytest.mark.spec("GEN-070")
def test_prices_are_looked_up_by_model_id_and_local_models_are_free():
    table = {"anthropic:claude-sonnet-5-5": SONNET}

    assert price_for("anthropic:claude-sonnet-5-5", table) == SONNET
    assert price_for("ollama:qwen3.5:27b", table) == Price(0.0, 0.0)
    assert price_for("openai:gpt-5", table) is None
