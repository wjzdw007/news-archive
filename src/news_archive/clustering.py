"""Minimal topic_id clustering for same-event articles."""

from __future__ import annotations

# CEO 2026-10-15: try 0.7 (was 0.8); revert this constant to roll back.
DEFAULT_SIMILARITY_THRESHOLD = 0.7
DEFAULT_WINDOW_HOURS = 6.0

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any


def normalize_title(title: str) -> str:
    """Normalize title: lowercase, strip punctuation/whitespace, keep CJK/Latin/digits."""
    # Convert to lowercase
    title = title.lower()
    # Keep only CJK characters, Latin letters, and digits
    # CJK ranges: \u4e00-\u9fff (common), \u3400-\u4dbf (extension A), \uf900-\ufaff (compatibility)
    # Also keep spaces temporarily for splitting
    title = re.sub(r"[^\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaffa-z0-9\s]", "", title)
    # Collapse whitespace
    title = re.sub(r"\s+", "", title)
    return title


def char_bigrams(text: str) -> set[str]:
    """Generate character bigrams from text."""
    if len(text) < 2:
        return {text} if text else set()
    return {text[i : i + 2] for i in range(len(text) - 1)}


def jaccard_similarity(text1: str, text2: str) -> float:
    """Calculate Jaccard similarity on character bigrams."""
    bigrams1 = char_bigrams(text1)
    bigrams2 = char_bigrams(text2)
    
    if not bigrams1 and not bigrams2:
        return 1.0
    if not bigrams1 or not bigrams2:
        return 0.0
    
    intersection = len(bigrams1 & bigrams2)
    union = len(bigrams1 | bigrams2)
    return intersection / union if union > 0 else 0.0


def parse_iso_datetime(dt_str: str | None) -> datetime | None:
    """Parse ISO-8601 datetime string."""
    if not dt_str:
        return None
    try:
        # Handle various ISO formats
        dt_str = dt_str.strip()
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"
        return datetime.fromisoformat(dt_str)
    except (ValueError, AttributeError):
        return None


def within_time_window(
    dt1: datetime | None, dt2: datetime | None, window_hours: float = 6.0
) -> bool:
    """Check if two datetimes are within ±window_hours of each other (anchored on earlier)."""
    if dt1 is None or dt2 is None:
        return False
    
    earlier = min(dt1, dt2)
    later = max(dt1, dt2)
    delta = later - earlier
    
    return delta <= timedelta(hours=window_hours)


def should_merge(
    article1: dict[str, Any],
    article2: dict[str, Any],
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    window_hours: float = DEFAULT_WINDOW_HOURS,
) -> bool:
    """Determine if two articles should share the same topic_id.
    
    Merge if:
    - Normalized title similarity ≥ threshold (Jaccard on char bigrams)
    - Published within same time window (±6h anchored on earlier)
    - Preferentially merge across sources (same-source generally don't merge)
    """
    # Skip if same source (generally don't merge same-source)
    if article1.get("source") == article2.get("source"):
        return False
    
    # Check title similarity
    title1 = normalize_title(article1.get("title", ""))
    title2 = normalize_title(article2.get("title", ""))
    
    if not title1 or not title2:
        return False
    
    similarity = jaccard_similarity(title1, title2)
    if similarity < similarity_threshold:
        return False
    
    # Check time window
    dt1 = parse_iso_datetime(article1.get("published_at"))
    dt2 = parse_iso_datetime(article2.get("published_at"))
    
    if not within_time_window(dt1, dt2, window_hours):
        return False
    
    return True


def assign_topic_ids(
    articles: list[dict[str, Any]],
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    window_hours: float = DEFAULT_WINDOW_HOURS,
) -> list[dict[str, Any]]:
    """Assign topic_id to articles using greedy clustering.
    
    Rules:
    - Only active articles participate in NEW merges
    - Articles with existing topic_id keep it (gone articles excluded from new merges)
    - Single articles still get a topic_id
    - Cross-source merging preferred
    
    Returns: List of articles with topic_id assigned
    """
    # Separate articles: active without topic_id (candidates) vs. others (keep as-is)
    candidates = [a for a in articles if a.get("status") == "active" and not a.get("topic_id")]
    existing = [a for a in articles if a.get("topic_id") or a.get("status") != "active"]
    
    # Track topic_id assignments for candidates
    topic_assignments: dict[int, str] = {}  # index -> topic_id
    
    # Greedy clustering
    for i, article1 in enumerate(candidates):
        if i in topic_assignments:
            continue
        
        # Check if this article merges with any already-assigned articles
        merged = False
        for j in range(i):
            if j not in topic_assignments:
                continue
            
            article2 = candidates[j]
            if should_merge(article1, article2, similarity_threshold, window_hours):
                # Merge into existing cluster
                topic_assignments[i] = topic_assignments[j]
                merged = True
                break
        
        if not merged:
            # Check if merges with any unassigned articles ahead
            cluster_members = [i]
            for j in range(i + 1, len(candidates)):
                if j in topic_assignments:
                    continue
                
                article2 = candidates[j]
                # Check against any member of the current cluster
                for k in cluster_members:
                    article_k = candidates[k]
                    if should_merge(article1, article2, similarity_threshold, window_hours) or \
                       should_merge(article2, article_k, similarity_threshold, window_hours):
                        cluster_members.append(j)
                        break
            
            # Assign new topic_id to this cluster
            topic_id = str(uuid.uuid4())
            for k in cluster_members:
                topic_assignments[k] = topic_id
    
    # Apply topic_id to candidates
    result_candidates = []
    for i, article in enumerate(candidates):
        updated = article.copy()
        updated["topic_id"] = topic_assignments.get(i, str(uuid.uuid4()))
        result_candidates.append(updated)
    
    return existing + result_candidates
