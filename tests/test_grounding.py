"""Tests for Korean-market grounding: trusted-domain allowlist + precedence."""

from backend.openrouter import _hostname_in_allowlist
from backend.config import TRUSTED_DOMAINS


def test_korean_authorities_allowlisted_including_subdomains():
    assert _hostname_in_allowlist("https://health.kdca.go.kr/info", TRUSTED_DOMAINS)
    assert _hostname_in_allowlist("https://www.mfds.go.kr/brd/1", TRUSTED_DOMAINS)
    assert _hostname_in_allowlist("https://amc.seoul.kr/asan/healthinfo", TRUSTED_DOMAINS)
    assert _hostname_in_allowlist("https://www.pediatric.or.kr/guide", TRUSTED_DOMAINS)


def test_non_authority_korean_sites_blocked():
    assert not _hostname_in_allowlist("https://blog.naver.com/mom123", TRUSTED_DOMAINS)
    assert not _hostname_in_allowlist("https://cafe.daum.net/parenting", TRUSTED_DOMAINS)


def test_international_authorities_still_allowlisted():
    assert _hostname_in_allowlist("https://www.who.int/x", TRUSTED_DOMAINS)
    assert _hostname_in_allowlist("https://www.healthychildren.org/y", TRUSTED_DOMAINS)


def test_korean_authorities_take_precedence_in_ordering():
    # KR authorities must appear before international ones (source-precedence rule).
    assert TRUSTED_DOMAINS.index("kdca.go.kr") < TRUSTED_DOMAINS.index("who.int")
    assert TRUSTED_DOMAINS.index("pediatric.or.kr") < TRUSTED_DOMAINS.index("aap.org")
