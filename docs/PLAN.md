# Preflop Web/HTTP MVP Evaluation Plan

## Goals
- Validate the existing Preflop Web/HTTP MVP can be run in production within this week.
- Confirm core user journeys remain reliable under projected launch traffic and failure scenarios.
- Deliver hand-off artifacts so on-call owners can operate and monitor the service post-launch.

## Scope
- Production-readiness review of the current MVP build and infrastructure.
- Deployment pipeline verification from staging to production, including rollback paths.
- Observability baseline: logs, metrics, traces, alerts, dashboards, SLO/SLA definitions.
- Lean documentation updates needed for runbooks, incident response, and stakeholder sign-off.

## Assumptions
- Existing staging and production environments are available with environment parity.
- Core dependencies (datastores, external APIs, auth) have test doubles or sandboxes for validation.
- Traffic projections and target SLOs are already approved by stakeholders.
- Dedicated triage owner and an SRE partner are available during the evaluation window.

## Work Plan (Timeline)
- **Day 0 (Today, T+0-4h):** Kickoff sync, review open risks, freeze non-essential changes, gather deployment + monitoring artifacts.
- **Day 1 (T+4-12h):** Run smoke tests against staging → production; verify deploy + rollback; document gaps.
- **Day 2 (T+12-24h):** Execute targeted load/performance tests using launch traffic model; stress error paths and throttling.
- **Day 3 (T+24-36h):** Harden observability (alerts, dashboards, runbooks); implement critical fixes; re-test high-risk flows.
- **Day 4 (T+36-48h):** Conduct security & dependency review (OWASP top issues, dependency scanning, secrets checks).
- **Day 5 (T+48-60h):** Final go/no-go rehearsal, stakeholder walkthrough, confirm on-call rotation + escalation tree.

## Milestones
- M1: Kickoff complete, ownership + checklist confirmed (Day 0).
- M2: Staging and production smoke test reports published, rollback validated (Day 1).
- M3: Load/performance validation with metrics vs targets documented (Day 2).
- M4: Observability + runbooks updated and reviewed with SRE/on-call (Day 3).
- M5: Security/dependency review sign-off (Day 4).
- M6: Final readiness review + launch decision (Day 5).

## Risks/Mitigations
- **Unclear scope or missing requirements:** Schedule stakeholder Q&A early; capture open questions in daily sync notes.
- **Infrastructure or dependency instability:** Engage platform/infra owners for standby support; prepare feature flags and rollback scripts.
- **Insufficient observability:** Prioritize alert and dashboard gaps in Day 3 sprint; fail readiness check if coverage insufficient.
- **Limited headcount/time:** Enforce scope discipline, focus on critical flows first, time-box exploratory testing.
- **Unexpected security findings:** Pre-allocate buffer in Day 4 for remediation; have exception process documented.

## Validation
- Smoke tests: automated and manual checklists covering authentication, primary API endpoints, and core UI flows.
- Performance: load test at 1.5× projected traffic with P95 latency ≤ target and error rate <1%.
- Resilience: chaos scenarios (dependency failure, slow downstream) executed in staging with documented outcomes and mitigations.
- Observability: alert run-through with paging simulation; dashboards reviewed for key metrics (latency, saturation, errors, throughput).
- Documentation: runbook, deployment checklist, and on-call guide updated and stored in repo/Confluence with owners assigned.

## Open Questions
- Do we have written acceptance criteria for success/failure during load testing?
- What SLA commitments exist for partner teams relying on the MVP service?
- Are there compliance or data residency checks required before launch?
