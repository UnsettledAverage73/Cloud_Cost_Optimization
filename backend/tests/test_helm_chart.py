"""
Unit & Security Tests for CloudPulse Enterprise Private VPC Helm Chart (Milestone 3 - Priority 1).
Verifies Helm Chart.yaml metadata, production values.yaml defaults (Zero-Storage RAM mode, IRSA, non-root),
template file completeness, and Kubernetes manifest compliance.
"""

from pathlib import Path
import yaml
import pytest

CHART_DIR = Path(__file__).resolve().parent.parent.parent / "deploy" / "helm" / "cloudpulse"


def test_helm_chart_metadata():
    """Verifies Chart.yaml metadata, versions, and required keys."""
    chart_file = CHART_DIR / "Chart.yaml"
    assert chart_file.exists(), f"Chart.yaml missing at {chart_file}"

    with open(chart_file, "r") as f:
        meta = yaml.safe_load(f)

    assert meta["apiVersion"] == "v2"
    assert meta["name"] == "cloudpulse"
    assert "version" in meta
    assert meta["appVersion"] == "2.0.0"
    assert meta["type"] == "application"
    assert "finops" in meta.get("keywords", [])


def test_helm_values_enterprise_security_defaults():
    """Verifies values.yaml satisfies InfoSec, SOC 2, and zero-storage requirements."""
    values_file = CHART_DIR / "values.yaml"
    assert values_file.exists(), f"values.yaml missing at {values_file}"

    with open(values_file, "r") as f:
        val = yaml.safe_load(f)

    # 1. Zero-Storage Ephemeral RAM Mode
    assert val.get("ephemeralMode") is True, "ephemeralMode must be enabled by default for InfoSec compliance"

    # 2. High Availability Replicas
    assert val.get("replicaCount", 0) >= 2

    # 3. Non-Root Least Privilege Security Context
    pod_sec = val.get("podSecurityContext", {})
    assert pod_sec.get("runAsNonRoot") is True
    assert pod_sec.get("runAsUser") == 10001
    assert pod_sec.get("runAsGroup") == 10001

    sec = val.get("securityContext", {})
    assert sec.get("readOnlyRootFilesystem") is True
    assert sec.get("allowPrivilegeEscalation") is False
    assert sec.get("capabilities", {}).get("drop") == ["ALL"]

    # 4. Autoscaling and Networking Isolation
    assert val.get("autoscaling", {}).get("enabled") is True
    assert val.get("networkPolicy", {}).get("enabled") is True
    assert val.get("networkPolicy", {}).get("allowDns") is True
    assert val.get("networkPolicy", {}).get("allowEgressAws") is True


def test_helm_templates_file_structure():
    """Verifies that all required production Kubernetes manifest templates exist."""
    templates_dir = CHART_DIR / "templates"
    assert templates_dir.exists()

    required_templates = [
        "_helpers.tpl",
        "deployment.yaml",
        "service.yaml",
        "serviceaccount.yaml",
        "configmap.yaml",
        "ingress.yaml",
        "hpa.yaml",
        "networkpolicy.yaml"
    ]

    for tpl in required_templates:
        p = templates_dir / tpl
        assert p.exists(), f"Required Helm template '{tpl}' is missing in {templates_dir}"


def test_helm_readme_documentation():
    """Verifies comprehensive README documentation with IRSA Terraform snippets."""
    readme_file = CHART_DIR / "README.md"
    assert readme_file.exists()

    content = readme_file.read_text()
    assert "Zero-Storage Ephemeral RAM Mode" in content
    assert "IAM Roles for Service Accounts (IRSA)" in content
    assert "helm upgrade --install" in content
    assert "terraform-aws-modules/iam/aws" in content


def test_helm_template_syntax_sanity():
    """Verifies that template files contain expected Kubernetes kinds and annotations."""
    templates_dir = CHART_DIR / "templates"

    sa_content = (templates_dir / "serviceaccount.yaml").read_text()
    assert "kind: ServiceAccount" in sa_content
    assert "eks.amazonaws.com/role-arn" in sa_content

    deploy_content = (templates_dir / "deployment.yaml").read_text()
    assert "kind: Deployment" in deploy_content
    assert "livenessProbe" in deploy_content
    assert "readinessProbe" in deploy_content
    assert "emptyDir" in deploy_content
    assert "tmp-dir" in deploy_content

    np_content = (templates_dir / "networkpolicy.yaml").read_text()
    assert "kind: NetworkPolicy" in np_content
    assert "policyTypes" in np_content
    assert "port: 8000" in np_content
    assert "port: 443" in np_content
    assert "port: 53" in np_content

    hpa_content = (templates_dir / "hpa.yaml").read_text()
    assert "kind: HorizontalPodAutoscaler" in hpa_content
    assert "targetCPUUtilizationPercentage" in hpa_content


def test_cli_onboard_helm_mode(capsys):
    """Verifies CLI cmd_onboard --helm outputs Private VPC deployment command."""
    import argparse
    from cli_main import cmd_onboard

    args = argparse.Namespace(
        helm=True,
        irsa_role="arn:aws:iam::123456789012:role/CloudPulseRole",
        url="http://localhost:8000"
    )
    cmd_onboard(args)
    captured = capsys.readouterr().out
    assert "CLOUDPULSE PRIVATE VPC SINGLE-TENANT HELM ONBOARDING" in captured
    assert "Zero-Storage Ephemeral RAM mode" in captured
    assert "helm upgrade --install cloudpulse" in captured
    assert "arn:aws:iam::123456789012:role/CloudPulseRole" in captured

