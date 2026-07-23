"""
Thin client for the external WD tagger microservice (tools/wd-tagger-service).

Speaks the contract: POST the image bytes to the configured URL with an
X-Auth-Token header and general/character thresholds as query params; get back
{model, rating, general, character}. Only the standard library is used.
"""

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_TIMEOUT = 120


class TaggerError(Exception):
    """The tagger could not be reached or returned an unusable response."""


def tag(
    url: str,
    image_bytes: bytes,
    token: str,
    general_threshold: float,
    character_threshold: float,
    mime_type: Optional[str] = None,
) -> Dict:
    separator = "&" if "?" in url else "?"
    full_url = url + separator + urllib.parse.urlencode(
        {
            "general_threshold": general_threshold,
            "character_threshold": character_threshold,
        }
    )
    request = urllib.request.Request(full_url, data=image_bytes, method="POST")
    request.add_header("Content-Type", mime_type or "application/octet-stream")
    request.add_header("Accept", "application/json")
    if token:
        request.add_header("X-Auth-Token", token)

    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            raw = response.read()
    except urllib.error.HTTPError as ex:
        raise TaggerError("tagger returned HTTP %d" % ex.code)
    except urllib.error.URLError as ex:
        raise TaggerError("tagger unreachable: %s" % ex.reason)
    except OSError as ex:
        raise TaggerError("tagger request failed: %s" % ex)

    try:
        data = json.loads(raw.decode("utf-8", "replace"))
    except ValueError:
        raise TaggerError("tagger returned invalid JSON")
    if not isinstance(data, dict):
        raise TaggerError("tagger returned an unexpected payload")
    return data
