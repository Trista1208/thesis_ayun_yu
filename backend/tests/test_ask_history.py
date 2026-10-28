"""Ask Joule keeps a member's questions and answers, and can erase them."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.ai.ask_history import delete_ask_history, list_ask_history, save_ask_exchange  # noqa: E402


def test_save_then_clear_ask_history():
    user_id = "test-ask-history-user"
    delete_ask_history(user_id)
    try:
        saved = save_ask_exchange(
            user_id,
            question="How should I train this week?",
            answer="Two strength sessions and one Zone 2 ride.",
            mode="cited",
            confidence="high",
        )
        assert saved is not None
        rows = list_ask_history(user_id)
        assert rows[-1]["question"] == "How should I train this week?"
        assert "Zone 2" in rows[-1]["answer"]
        assert delete_ask_history(user_id) >= 1
        assert list_ask_history(user_id) == []
    finally:
        delete_ask_history(user_id)
