from dataclasses import dataclass


@dataclass(frozen=True)
class SearchResult:
    id: str
    title: str
    url: str


@dataclass(frozen=True)
class Item:
    id: str
    kind: str
    title: str
    url: str
    description: str = ""
    content: str = ""


@dataclass(frozen=True)
class SubmissionResult:
    kind: str
    url: str
    confirmation: str


@dataclass(frozen=True)
class Dish:
    """A dish entry embedded in the mobile shop page."""

    shop_id: str
    name: str
    price: float | None = None
    signature: bool = False


@dataclass(frozen=True)
class Review:
    """A customer review from the server-rendered review page."""

    shop_id: str
    time: str | None = None
    text: str = ""
