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


def _user_by_screen_name_payload(handle: str, rest_id: str) -> dict:
    return {
        "data": {
            "user": {
                "result": {
                    "__typename": "User",
                    "rest_id": rest_id,
                    "core": {"screen_name": handle},
                }
            }
        }
    }


def _user_tweets_payload(handle: str, post_id: str, text: str) -> dict:
    return {
        "data": {
            "user": {
                "result": {
                    "timeline_v2": {
                        "timeline": {
                            "instructions": [
                                {
                                    "type": "TimelineAddEntries",
                                    "entries": [
                                        {
                                            "entryId": f"tweet-{post_id}",
                                            "content": {
                                                "itemContent": {
                                                    "tweet_results": {
                                                        "result": {
                                                            "__typename": "Tweet",
                                                            "rest_id": post_id,
                                                            "legacy": {
                                                                "full_text": text,
                                                                "created_at": "Mon Oct 14 12:34:56 +0000 2024",
                                                            },
                                                            "core": {
                                                                "user_results": {
                                                                    "result": {
                                                                        "core": {
                                                                            "screen_name": handle
                                                                        },
                                                                        "legacy": {},
                                                                    }
                                                                }
                                                            },
                                                        }
                                                    }
                                                }
                                            },
                                        }
                                    ],
                                }
                            ]
                        }
                    }
                }
            }
        }
    }


def test_fetch_user_accounts_per_handle():
    """UserTweets path: resolve rest_id then parse that handle's timeline."""
    import json

    from news_archive.x_http_client import fetch_user_accounts

    mock_session = MagicMock()

    def fake_get(url, params=None, timeout=None):
        resp = MagicMock()
        resp.status_code = 200
        if "UserByScreenName" in url:
            handle = json.loads(params["variables"])["screen_name"]
            resp.json.return_value = _user_by_screen_name_payload(handle, f"uid-{handle}")
        elif "UserTweets" in url:
            uid = json.loads(params["variables"])["userId"]
            handle = uid.removeprefix("uid-")
            resp.json.return_value = _user_tweets_payload(
                handle, f"tw-{handle}", f"{handle} ships a model"
            )
        else:
            raise AssertionError(f"unexpected url: {url}")
        return resp

    mock_session.get.side_effect = fake_get

    with patch("news_archive.x_http_client._make_session", return_value=mock_session):
        with patch.dict(
            "os.environ",
            {"X_AUTH_TOKEN": "test_token", "X_CT0_TOKEN": "test_ct0"},
        ):
            with patch("news_archive.x_http_client.time.sleep"):
                with patch("sys.stderr"):
                    posts = fetch_user_accounts(
                        target_accounts=["OpenAI", "karpathy"],
                        pause_seconds=0,
                    )

    authors = {p["author"] for p in posts}
    assert authors == {"OpenAI", "karpathy"}
    assert all("ships a model" in p["text"] for p in posts)
    # lookup + tweets per handle
    assert mock_session.get.call_count == 4


def test_fetch_user_accounts_skips_one_handle():
    """One unavailable handle must not drop the rest of the batch."""
    import json

    from news_archive.x_http_client import fetch_user_accounts

    mock_session = MagicMock()

    def fake_get(url, params=None, timeout=None):
        resp = MagicMock()
        if "UserByScreenName" in url:
            handle = json.loads(params["variables"])["screen_name"]
            if handle == "missingAI":
                resp.status_code = 404
                resp.text = "not found"
                return resp
            resp.status_code = 200
            resp.json.return_value = _user_by_screen_name_payload(handle, "uid-ok")
            return resp
        resp.status_code = 200
        resp.json.return_value = _user_tweets_payload("OpenAI", "99", "still here")
        return resp

    mock_session.get.side_effect = fake_get

    with patch("news_archive.x_http_client._make_session", return_value=mock_session):
        with patch.dict(
            "os.environ",
            {"X_AUTH_TOKEN": "test_token", "X_CT0_TOKEN": "test_ct0"},
        ):
            with patch("sys.stderr"):
                posts = fetch_user_accounts(
                    target_accounts=["missingAI", "OpenAI"],
                    pause_seconds=0,
                )

    assert len(posts) == 1
    assert posts[0]["author"] == "OpenAI"


def test_user_tweets_visibility_unwrap():
    """User timeline also unwraps TweetWithVisibilityResults."""
    from news_archive.x_http_client import _parse_tweets_from_timeline

    wrapped = _user_tweets_payload("AnthropicAI", "777", "Claude update")
    tweet = wrapped["data"]["user"]["result"]["timeline_v2"]["timeline"]["instructions"][0][
        "entries"
    ][0]["content"]["itemContent"]["tweet_results"]["result"]
    wrapped["data"]["user"]["result"]["timeline_v2"]["timeline"]["instructions"][0]["entries"][0][
        "content"
    ]["itemContent"]["tweet_results"]["result"] = {
        "__typename": "TweetWithVisibilityResults",
        "tweet": tweet,
    }
    posts = _parse_tweets_from_timeline(wrapped)
    assert len(posts) == 1
    assert posts[0]["author"] == "AnthropicAI"
    assert posts[0]["text"] == "Claude update"


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
