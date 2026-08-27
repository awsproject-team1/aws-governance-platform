import test from "node:test";
import assert from "node:assert/strict";
import { policyViewModel, rulesByControl } from "../../apps/frontend/src/policy/model.mjs";

test("same-control source rules remain independent", () => {
  const rules = [
    { rule_id: "GLOBAL-S3-PAB-001", version: 1, source_type: "GLOBAL", control_key: "s3.public_access_block.enabled" },
    { rule_id: "CUSTOMER-S3-PAB-003", version: 2, source_type: "CUSTOMER", control_key: "s3.public_access_block.enabled" },
  ];
  const groups = rulesByControl(rules);
  assert.equal(groups.length, 1);
  assert.equal(groups[0].rules.length, 2);
  assert.deepEqual(groups[0].rules.map(item => item.source_type).sort(), ["CUSTOMER", "GLOBAL"]);
});

test("approval and source metrics are presented without an overall metric", () => {
  const view = policyViewModel({
    rules: [{ rule_id: "GLOBAL-S3-PAB-001", version: 1, control_key: "s3.public_access_block.enabled" }],
    approvals: [{ rule_id: "GLOBAL-S3-PAB-001", version: 1 }],
    sourceMetrics: [{ source_id: "aws-fsbp-1-0-0", score: 100, coverage: 100 }],
  });
  assert.equal(view.controlGroups[0].rules[0].approved, true);
  assert.equal(view.sourceMetrics.length, 1);
  assert.equal(view.overallMetric, null);
  assert.match(view.overallMetricExplanation, /Overall Score/);
});

test("source processing, candidate evidence, limitations, and rule history remain explicit", () => {
  const view = policyViewModel({
    sources: [{ source_id: "customer-policy", source_version: "2", source_type: "CUSTOMER", processing_status: "FAILED", processing_error: "OCR_REQUIRED" }],
    candidates: [{
      candidate_id: "candidate-2",
      source_type: "CUSTOMER",
      valid: true,
      limitations: ["scope is unresolved"],
      evidence: [{ source_reference: { document_id: "customer-policy", document_version: "2", section: "storage", content_hash: "sha256:x" }, locator: "pdf:page=1/block=2" }],
    }],
    rules: [
      { rule_id: "CUSTOMER-S3-ENC-001", version: 1, control_key: "s3.encryption.at_rest" },
      { rule_id: "CUSTOMER-S3-ENC-001", version: 2, control_key: "s3.encryption.at_rest" },
    ],
    profiles: [{ policy_profile_id: "profile-1", policy_profile_version: 2, rule_pins: [{ rule_id: "CUSTOMER-S3-ENC-001", version: 2 }] }],
  });

  assert.equal(view.sources[0].processing_error, "OCR_REQUIRED");
  assert.equal(view.candidates[0].canApprove, false);
  assert.equal(view.candidates[0].evidence[0].locator, "pdf:page=1/block=2");
  assert.deepEqual(view.ruleHistories[0].versions.map(item => item.version), [2, 1]);
  assert.equal(view.profiles[0].rule_pins[0].version, 2);
});

test("Global Source definitions and ISMS readiness never become an overall or compliance score", () => {
  const view = policyViewModel({
    sourceCatalog: [
      {
        source_id: "aws-fsbp-1-0-0",
        publisher: "AWS",
        framework_version: "1.0.0",
        role: "SECURITY_BASELINE",
        score_label: "FSBP 기반 Governance Score",
      },
      {
        source_id: "isms-p-2023-11-23",
        publisher: "KISA 및 관계기관",
        framework_version: "2023.11.23",
        role: "MAPPING_EVIDENCE",
        score_label: null,
      },
    ],
    complianceReadiness: [
      {
        source_id: "isms-p-2023-11-23",
        source_version: "2023.11.23",
        mapping_coverage: 33.3,
        evidence_status_counts: { MANUAL_REVIEW: 1 },
      },
    ],
  });
  assert.equal(view.globalSourceDefinitions[0].implementation_status, "REFERENCE_ONLY");
  assert.equal(view.globalSourceDefinitions[0].frozen, false);
  assert.equal("complianceScore" in view.complianceReadiness[0], false);
  assert.equal(view.overallMetric, null);
});
