class DianpingError(RuntimeError):
    """Base error for a Dianping browser operation."""


class AccessRequired(DianpingError):
    """The page requires account login or an interactive verification."""


class ElementMissing(DianpingError):
    """The current page does not have the expected control or result."""


class SubmissionUnconfirmed(DianpingError):
    """The browser submitted a form but no success signal was observed."""


class PublishingUnavailable(DianpingError):
    """No verified publishing workflow is available on the current platform."""
