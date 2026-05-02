"""Tests for FeatureCard widget render."""
from __future__ import annotations


def test_feature_card_renders_four_lines():
    from orca.tui.kanban import CardData, KanbanColumn
    from orca.tui.cards import FeatureCard

    data = CardData(
        feature_id="001-orca-worktree-runtime",
        column=KanbanColumn.PLAN,
        branch="001-orca-worktree-runtime",
        worktree_path="/tmp/wt",
        worktree_status="clean",
        review_summary="spec missing",
    )
    card = FeatureCard(data)
    text = card._content_lines()
    assert len(text) == 4
    assert "001-orca-worktree-runtime" in text[0]
    assert "001-orca-worktree-runtime" in text[1]
    assert "clean" in text[2]
    assert "spec missing" in text[3]


def test_feature_card_renders_no_worktree_placeholder():
    from orca.tui.kanban import CardData, KanbanColumn
    from orca.tui.cards import FeatureCard

    data = CardData(feature_id="001-foo", column=KanbanColumn.SPEC)
    card = FeatureCard(data)
    text = card._content_lines()
    body = "\n".join(text)
    assert "(no worktree)" in body
