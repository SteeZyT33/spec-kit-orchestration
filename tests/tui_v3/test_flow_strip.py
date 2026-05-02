"""Flow strip: 8-glyph progress meter from FlowStateResult."""
from orca.flow_state import FlowMilestone
from orca.tui.flow_strip import render_strip, plain_strip, STAGE_GLYPHS


def test_glyph_order_matches_stage_order():
    assert STAGE_GLYPHS == ["br", "sp", "pl", "ta", "im", "rs", "rc", "rp"]


def test_plain_strip_all_not_started():
    milestones = [FlowMilestone(stage=name, status="not_started")
                  for name in ["brainstorm", "specify", "plan", "tasks",
                               "implement", "review-spec", "review-code",
                               "review-pr"]]
    assert plain_strip(milestones) == "br·sp·pl·ta·im·rs·rc·rp"


def test_plain_strip_specify_in_progress():
    statuses = ["complete", "in_progress", "not_started", "not_started",
                "not_started", "not_started", "not_started", "not_started"]
    names = ["brainstorm", "specify", "plan", "tasks",
             "implement", "review-spec", "review-code", "review-pr"]
    milestones = [FlowMilestone(stage=n, status=s)
                  for n, s in zip(names, statuses)]
    assert plain_strip(milestones) == "br·SP·pl·ta·im·rs·rc·rp"


def test_plain_strip_blocked_at_review_code():
    statuses = ["complete", "complete", "complete", "complete",
                "complete", "complete", "blocked", "not_started"]
    names = ["brainstorm", "specify", "plan", "tasks",
             "implement", "review-spec", "review-code", "review-pr"]
    milestones = [FlowMilestone(stage=n, status=s)
                  for n, s in zip(names, statuses)]
    assert plain_strip(milestones) == "br·sp·pl·ta·im·rs·RC·rp"


def test_render_strip_returns_rich_text():
    from rich.text import Text
    milestones = [FlowMilestone(stage="brainstorm", status="complete")]
    out = render_strip(milestones + [FlowMilestone(stage=n, status="not_started")
                                      for n in ["specify", "plan", "tasks",
                                                "implement", "review-spec",
                                                "review-code", "review-pr"]])
    assert isinstance(out, Text)
    assert out.plain == "br·sp·pl·ta·im·rs·rc·rp"
