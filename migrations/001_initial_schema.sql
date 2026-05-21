-- Migration 001: Initial Schema
-- Per spec: migration_log must exist and be populated BEFORE any other table creation.

CREATE TABLE IF NOT EXISTS migration_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    executed_by TEXT NOT NULL DEFAULT 'system'
);

INSERT OR IGNORE INTO migration_log (version, description, executed_by)
VALUES ('001', 'Initial schema: all core tables', 'system');

-- Prompt registry: every agent prompt must be registered here before use.
CREATE TABLE IF NOT EXISTS prompt_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_name TEXT NOT NULL,
    version TEXT NOT NULL,
    agent_type TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    description TEXT,
    is_active INTEGER DEFAULT 1,
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(prompt_name, version)
);

-- Approval policy rules (source of truth for approval routing agent).
CREATE TABLE IF NOT EXISTS policy_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL,
    min_value REAL NOT NULL DEFAULT 0,
    max_value REAL,
    currency TEXT NOT NULL DEFAULT 'USD',
    approver_level_1 TEXT NOT NULL,
    approver_level_2 TEXT,
    approver_level_3 TEXT,
    dual_approval_required INTEGER NOT NULL DEFAULT 0,
    escalation_condition TEXT,
    sla_hours INTEGER NOT NULL DEFAULT 24,
    description TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Inbound purchase requests.
CREATE TABLE IF NOT EXISTS purchase_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT UNIQUE NOT NULL,
    requester TEXT NOT NULL,
    supplier_name TEXT,
    category TEXT NOT NULL,
    value REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    description TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    pilot_team TEXT,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Approval routing decisions produced by the Approval Routing Agent.
CREATE TABLE IF NOT EXISTS approval_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    policy_rule_id TEXT,
    approval_chain TEXT NOT NULL DEFAULT '[]',
    escalation_condition TEXT,
    sla_hours INTEGER,
    status TEXT NOT NULL DEFAULT 'pending',
    routing_confidence REAL,
    is_policy_gap INTEGER NOT NULL DEFAULT 0,
    decided_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (request_id) REFERENCES purchase_requests(request_id)
);

-- Supplier scores produced by the Supplier Scoring Agent.
CREATE TABLE IF NOT EXISTS supplier_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_name TEXT NOT NULL,
    request_id TEXT,
    reliability_score REAL,
    compliance_score REAL,
    cost_score REAL,
    risk_score REAL,
    fit_score REAL,
    composite_score REAL,
    status TEXT,
    source_chunks TEXT DEFAULT '{}',
    prompt_version TEXT NOT NULL,
    confidence REAL,
    scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Process improvement findings produced by the Process Discovery Agent.
CREATE TABLE IF NOT EXISTS process_backlog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id TEXT UNIQUE NOT NULL,
    workflow TEXT NOT NULL,
    bottleneck TEXT NOT NULL,
    root_cause_hypothesis TEXT,
    effort TEXT NOT NULL,
    impact TEXT NOT NULL,
    score INTEGER NOT NULL,
    recommended_action TEXT,
    status TEXT NOT NULL DEFAULT 'backlog',
    discovered_date TEXT NOT NULL,
    pilot_team TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Audit log: every inter-agent transition and agent action is written here.
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    agent TEXT NOT NULL,
    action TEXT NOT NULL,
    request_id TEXT,
    confidence REAL,
    policy_rule TEXT,
    prompt_version TEXT,
    pilot_team TEXT,
    slack_channel TEXT,
    status TEXT,
    context_payload_hash TEXT,
    source_agent TEXT,
    target_agent TEXT,
    triggering_condition TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Rolling aggregate metrics (one row per calendar date).
CREATE TABLE IF NOT EXISTS metrics_aggregate (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_date TEXT NOT NULL UNIQUE,
    requests_processed INTEGER NOT NULL DEFAULT 0,
    supplier_scores_generated INTEGER NOT NULL DEFAULT 0,
    approval_decisions_made INTEGER NOT NULL DEFAULT 0,
    avg_approval_cycle_hours REAL NOT NULL DEFAULT 0,
    escalation_rate REAL NOT NULL DEFAULT 0,
    policy_gap_count INTEGER NOT NULL DEFAULT 0,
    process_findings_count INTEGER NOT NULL DEFAULT 0,
    agent_invocations TEXT NOT NULL DEFAULT '{}',
    avg_confidence REAL NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Per-pilot metrics partition.
CREATE TABLE IF NOT EXISTS pilot_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pilot_team TEXT NOT NULL,
    stage INTEGER NOT NULL DEFAULT 1,
    active_users INTEGER NOT NULL DEFAULT 0,
    requests_processed INTEGER NOT NULL DEFAULT 0,
    routing_accuracy REAL NOT NULL DEFAULT 0,
    avg_scoring_confidence REAL NOT NULL DEFAULT 0,
    stakeholder_satisfaction REAL NOT NULL DEFAULT 0,
    open_feedback_items INTEGER NOT NULL DEFAULT 0,
    prompt_version TEXT NOT NULL,
    blockers TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'active',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(pilot_team, stage)
);

-- Stakeholder feedback entries.
CREATE TABLE IF NOT EXISTS stakeholder_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pilot_team TEXT,
    request_id TEXT,
    rating INTEGER CHECK(rating BETWEEN 1 AND 5),
    feedback_text TEXT,
    submitted_by TEXT,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
