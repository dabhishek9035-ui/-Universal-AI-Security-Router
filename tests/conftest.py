"""Shared test setup: point data dir at a temp dir before any app import."""
import os
import tempfile

os.environ["AI_ROUTER_DATA_DIR"] = tempfile.mkdtemp(prefix="ai_router_test_")
