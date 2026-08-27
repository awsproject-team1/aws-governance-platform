import importlib.util
import json
import sys
import unittest
from pathlib import Path

from packages.contracts.governance import (
    ContractValidationError,
    Control,
    EvidenceResultStatus,
    PolicySource,
    SourceControlMapping,
)
from packages.governance.controls.registry import ControlRegistry
from packages.governance.mappings.registry import SourceControlMappingRegistry
from packages.governance.sources.registry import PolicySourceRegistry

REPO = Path(__file__).resolve().parents[2]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


POLICY_TOOL = load_module("policy_knowledge_port", REPO / "tools" / "policy-knowledge" / "port.py")
EXTERNAL_TOOL = load_module(
    "external_evidence_port", REPO / "tools" / "external-evidence" / "port.py"
)


def fixtures():
    rules = json.loads(
        (REPO / "fixtures" / "rules" / "governance-golden.json").read_text(encoding="utf-8")
    )
    policy = json.loads(
        (REPO / "fixtures" / "policy" / "evidence-golden.json").read_text(encoding="utf-8")
    )
    controls = ControlRegistry([Control.from_dict(item) for item in rules["controls"]])
    sources = PolicySourceRegistry(
        [PolicySource.from_dict(item) for item in rules["policy_sources"]]
    )
    mappings = SourceControlMappingRegistry(
        controls, sources, [SourceControlMapping.from_dict(item) for item in rules["mappings"]]
    )
    return policy, mappings


class PolicyKnowledgeTests(unittest.TestCase):
    def test_found_not_found_and_error_are_distinct(self):
        policy, mappings = fixtures()
        service = POLICY_TOOL.PolicyKnowledgeService(
            POLICY_TOOL.FixturePolicyKnowledgeAdapter(policy["evidence"]), mappings
        )
        found = service.query("Block Public Access", ["aws-fsbp-1-0-0"])
        missing = service.query("unrelated phrase", ["aws-fsbp-1-0-0"])

        class FailingAdapter:
            def search(self, query, allowed_source_ids):
                raise RuntimeError("untrusted adapter detail")

        failed = POLICY_TOOL.PolicyKnowledgeService(FailingAdapter(), mappings).query(
            "anything", ["aws-fsbp-1-0-0"]
        )
        self.assertIs(found.status, EvidenceResultStatus.FOUND)
        self.assertIs(missing.status, EvidenceResultStatus.NOT_FOUND)
        self.assertIs(failed.status, EvidenceResultStatus.ERROR)
        self.assertEqual(failed.error_code, "POLICY_KNOWLEDGE_TOOL_ERROR")

    def test_unregistered_source_evidence_is_rejected(self):
        policy, mappings = fixtures()
        untrusted = json.loads(json.dumps(policy["evidence"]))
        untrusted[0]["source_reference"]["section"] = "UNKNOWN"
        service = POLICY_TOOL.PolicyKnowledgeService(
            POLICY_TOOL.FixturePolicyKnowledgeAdapter(untrusted), mappings
        )
        with self.assertRaises(ContractValidationError):
            service.query("Block", ["aws-fsbp-1-0-0"])


class ExternalEvidenceTests(unittest.TestCase):
    def test_allowlist_and_identifier_prefix_are_enforced_without_network(self):
        policy, _ = fixtures()
        identifier = "https://docs.aws.amazon.com/securityhub/latest/userguide/s3-controls.html"
        adapter = EXTERNAL_TOOL.FixtureExternalEvidenceAdapter(
            {f"aws-official-docs|{identifier}": policy["external_evidence"]}
        )
        service = EXTERNAL_TOOL.ExternalEvidenceService(adapter, policy["external_allowlist"])
        self.assertIs(
            service.query("aws-official-docs", identifier).status,
            EvidenceResultStatus.FOUND,
        )
        with self.assertRaises(ContractValidationError):
            service.query("unapproved-vendor", identifier)
        with self.assertRaises(ContractValidationError):
            service.query("aws-official-docs", "https://example.com/not-allowed")

    def test_external_not_found_and_tool_error_are_distinct(self):
        policy, _ = fixtures()
        allowed = policy["external_allowlist"]
        identifier = "https://docs.aws.amazon.com/missing"
        missing = EXTERNAL_TOOL.ExternalEvidenceService(
            EXTERNAL_TOOL.FixtureExternalEvidenceAdapter({}), allowed
        ).query("aws-official-docs", identifier)

        class FailingAdapter:
            def fetch(self, source_id, identifier):
                raise RuntimeError("adapter failed")

        failed = EXTERNAL_TOOL.ExternalEvidenceService(FailingAdapter(), allowed).query(
            "aws-official-docs", identifier
        )
        self.assertIs(missing.status, EvidenceResultStatus.NOT_FOUND)
        self.assertIs(failed.status, EvidenceResultStatus.ERROR)


if __name__ == "__main__":
    unittest.main()
