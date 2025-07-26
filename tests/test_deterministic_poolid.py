"""
Test for deterministic pool ID generation.
"""

from datetime import datetime

from core.strategy.pool_models import generate_pool_id


def test_deterministic_pool_id_generation():
    """Test that pool IDs are deterministic across runs."""
    timestamp = datetime(2025, 1, 1, 12, 0, 0)

    # Generate the same pool ID multiple times
    pool_id1 = generate_pool_id("H1", timestamp, 1.1000, 1.0950)
    pool_id2 = generate_pool_id("H1", timestamp, 1.1000, 1.0950)
    pool_id3 = generate_pool_id("H1", timestamp, 1.1000, 1.0950)

    # All should be identical
    assert pool_id1 == pool_id2 == pool_id3

    # Verify format
    assert pool_id1.startswith("H1_2025-01-01T12:00:00_")
    assert len(pool_id1.split("_")) == 3

    # Different inputs should generate different IDs
    pool_id_different = generate_pool_id("H1", timestamp, 1.2000, 1.1950)
    assert pool_id1 != pool_id_different

    print(f"✓ Deterministic pool ID: {pool_id1}")
    print(f"✓ Different pool ID: {pool_id_different}")


def test_deterministic_hash_consistency():
    """Test that the underlying hash function is consistent."""
    import struct
    import zlib

    # Test the same values multiple times with new hash function
    timeframe = "H1"
    timestamp = datetime(2025, 1, 1, 12, 0, 0)
    top, bottom = 1.1000, 1.0950

    # New hash function includes timeframe and timestamp
    price_bytes = struct.pack("!dd", top, bottom)
    tf_bytes = timeframe.encode("utf-8")
    timestamp_bytes = struct.pack("!q", int(timestamp.timestamp()))
    combined_bytes = tf_bytes + timestamp_bytes + price_bytes

    hash1 = zlib.adler32(combined_bytes) & 0xFFFFFF
    hash2 = zlib.adler32(combined_bytes) & 0xFFFFFF
    hash3 = zlib.adler32(combined_bytes) & 0xFFFFFF

    assert hash1 == hash2 == hash3

    # Different values should give different hashes (most of the time)
    different_bytes = tf_bytes + timestamp_bytes + struct.pack("!dd", 1.2000, 1.1950)
    hash_different = zlib.adler32(different_bytes) & 0xFFFFFF
    assert hash1 != hash_different  # Very unlikely to collide

    print(f"✓ Consistent hash for (1.1000, 1.0950): {hash1:04x}")
    print(f"✓ Different hash for (1.2000, 1.1950): {hash_different:04x}")
