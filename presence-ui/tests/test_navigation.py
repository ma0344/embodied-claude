"""Legacy session/navigation API — superseded by Claude Code gateway mirror."""

import pytest

pytestmark = pytest.mark.skip(reason="Removed: presence-ui now proxies Claude Code /api/* on 8080")
