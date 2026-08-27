import React from "react";
import { policyViewModel, ruleIdentity } from "./model.mjs";

export function PolicyGovernancePanel(props) {
  const view = policyViewModel(props);
  return <main aria-label="Policy Governance">
    <section aria-label="Policy Sources">
      <h2>Policy Sources</h2>
      <ul>{view.sources.map(source => <li key={`${source.source_id}@${source.source_version}`}>
        {source.source_id} · {source.source_type} · {source.source_version} · {source.processing_status}
        {source.processing_error && <span role="alert"> · {source.processing_error}</span>}
        {props.onManageSource && <button type="button" onClick={() => props.onManageSource(source)}>Source 관리</button>}
      </li>)}</ul>
    </section>

    <section aria-label="Global Source Scope">
      <h2>Global Source 적용 범위</h2>
      <ul>{view.globalSourceDefinitions.map(source => <li key={source.source_id}>
        {source.source_id} · {source.publisher} · {source.framework_version ?? "catalog snapshot"} · {source.role} · {source.implementation_status}
        {!source.frozen && <strong> · Frozen Snapshot 필요</strong>}
        {source.score_label && <span> · {source.score_label}</span>}
        {source.required_capabilities?.length > 0 && <small> · Required context: {source.required_capabilities.join(", ")}</small>}
        {source.global_evaluation_scope?.length > 0 && <ul>{source.global_evaluation_scope.map(item => <li key={item}>Scope: {item}</li>)}</ul>}
        {source.customer_defined_scope?.length > 0 && <ul>{source.customer_defined_scope.map(item => <li key={item}>Customer Policy: {item}</li>)}</ul>}
      </li>)}</ul>
    </section>

    <section aria-label="Rule Candidates">
      <h2>Rule Candidates</h2>
      <ul>{view.candidates.map(candidate => <li key={candidate.candidate_id}>
        <strong>{candidate.candidate_id}</strong> · {candidate.source_type} · {candidate.valid ? "STRUCTURED" : "INVALID"} · HUMAN REVIEW REQUIRED
        <ul>{candidate.evidence.map(item => <li key={`${item.source_reference.document_id}@${item.source_reference.document_version}#${item.source_reference.section}`}>
          {item.source_reference.document_id}@{item.source_reference.document_version}#{item.source_reference.section} · {item.locator}
          {item.excerpt && <blockquote>{item.excerpt}</blockquote>}
        </li>)}</ul>
        {candidate.limitations.length > 0 && <ul>{candidate.limitations.map(item => <li key={item}>Limitation: {item}</li>)}</ul>}
        {candidate.canApprove && props.onReviewCandidate && <button type="button" onClick={() => props.onReviewCandidate(candidate)}>승인 검토</button>}
      </li>)}</ul>
    </section>

    <section aria-label="Rule Registry and Approval">
      <h2>Rule Registry / Approval</h2>
      {view.controlGroups.map(group => <article key={group.controlKey}>
        <h3>{group.controlKey}</h3>
        <ul>{group.rules.map(rule => <li key={ruleIdentity(rule)}>
          {ruleIdentity(rule)} · {rule.source_type} · {rule.evaluation_type} · {rule.severity} · {rule.status} · {rule.approved ? "APPROVED" : "REVIEW REQUIRED"}
          {rule.approval && <small> · hash {rule.approval.rule_content_hash} · by {rule.approval.approved_by} at {rule.approval.approved_at}</small>}
          {!rule.approved && props.onApproveRule && <button type="button" onClick={() => props.onApproveRule(rule)}>승인 검토</button>}
        </li>)}</ul>
      </article>)}
    </section>

    <section aria-label="Policy Profiles">
      <h2>Policy Profiles</h2>
      <ul>{view.profiles.map(profile => <li key={`${profile.policy_profile_id}@${profile.policy_profile_version}`}>
        <button type="button" onClick={() => props.onSelectProfile?.(profile)}>{profile.policy_profile_id}@{profile.policy_profile_version}</button>
        <ul>{profile.rule_pins.map(pin => <li key={`${pin.rule_id}@${pin.version}`}>{pin.rule_id}@{pin.version}</li>)}</ul>
      </li>)}</ul>
    </section>

    <section aria-label="Effective Rule Set">
      <h2>Effective Rule Set</h2>
      {view.effectiveRuleSet ? <>
        <p>{view.effectiveRuleSet.phase} · {view.effectiveRuleSet.rule_set_hash}</p>
        <p>Admin Settings: {view.effectiveRuleSet.admin_settings_snapshot_hash}</p>
        <ul>{view.effectiveRuleSet.rules.map(rule => <li key={ruleIdentity(rule)}>{ruleIdentity(rule)} · {rule.source_type}</li>)}</ul>
      </> : <p>선택된 Effective Rule Set이 없습니다.</p>}
    </section>

    <section aria-label="Source Score and Coverage">
      <h2>Source별 Score / Coverage</h2>
      <p>{view.overallMetricExplanation}</p>
      <ul>{view.sourceMetrics.map(metric => <li key={metric.source_id}>
        {metric.source_id} · Score {metric.score ?? "N/A"} · Coverage {metric.coverage ?? "N/A"} · Scoring v{metric.scoring_version}
        <small> · PASS {metric.pass_count ?? 0} · FAIL {metric.fail_count ?? 0} · N/A {metric.not_applicable_count ?? 0} · Manual {metric.manual_review_count ?? 0} · Error {metric.execution_error_count ?? 0}</small>
      </li>)}</ul>
    </section>

    <section aria-label="Compliance Mapping and Evidence Readiness">
      <h2>Compliance Mapping / Evidence Readiness</h2>
      <p>Mapping Coverage는 준수율이나 인증 가능성을 의미하지 않습니다.</p>
      <ul>{view.complianceReadiness.map(readiness => <li key={`${readiness.source_id}@${readiness.source_version}`}>
        {readiness.source_id}@{readiness.source_version} · Mapping Coverage {readiness.mapping_coverage ?? "N/A"} · Compliance Score 없음
        <ul>{Object.entries(readiness.evidence_status_counts ?? {}).map(([status, count]) => <li key={status}>{status}: {count}</li>)}</ul>
      </li>)}</ul>
    </section>
  </main>;
}
