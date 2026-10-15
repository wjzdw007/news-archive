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


def test_fetch_news_accounts_success():
    """Test successful home timeline fetch with filtering (x-crawler pattern)."""
    from news_archive.x_http_client import fetch_news_accounts

    # Mock HomeLatestTimeline GraphQL response (x-crawler pattern)
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
                                                                "legacy": {
                                                                    "screen_name": "BBCChinese"
                                                                }
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
                                                                "legacy": {
                                                                    "screen_name": "RandomUser"
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

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_response_data

    with patch("news_archive.x_http_client.requests") as mock_requests:
        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        mock_requests.Session.return_value = mock_session

        tweets = fetch_news_accounts(
            target_accounts=["BBCChinese"],
            auth_token="test_auth",
            ct0="test_ct0",
            bearer_token="Bearer test_token",
        )

        # Should only return BBCChinese tweet (filtered out RandomUser)
        assert len(tweets) == 1
        assert tweets[0]["post_id"] == "123456"
        assert tweets[0]["author"] == "BBCChinese"
        assert tweets[0]["text"] == "BBC test tweet content"
        assert tweets[0]["url"] == "https://x.com/BBCChinese/status/123456"
        assert "2024-10-14" in tweets[0]["posted_at"]


def test_fetch_news_accounts_rate_limited():
    """Test rate limit handling."""
    from news_archive.x_http_client import XHTTPError, fetch_news_accounts

    mock_response = MagicMock()
    mock_response.status_code = 429

    with patch("news_archive.x_http_client.requests") as mock_requests:
        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        mock_requests.Session.return_value = mock_session

        with pytest.raises(XHTTPError, match="rate limited"):
            fetch_news_accounts(
                target_accounts=["BBCChinese"],
                auth_token="test_auth",
                ct0="test_ct0",
            )


def test_fetch_news_accounts_unauthorized():
    """Test unauthorized handling."""
    from news_archive.x_http_client import XHTTPError, fetch_news_accounts

    mock_response = MagicMock()
    mock_response.status_code = 401

    with patch("news_archive.x_http_client.requests") as mock_requests:
        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        mock_requests.Session.return_value = mock_session

        with pytest.raises(XHTTPError, match="unauthorized.*401"):
            fetch_news_accounts(
                target_accounts=["BBCChinese"],
                auth_token="test_auth",
                ct0="test_ct0",
            )


def test_live_mode_integration_with_fetch_account_posts():
    """Test that fetch_account_posts can use live mode with mocked HTTP."""
    from news_archive.x_fetch import fetch_account_posts

    # Mock environment with credentials (only auth_token + ct0 required)
    mock_env = {
        "X_AUTH_TOKEN": "test_auth",
        "X_CT0_TOKEN": "test_ct0",
        "X_BEARER_TOKEN": "Bearer test_token",
    }

    mock_response_data = {
        "data": {
            "home": {
                "home_timeline_urt": {
                    "instructions": [
                        {
                            "type": "TimelineAddEntries",
                            "entries": [
                                {
                                    "entryId": "tweet-789",
                                    "content": {
                                        "itemContent": {
                                            "tweet_results": {
                                                "result": {
                                                    "__typename": "Tweet",
                                                    "rest_id": "789",
                                                    "legacy": {
                                                        "full_text": "BBC tweet",
                                                        "created_at": "Tue Oct 15 08:00:00 +0000 2024",
                                                    },
                                                    "core": {
                                                        "user_results": {
                                                            "result": {
                                                                "legacy": {
                                                                    "screen_name": "BBCChinese"
                                                                }
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

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_response_data

    with patch.dict("os.environ", mock_env):
        with patch("news_archive.x_http_client.requests") as mock_requests:
            mock_session = MagicMock()
            mock_session.get.return_value = mock_response
            mock_requests.Session.return_value = mock_session

            posts = fetch_account_posts(mode="live", accounts=["BBCChinese"])

            assert len(posts) == 1
            assert posts[0].post_id == "789"
            assert posts[0].author == "BBCChinese"
            assert posts[0].text_snapshot == "BBC tweet"
            assert posts[0].status == "active"


def test_live_mode_soft_fail_on_missing_creds():
    """Test that live mode soft-fails when credentials missing."""
    from news_archive.x_fetch import XFetchError, fetch_account_posts

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(XFetchError, match="live mode unavailable"):
            fetch_account_posts(mode="live", accounts=["BBCChinese"])


def test_missing_auth_token_raises_error():
    """Test that missing auth_token raises XHTTPError."""
    from news_archive.x_http_client import XHTTPError, fetch_news_accounts

    with pytest.raises(XHTTPError, match="missing X_AUTH_TOKEN"):
        fetch_news_accounts(
            target_accounts=["BBCChinese"],
            auth_token=None,
            ct0="test_ct0",
        )


def test_missing_ct0_raises_error():
    """Test that missing ct0 raises XHTTPError."""
    from news_archive.x_http_client import XHTTPError, fetch_news_accounts

    with pytest.raises(XHTTPError, match="missing.*X_CT0_TOKEN"):
        fetch_news_accounts(
            target_accounts=["BBCChinese"],
            auth_token="test_auth",
            ct0=None,
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
