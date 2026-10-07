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
