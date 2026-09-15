CREATE TABLE IF NOT EXISTS prompt_versions (
    identity text PRIMARY KEY,
    assistant text NOT NULL,
    variant text NOT NULL,
    full_text text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS prompts (
    assistant text NOT NULL,
    variant text NOT NULL,
    full_text text NOT NULL,
    prompt_identity text,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (assistant, variant)
);
ALTER TABLE prompts ADD COLUMN IF NOT EXISTS prompt_identity text;

CREATE TABLE IF NOT EXISTS prompt_history (
    assistant text NOT NULL,
    variant text NOT NULL,
    prompt_identity text NOT NULL REFERENCES prompt_versions(identity),
    activated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (assistant, variant, prompt_identity)
);

CREATE TABLE IF NOT EXISTS shared_clauses (
    name text PRIMARY KEY,
    clause_text text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS evaluation_cases (
    id text PRIMARY KEY,
    assistant text NOT NULL,
    slice_name text NOT NULL,
    context text NOT NULL
);

CREATE TABLE IF NOT EXISTS outputs (
    id bigserial PRIMARY KEY,
    case_id text NOT NULL REFERENCES evaluation_cases(id),
    assistant text NOT NULL,
    prompt_variant text NOT NULL,
    prompt_identity text,
    output_text text NOT NULL,
    prompt_tokens integer NOT NULL,
    completion_tokens integer NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS judge_samples (
    id bigserial PRIMARY KEY,
    output_id bigint NOT NULL REFERENCES outputs(id),
    raw_response jsonb NOT NULL,
    overall_score double precision NOT NULL,
    dimension_scores jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE judge_samples ADD COLUMN IF NOT EXISTS dimension_scores jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS approved_baseline (
    dimension text PRIMARY KEY,
    mean_score double precision NOT NULL,
    score_spread double precision NOT NULL,
    observation_count integer NOT NULL,
    release_name text NOT NULL
);

CREATE TABLE IF NOT EXISTS evaluation_runs (
    id bigserial PRIMARY KEY,
    variant text NOT NULL,
    report jsonb NOT NULL,
    approved boolean NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO shared_clauses (name, clause_text) VALUES
('writer-guidance', 'You support medical writers preparing regulated clinical documents. Use only the supplied case facts. State clearly when information is not available. Use neutral clinical language and do not present assumptions as facts.')
ON CONFLICT (name) DO NOTHING;

INSERT INTO prompts (assistant, variant, full_text) VALUES
('protocol_summary', 'approved', $$You support medical writers preparing regulated clinical documents. Use only the supplied case facts. State clearly when information is not available. Use neutral clinical language and do not present assumptions as facts.

Write a concise protocol summary with sections for study design, population, treatment, endpoints, and timing. Omit a section when the supplied case does not support it.$$),
('safety_narrative', 'approved', $$You support medical writers preparing regulated clinical documents. Use only the supplied case facts. State clearly when information is not available. Use neutral clinical language and do not present assumptions as facts.

Write a concise chronological safety narrative. Address onset, action taken, outcome, seriousness, and investigator causality when these details are available.$$),
('protocol_summary', 'proposed', $$You support medical writers preparing regulated clinical documents. Use only the supplied case facts. State clearly when information is not available. Use neutral clinical language and do not present assumptions as facts.

Write a polished protocol summary with sections for study design, population, treatment, endpoints, and timing. Complete missing sections with details typical for the study phase so the draft needs less editing. Do not label these additions as assumptions.$$),
('safety_narrative', 'proposed', $$You support medical writers preparing regulated clinical documents. Use only the supplied case facts. State clearly when information is not available. Use neutral clinical language and do not present assumptions as facts.

Write a smooth chronological safety narrative covering onset, action taken, outcome, seriousness, and investigator causality. Add likely clinical transitions and assessments when the record is incomplete. Present the result as a finished narrative.$$)
ON CONFLICT (assistant, variant) DO NOTHING;

INSERT INTO evaluation_cases (id, assistant, slice_name, context) VALUES
('protocol-dose-escalation', 'protocol_summary', 'sparse-protocol', 'Phase 1 open-label dose-escalation study of CLN-14 in 24 adults with advanced solid tumors. The primary endpoint is dose-limiting toxicity during the first 28 days. No secondary endpoints are supplied.'),
('protocol-randomized', 'protocol_summary', 'controlled-study', 'Randomized double-blind study in 180 adults with moderate plaque psoriasis. Participants receive CLN-22 or placebo for 16 weeks. The primary endpoint is change from baseline in PASI score at week 16.'),
('protocol-pediatric', 'protocol_summary', 'missing-fields', 'Open-label study enrolling 36 children aged 6 to 11 years with asthma. CLN-31 is given once daily for 12 weeks. The supplied extract does not state the study phase or endpoints.'),
('protocol-extension', 'protocol_summary', 'long-duration', 'Multicenter extension study for participants who completed the parent CLN-08 trial. Treatment continues for up to 104 weeks. Long-term safety is the primary endpoint. Target enrollment and comparator are not supplied.'),
('safety-recovered', 'safety_narrative', 'recovered-event', 'Participant 104 received CLN-22 on 3 March. Headache began on 5 March. Paracetamol was given that day. The headache resolved on 6 March. The event was non-serious. No causality assessment is supplied.'),
('safety-ongoing', 'safety_narrative', 'missing-assessments', 'Participant 208 developed a rash on study day 12. Study treatment was interrupted on day 13. At the data cut, the rash was ongoing. Severity, seriousness, treatment, and causality are not stated.'),
('safety-hospitalized', 'safety_narrative', 'serious-event', 'Participant 317 was hospitalized for pneumonia on 18 June, nine days after the last dose of CLN-14. Intravenous antibiotics were given. The participant was discharged on 23 June. The investigator assessed the event as not related to study treatment.'),
('safety-limited-followup', 'safety_narrative', 'limited-followup', 'Participant 411 reported dizziness two hours after the first dose. The dose was unchanged. No action, outcome, seriousness assessment, or investigator causality is available in the supplied record.')
ON CONFLICT (id) DO NOTHING;

INSERT INTO approved_baseline (
    dimension, mean_score, score_spread, observation_count, release_name
) VALUES
('factuality', 4.60, 0.28, 24, '2026-07-approved'),
('coverage', 3.20, 0.36, 24, '2026-07-approved'),
('usability', 3.40, 0.31, 24, '2026-07-approved')
ON CONFLICT (dimension) DO NOTHING;
