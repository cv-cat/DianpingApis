import pytest

from dianping_apis import DianpingCreatorAPI, PublishingUnavailable


class NoBrowserPage:
    """Publishing must not navigate or submit from an unverified Web flow."""

    def __getattr__(self, name):
        raise AssertionError(f"unexpected browser operation: {name}")


def test_note_publishing_reports_unavailable_without_browser_side_effects():
    with pytest.raises(PublishingUnavailable, match="no verified note editor"):
        DianpingCreatorAPI(NoBrowserPage()).publish_note("探店标题", "真实体验", submit=True)


def test_review_publishing_reports_unavailable_without_browser_side_effects():
    with pytest.raises(PublishingUnavailable, match="no verified review form"):
        DianpingCreatorAPI(NoBrowserPage()).publish_review(
            "https://www.dianping.com/shop/123", "真实体验", rating=4, submit=True
        )


def test_review_rejects_invalid_shop_and_rating():
    creator = DianpingCreatorAPI(NoBrowserPage())
    with pytest.raises(ValueError, match="shop_url"):
        creator.publish_review("https://www.dianping.com/note/123", "真实体验", rating=4)
    with pytest.raises(ValueError, match="rating"):
        creator.publish_review("https://www.dianping.com/shop/123", "真实体验", rating=True)
