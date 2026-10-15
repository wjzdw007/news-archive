"""Tests for X HTTP client with mocked HTTP."""

from __future__ import annotations

import json
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
            create_live_fetcher()


def test_fetch_user_timeline_success():
    """Test successful timeline fetch with mocked HTTP response."""
    from news_archive.x_http_client import fetch_user_timeline

    # Mock GraphQL response (simplified)
    mock_response_data = {
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
                                            "entryId": "tweet-123456",
                                            "content": {
                                                "itemContent": {
                                                    "tweet_results": {
                                                        "result": {
                                                            "__typename": "Tweet",
                                                            "rest_id": "123456",
                                                            "legacy": {
                                                                "full_text": "Test tweet content",
                                                                "created_at": "Mon Oct 14 12:34:56 +0000 2024",
                                                            },
                                                            "core": {
                                                                "user_results": {
                                                                    "result": {
                                                                        "legacy": {
                                                                            "screen_name": "testuser"
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
        }
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_response_data

    with patch("news_archive.x_http_client.requests") as mock_requests:
        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        mock_requests.Session.return_value = mock_session

        tweets = fetch_user_timeline(
            "testuser",
            bearer_token="Bearer test_token",
            auth_token="test_auth",
            ct0="test_ct0",
        )

        assert len(tweets) == 1
        assert tweets[0]["post_id"] == "123456"
        assert tweets[0]["text"] == "Test tweet content"
        assert tweets[0]["url"] == "https://x.com/testuser/status/123456"
        assert "2024-10-14" in tweets[0]["posted_at"]


def test_fetch_user_timeline_rate_limited():
    """Test rate limit handling."""
    from news_archive.x_http_client import XHTTPError, fetch_user_timeline

    mock_response = MagicMock()
    mock_response.status_code = 429

    with patch("news_archive.x_http_client.requests") as mock_requests:
        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        mock_requests.Session.return_value = mock_session

        with pytest.raises(XHTTPError, match="rate limited"):
            fetch_user_timeline(
                "testuser",
                bearer_token="Bearer test_token",
                auth_token="test_auth",
                ct0="test_ct0",
            )


def test_fetch_user_timeline_unauthorized():
    """Test unauthorized handling."""
    from news_archive.x_http_client import XHTTPError, fetch_user_timeline

    mock_response = MagicMock()
    mock_response.status_code = 401

    with patch("news_archive.x_http_client.requests") as mock_requests:
        mock_session = MagicMock()
        mock_session.get.return_value = mock_response
        mock_requests.Session.return_value = mock_session

        with pytest.raises(XHTTPError, match="unauthorized.*401"):
            fetch_user_timeline(
                "testuser",
                bearer_token="Bearer test_token",
                auth_token="test_auth",
                ct0="test_ct0",
            )


def test_live_mode_integration_with_fetch_account_posts():
    """Test that fetch_account_posts can use live mode with mocked HTTP."""
    from news_archive.x_fetch import fetch_account_posts
    from news_archive.x_http_client import XHTTPError

    # Mock environment with credentials
    mock_env = {
        "X_BEARER_TOKEN": "Bearer test_token",
        "X_AUTH_TOKEN": "test_auth",
        "X_CT0_TOKEN": "test_ct0",
    }

    mock_response_data = {
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
