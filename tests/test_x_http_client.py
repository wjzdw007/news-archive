"""Tests for X HTTP client with mocked HTTP (x-crawler HomeLatestTimeline mode)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_http_client_missing_requests():
    """Test graceful failure when requests library missing."""
    # Note: This test is for documentation purposes; in practice,
    # requests is imported at module level so patching sys.modules
    # after import won't affect the already-loaded module.
    # The actual check happens in _make_session at runtime.
    pytest.skip("Module-level import makes this test non-functional")


def test_create_live_fetcher_missing_credentials():
    """Test that create_live_fetcher raises on missing credentials."""
    from news_archive.x_http_client import XHTTPError, create_live_fetcher

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(XHTTPError, match="X credentials missing"):
            create_live_fetcher(target_accounts=["BBCChinese"])


def test_fetch_news_accounts_success_new_schema():
    """Test successful home timeline fetch with NEW user.core.screen_name schema."""
    from news_archive.x_http_client import fetch_news_accounts

    # Mock HomeLatestTimeline GraphQL response (NEW schema: user.core.screen_name)
    mock_response_data = {
        "data": {
            "home": {
                "home_timeline_urt": {
                    "instructions": [
                        {
                            "type": "TimelineAddEntries",
                            "entries": [
                                {
                                    "entryId": "tweet-123456",
                                    "content": {
                                        "itemContent": {
                                            "tweet_results": {
                                                "result": {
                                                    "__typename": "Tweet",
                                                    "rest_id": "123456",
                                                    "legacy": {
                                                        "full_text": "BBC test tweet content",
                                                        "created_at": "Mon Oct 14 12:34:56 +0000 2024",
                                                    },
                                                    "core": {
                                                        "user_results": {
                                                            "result": {
                                                                "core": {
                                                                    "screen_name": "BBCChinese"
                                                                },
                                                                "legacy": {}  # empty fallback
                                                            }
                                                        }
                                                    },
                                                }
                                            }
                                        }
                                    },
                                },
                                {
                                    "entryId": "tweet-789012",
                                    "content": {
                                        "itemContent": {
                                            "tweet_results": {
                                                "result": {
                                                    "__typename": "Tweet",
                                                    "rest_id": "789012",
                                                    "legacy": {
                                                        "full_text": "Random user tweet (should be filtered out)",
                                                        "created_at": "Tue Oct 15 08:00:00 +0000 2024",
                                                    },
                                                    "core": {
                                                        "user_results": {
                                                            "result": {
                                                                "core": {
                                                                    "screen_name": "RandomUser"
                                                                },
                                                                "legacy": {}
                                                            }
                                                        }
                                                    },
                                                }
                                            }
                                        }
                                    },
                                },
                            ],
                        }
                    ]
                }
            }
        }
    }

    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_response_data
    mock_session.get.return_value = mock_response

    with patch("news_archive.x_http_client._make_session", return_value=mock_session):
        with patch.dict(
            "os.environ",
            {"X_AUTH_TOKEN": "test_token", "X_CT0_TOKEN": "test_ct0"},
        ):
            # Suppress stderr logs during test
            with patch("sys.stderr"):
                posts = fetch_news_accounts(target_accounts=["BBCChinese"])

    assert len(posts) == 1  # Only BBCChinese, RandomUser filtered out
    assert posts[0]["post_id"] == "123456"
    assert posts[0]["author"] == "BBCChinese"
    assert "BBC test tweet" in posts[0]["text"]


def test_fetch_news_accounts_legacy_fallback():
    """Test author extraction fallback to legacy.screen_name when core is missing."""
    from news_archive.x_http_client import fetch_news_accounts

    # Mock response with ONLY legacy.screen_name (old schema)
    mock_response_data = {
        "data": {
            "home": {
                "home_timeline_urt": {
                    "instructions": [
                        {
                            "type": "TimelineAddEntries",
                            "entries": [
                                {
                                    "entryId": "tweet-111222",
                                    "content": {
                                        "itemContent": {
                                            "tweet_results": {
                                                "result": {
                                                    "__typename": "Tweet",
                                                    "rest_id": "111222",
                                                    "legacy": {
                                                        "full_text": "Reuters old schema",
                                                        "created_at": "Mon Oct 14 12:00:00 +0000 2024",
                                                    },
                                                    "core": {
                                                        "user_results": {
                                                            "result": {
                                                                "core": {},  # No core.screen_name
                                                                "legacy": {
                                                                    "screen_name": "Reuters"
                                                                }
                                                            }
                                                        }
                                                    },
                                                }
                                            }
                                        }
                                    },
                                },
                            ],
                        }
                    ]
                }
            }
        }
    }

    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_response_data
    mock_session.get.return_value = mock_response

    with patch("news_archive.x_http_client._make_session", return_value=mock_session):
        with patch.dict(
            "os.environ",
            {"X_AUTH_TOKEN": "test_token", "X_CT0_TOKEN": "test_ct0"},
        ):
            with patch("sys.stderr"):
                posts = fetch_news_accounts(target_accounts=["Reuters"])

    assert len(posts) == 1
    assert posts[0]["author"] == "Reuters"  # Fallback worked
    assert posts[0]["text"] == "Reuters old schema"


def test_tweet_with_visibility_results_unwrap():
    """Test TweetWithVisibilityResults wrapper is unwrapped correctly."""
    from news_archive.x_http_client import fetch_news_accounts

    # Mock response with TweetWithVisibilityResults wrapper
    mock_response_data = {
        "data": {
            "home": {
                "home_timeline_urt": {
                    "instructions": [
                        {
                            "type": "TimelineAddEntries",
                            "entries": [
                                {
                                    "entryId": "tweet-333444",
                                    "content": {
                                        "itemContent": {
                                            "tweet_results": {
                                                "result": {
                                                    "__typename": "TweetWithVisibilityResults",
                                                    "tweet": {
                                                        "__typename": "Tweet",
                                                        "rest_id": "333444",
                                                        "legacy": {
                                                            "full_text": "FT wrapped tweet",
                                                            "created_at": "Mon Oct 14 13:00:00 +0000 2024",
                                                        },
                                                        "core": {
                                                            "user_results": {
                                                                "result": {
                                                                    "core": {
                                                                        "screen_name": "FT"
                                                                    },
                                                                    "legacy": {}
                                                                }
                                                            }
                                                        },
                                                    }
                                                }
                                            }
                                        }
                                    },
                                },
                            ],
                        }
                    ]
                }
            }
        }
    }

    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_response_data
    mock_session.get.return_value = mock_response

    with patch("news_archive.x_http_client._make_session", return_value=mock_session):
        with patch.dict(
            "os.environ",
            {"X_AUTH_TOKEN": "test_token", "X_CT0_TOKEN": "test_ct0"},
        ):
            with patch("sys.stderr"):
                posts = fetch_news_accounts(target_accounts=["FT"])

    assert len(posts) == 1
    assert posts[0]["author"] == "FT"
    assert posts[0]["text"] == "FT wrapped tweet"


def test_author_unknown_when_missing():
    """Test author becomes 'unknown' when both core and legacy are missing."""
    from news_archive.x_http_client import _parse_single_tweet

    tweet_data = {
        "rest_id": "999888",
        "legacy": {
            "full_text": "Mystery tweet",
            "created_at": "Mon Oct 14 14:00:00 +0000 2024",
        },
        "core": {
            "user_results": {
                "result": {
                    "core": {},
                    "legacy": {}  # Both empty
                }
            }
        },
    }

    parsed = _parse_single_tweet(tweet_data)
    assert parsed is not None
    assert parsed["author"] == "unknown"
