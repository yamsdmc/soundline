class SoundlineError(Exception):
    """Base of every error Soundline raises on purpose (ARC-030).

    `code` is stable and machine-readable; the message says what to do next (ARC-031).
    """

    code = "soundline_error"


class IndexMismatchError(SoundlineError):
    """The index was built with a different pipeline than the current configuration (STO-010)."""

    code = "index_fingerprint_mismatch"


class ConfigurationError(SoundlineError):
    """The configuration cannot work as given; the message says how to fix it."""

    code = "configuration_error"
