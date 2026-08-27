export function ruleIdentity(rule) {
  return `${rule.rule_id}@${rule.version}`;
}

export function rulesByControl(rules = []) {
  const groups = new Map();
  for (const rule of rules) {
    const current = groups.get(rule.control_key) ?? [];
    current.push(rule);
    groups.set(rule.control_key, current);
  }
  return [...groups.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([controlKey, items]) => ({
      controlKey,
      rules: [...items].sort((left, right) => ruleIdentity(left).localeCompare(ruleIdentity(right))),
    }));
}

export function ruleHistories(rules = []) {
  const groups = new Map();
  for (const rule of rules) {
    const history = groups.get(rule.rule_id) ?? [];
    history.push(rule);
    groups.set(rule.rule_id, history);
  }
  return [...groups.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([ruleId, versions]) => ({
      ruleId,
      versions: [...versions].sort((left, right) => right.version - left.version),
    }));
}

export function policyViewModel({ sources = [], sourceCatalog = [], candidates = [], rules = [], approvals = [], profiles = [], effectiveRuleSet = null, sourceMetrics = [], complianceReadiness = [] }) {
  const approvalByRule = new Map(approvals.map(item => [`${item.rule_id}@${item.version}`, item]));
  const decoratedRules = rules.map(rule => ({
    ...rule,
    approval: approvalByRule.get(ruleIdentity(rule)) ?? null,
    approved: approvalByRule.has(ruleIdentity(rule)),
  }));
  return {
    sources: [...sources]
      .map(source => ({
        ...source,
        processing_status: source.processing_status ?? "NOT_REPORTED",
        processing_error: source.processing_error ?? null,
      }))
      .sort((left, right) => `${left.source_id}@${left.source_version}`.localeCompare(`${right.source_id}@${right.source_version}`)),
    globalSourceDefinitions: [...sourceCatalog]
      .map(source => ({
        ...source,
        frozen: source.frozen === true,
        implementation_status: source.implementation_status ?? "REFERENCE_ONLY",
      }))
      .sort((left, right) => left.source_id.localeCompare(right.source_id)),
    candidates: [...candidates]
      .map(candidate => ({
        ...candidate,
        limitations: candidate.limitations ?? [],
        evidence: candidate.evidence ?? [],
        canApprove: candidate.valid === true && (candidate.limitations ?? []).length === 0,
      }))
      .sort((left, right) => left.candidate_id.localeCompare(right.candidate_id)),
    controlGroups: rulesByControl(decoratedRules),
    ruleHistories: ruleHistories(decoratedRules),
    profiles: [...profiles]
      .map(profile => ({ ...profile, rule_pins: profile.rule_pins ?? [] }))
      .sort((left, right) => `${left.policy_profile_id}@${left.policy_profile_version}`.localeCompare(`${right.policy_profile_id}@${right.policy_profile_version}`)),
    effectiveRuleSet,
    sourceMetrics: [...sourceMetrics].sort((left, right) => left.source_id.localeCompare(right.source_id)),
    complianceReadiness: [...complianceReadiness]
      .map(view => ({
        ...view,
        resultLabel: "Mapping Coverage / Evidence Readiness",
      }))
      .sort((left, right) => left.source_id.localeCompare(right.source_id)),
    overallMetric: null,
    overallMetricExplanation: "Global/Customer Source는 독립 기준이므로 Cross-Source Overall Score를 만들지 않습니다.",
  };
}
