import os

from hypothesis import HealthCheck, settings

# "dev" is fast for the inner loop; "ci" is reproducible; "nightly" digs deeper.
settings.register_profile("dev", max_examples=50)
settings.register_profile("ci", max_examples=200, derandomize=True, print_blob=True)
settings.register_profile(
    "nightly", max_examples=5_000, suppress_health_check=[HealthCheck.too_slow]
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))
