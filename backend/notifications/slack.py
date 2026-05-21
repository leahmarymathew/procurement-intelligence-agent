"""
Slack notification system.
All five trigger events use structured Block Kit templates.
Raw data is NEVER posted directly — every call goes through a typed template function.
"""
from __future__ import annotations
from typing import Optional
from ..config import settings

# Channel map per spec
CHANNELS = {
    "escalation":  "#procurement-alerts",
    "supplier":    "#supplier-intel",
    "backlog":     "#ops-process",
    "report":      "#procurement-weekly",
    "pilot":       "#pilot-ops",
}


def _client():
    from slack_sdk.web.async_client import AsyncWebClient
    return AsyncWebClient(token=settings.slack_bot_token)


def _deep_link(path: str) -> str:
    return f"{settings.dashboard_base_url.rstrip('/')}{path}"


def _divider() -> dict:
    return {"type": "divider"}


def _section(text: str) -> dict:
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def _header(text: str) -> dict:
    return {"type": "header", "text": {"type": "plain_text", "text": text, "emoji": True}}


async def _post(channel: str, blocks: list[dict], fallback: str) -> bool:
    if not settings.slack_bot_token:
        print(f"[slack] MOCK post to {channel}: {fallback}")
        return True
    try:
        cl = _client()
        resp = await cl.chat_postMessage(channel=channel, blocks=blocks, text=fallback)
        return resp["ok"]
    except Exception as exc:
        print(f"[slack] error posting to {channel}: {exc}")
        return False


async def send_escalation_alert(
    request_id: str,
    requester: str,
    value: float,
    currency: str,
    category: str,
    escalation_reason: str,
    pilot_team: Optional[str] = None,
) -> bool:
    """Triggered: new P1 escalation in the approval chain."""
    channel = CHANNELS["escalation"]
    link = _deep_link(f"/procurement/request/{request_id}")
    blocks = [
        _header("P1 Escalation — Approval Required"),
        _divider(),
        _section(
            f"*Request ID:* `{request_id}`\n"
            f"*Requester:* {requester}\n"
            f"*Value:* {currency} {value:,.2f}\n"
            f"*Category:* {category}\n"
            f"*Pilot Team:* {pilot_team or 'N/A'}"
        ),
        _section(f"*Escalation Reason:* {escalation_reason}"),
        _section(f"<{link}|View in Dashboard>"),
    ]
    return await _post(channel, blocks, f"P1 Escalation: {request_id} — {category} {currency}{value:,.2f}")


async def send_supplier_flag(
    supplier_name: str,
    composite_score: float,
    status: str,
    category: str,
    top_concern: str,
    score_record_id: Optional[int] = None,
    pilot_team: Optional[str] = None,
) -> bool:
    """Triggered: supplier scored as watch-list or disqualified."""
    if status not in ("watch-list", "disqualified"):
        return False
    channel = CHANNELS["supplier"]
    link = _deep_link(f"/supplier/scores")
    emoji = "⚠️" if status == "watch-list" else "🚫"
    blocks = [
        _header(f"{emoji} Supplier Flag: {status.upper()}"),
        _divider(),
        _section(
            f"*Supplier:* {supplier_name}\n"
            f"*Category:* {category}\n"
            f"*Composite Score:* {composite_score:.1f}/10\n"
            f"*Status:* *{status}*\n"
            f"*Pilot Team:* {pilot_team or 'N/A'}"
        ),
        _section(f"*Primary Concern:* {top_concern}"),
        _section(f"<{link}|View Supplier Scores>"),
    ]
    return await _post(
        channel, blocks,
        f"Supplier flag [{status}]: {supplier_name} scored {composite_score:.1f}/10"
    )


async def send_backlog_alert(
    finding_id: str,
    workflow: str,
    bottleneck: str,
    score: int,
    recommended_action: str,
    pilot_team: Optional[str] = None,
) -> bool:
    """Triggered: process finding scored 7 or above."""
    if score < 7:
        return False
    channel = CHANNELS["backlog"]
    link = _deep_link(f"/process/backlog/{finding_id}")
    blocks = [
        _header(f"High-Priority Process Finding (Score: {score}/9)"),
        _divider(),
        _section(
            f"*Finding ID:* `{finding_id}`\n"
            f"*Workflow:* {workflow}\n"
            f"*Bottleneck:* {bottleneck}\n"
            f"*Pilot Team:* {pilot_team or 'N/A'}"
        ),
        _section(f"*Recommended Action:* {recommended_action}"),
        _section(f"<{link}|View in Process Backlog>"),
    ]
    return await _post(
        channel, blocks,
        f"Process finding [{finding_id}] scored {score}/9: {bottleneck}"
    )


async def send_weekly_report(
    headline: str,
    highlights: list[str],
    concerns: list[str],
    top_backlog_actions: list[str],
    feedback_discrepancy: Optional[str],
    recommended_focus: str,
    pilot_team: Optional[str] = None,
) -> bool:
    """Triggered: weekly insight report published."""
    channel = CHANNELS["report"]
    link = _deep_link("/reports/weekly")
    highlights_text = "\n".join(f"• {h}" for h in highlights)
    concerns_text = "\n".join(f"• {c}" for c in concerns)
    actions_text = "\n".join(f"• {a}" for a in top_backlog_actions)
    blocks = [
        _header("Weekly Procurement Insight Report"),
        _divider(),
        _section(f"*{headline}*"),
        _section(f"*Highlights:*\n{highlights_text}"),
        _section(f"*Concerns:*\n{concerns_text}"),
        _section(f"*Top Backlog Actions:*\n{actions_text}"),
    ]
    if feedback_discrepancy:
        blocks.append(_section(f"*Feedback Discrepancy:* {feedback_discrepancy}"))
    blocks += [
        _section(f"*Recommended Focus:* {recommended_focus}"),
        _section(f"<{link}|View Full Report>"),
    ]
    return await _post(channel, blocks, f"Weekly Report: {headline}")


async def send_pilot_milestone(
    pilot_team: str,
    milestone: str,
    stage: int,
    detail: str,
) -> bool:
    """Triggered: pilot stage milestone reached."""
    channel = CHANNELS["pilot"]
    link = _deep_link(f"/pilot/{pilot_team}")
    blocks = [
        _header(f"Pilot Milestone: {pilot_team}"),
        _divider(),
        _section(
            f"*Team:* {pilot_team}\n"
            f"*Stage:* {stage}\n"
            f"*Milestone:* {milestone}"
        ),
        _section(detail),
        _section(f"<{link}|View Pilot Dashboard>"),
    ]
    return await _post(channel, blocks, f"Pilot milestone [{pilot_team} Stage {stage}]: {milestone}")
