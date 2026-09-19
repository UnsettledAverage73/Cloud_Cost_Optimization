import pytest
from unittest.mock import patch, MagicMock
from testing.runner import CloudPulseTestRunner, TestResult, TestSuiteReport
from cli_main import load_config, save_config, get_backend_url, main
import json

def test_test_runner_initialization():
    runner = CloudPulseTestRunner(base_url="https://test-backend.internal", timeout=12.0)
    assert runner.base_url == "https://test-backend.internal"
    assert runner.timeout == 12.0

def test_test_runner_report_structure():
    results = [
        TestResult(
            category="Infrastructure",
            name="DB Ping",
            method="GET",
            endpoint="/api/v2/database/status",
            status_code=200,
            expected_code=200,
            elapsed_ms=120.0,
            passed=True,
            summary="200 OK"
        ),
        TestResult(
            category="Billing",
            name="FOCUS Spend",
            method="GET",
            endpoint="/api/v2/focus/spend",
            status_code=200,
            expected_code=200,
            elapsed_ms=180.0,
            passed=True,
            summary="200 OK"
        )
    ]
    report = TestSuiteReport(
        base_url="https://test-backend.internal",
        timestamp="2026-09-18 15:30:00 UTC",
        total_tests=2,
        passed_tests=2,
        failed_tests=0,
        success_rate_percent=100.0,
        total_duration_ms=300.0,
        avg_latency_ms=150.0,
        p95_latency_ms=180.0,
        min_latency_ms=120.0,
        max_latency_ms=180.0,
        results=results
    )
    report_dict = report.to_dict()
    assert report_dict["passed_tests"] == 2
    assert report_dict["failed_tests"] == 0
    assert report_dict["success_rate_percent"] == 100.0
    assert len(report_dict["results"]) == 2

def test_cli_config_management(tmp_path):
    with patch("cli_main.CONFIG_FILE", tmp_path / "config.json"), \
         patch("cli_main.CONFIG_DIR", tmp_path):
        save_config({"backend_url": "https://custom-cloudpulse.com"})
        conf = load_config()
        assert conf.get("backend_url") == "https://custom-cloudpulse.com"
        url = get_backend_url()
        assert url == "https://custom-cloudpulse.com"

def test_cli_override_url():
    url = get_backend_url("https://override-url.com/")
    assert url == "https://override-url.com"

def test_test_runner_html_generation(tmp_path):
    runner = CloudPulseTestRunner(base_url="https://test.internal")
    results = [
        TestResult(
            category="AI",
            name="Copilot Chat",
            method="POST",
            endpoint="/api/v2/copilot/chat",
            status_code=200,
            expected_code=200,
            elapsed_ms=45.0,
            passed=True,
            summary="200 OK",
            response_sample="Hello from copilot"
        )
    ]
    report = TestSuiteReport(
        base_url="https://test.internal",
        timestamp="2026-09-18 15:30:00 UTC",
        total_tests=1,
        passed_tests=1,
        failed_tests=0,
        success_rate_percent=100.0,
        total_duration_ms=45.0,
        avg_latency_ms=45.0,
        p95_latency_ms=45.0,
        min_latency_ms=45.0,
        max_latency_ms=45.0,
        results=results
    )
    html_file = tmp_path / "report.html"
    runner.generate_html_report(report, str(html_file))
    assert html_file.exists()
    content = html_file.read_text()
    assert "CloudPulse Production Health & Test Suite" in content
    assert "Copilot Chat" in content

def test_cmd_inspect_and_cost_commands(capsys):
    from cli_main import cmd_inspect, cmd_cost
    import argparse

    mock_inventory = {
        "metadata": {"region": "us-east-1", "timestamp": "2026-09-18T20:00:00Z"},
        "compute": {
            "nodes": [
                {
                    "instance_id": "i-test12345",
                    "name": "api-server",
                    "instance_type": "t3.micro",
                    "state": "running",
                    "platform": "linux",
                    "architecture": "x86_64",
                    "cost": 7.60,
                    "public_ip": "1.2.3.4",
                    "metrics": {"cpu_utilization_avg": 0.25, "cpu_utilization_max": 2.5}
                }
            ]
        },
        "ec2_other_resources": {
            "ebs_volumes": [
                {
                    "volume_id": "vol-test123",
                    "size_gb": 8,
                    "volume_type": "gp3",
                    "cost": 0.64,
                    "attached_instance_id": "i-test12345",
                    "status": "in-use",
                    "is_orphaned": False
                }
            ],
            "elastic_ips": [],
            "amis": [],
            "network_interfaces": [],
            "ebs_snapshots": [],
            "cloudwatch_log_groups": [],
            "s3_buckets": [],
            "security_groups": []
        },
        "vpc_resources": {"nat_gateways": [], "vpc_endpoints": []}
    }

    with patch("cli_main.fetch_inventory_data", return_value=mock_inventory):
        # 1. Test cost command json
        args_cost_json = argparse.Namespace(url=None, instance_id="i-test12345", json_only=True)
        cmd_cost(args_cost_json)
        captured = capsys.readouterr()
        cost_json = json.loads(captured.out)
        assert cost_json["instance_id"] == "i-test12345"
        assert cost_json["parameters"]["total_cost_usd"] == 11.84

        # 2. Test inspect command json
        args_inspect_json = argparse.Namespace(url=None, resource_id="i-test12345", json_only=True)
        cmd_inspect(args_inspect_json)
        captured = capsys.readouterr()
        inspect_json = json.loads(captured.out)
        assert inspect_json["instance_id"] == "i-test12345"
        assert inspect_json["cost_parameters"]["total_monthly_cost_usd"] == 11.84
        assert inspect_json["finops_assessment"]["is_idle"] is True


def test_cli_exporters_unit():
    from cli_exporters import FinOpsReportExporter

    # 1. Cost Rollup Exporters
    summary = {
        "total_instances": 1,
        "running_instances": 1,
        "total_monthly_spend_usd": 11.84,
        "compute_spend_usd": 7.60,
        "storage_spend_usd": 0.64,
        "public_ipv4_spend_usd": 3.60
    }
    instances = [
        {
            "instance_id": "i-test12345",
            "name": "api-server",
            "type": "t3.micro",
            "state": "running",
            "cpu_utilization_avg": 0.25,
            "compute_cost": 7.60,
            "storage_cost": 0.64,
            "public_ip_cost": 3.60,
            "total_cost": 11.84
        }
    ]
    csv_out = FinOpsReportExporter.cost_rollup_to_csv(summary, instances)
    assert "i-test12345" in csv_out
    assert "11.84" in csv_out
    assert "Total Monthly Spend" in csv_out

    md_out = FinOpsReportExporter.cost_rollup_to_markdown(summary, instances)
    assert "CloudPulse FinOps Executive Spend Report" in md_out
    assert "| `i-test12345` |" in md_out
    assert "$11.84/mo" in md_out

    # 2. Single Instance Cost Exporters
    cost_data = {
        "instance_id": "i-test12345",
        "instance_type": "t3.micro",
        "state": "running",
        "formula": "Total = (Hourly Compute × 730h) + Storage + IPv4",
        "parameters": {
            "hourly_rate_usd": 0.0104,
            "operating_hours": 730,
            "compute_cost_usd": 7.60,
            "storage_cost_usd": 0.64,
            "public_ipv4_cost_usd": 3.60,
            "total_cost_usd": 11.84
        },
        "line_items": [
            {"item": "EC2 Compute", "type": "t3.micro", "cost": 7.60, "share_pct": 64.2},
            {"item": "EBS Storage", "type": "1 volume", "cost": 0.64, "share_pct": 5.4}
        ],
        "savings_opportunities": [
            {"action": "Graviton Upgrade", "target_type": "t4g.micro", "monthly_savings": 1.52}
        ]
    }
    inst_csv = FinOpsReportExporter.single_instance_cost_to_csv(cost_data)
    assert "i-test12345" in inst_csv
    assert "Graviton Upgrade" in inst_csv

    inst_md = FinOpsReportExporter.single_instance_cost_to_markdown(cost_data)
    assert "FinOps Cost Decomposition:" in inst_md
    assert "Graviton Upgrade" in inst_md

    # 3. EBS Volumes Exporters
    ebs_vols = [
        {
            "volume_id": "vol-12345",
            "size_gb": 8,
            "volume_type": "gp3",
            "cost": 0.64,
            "attached_instance_id": "i-test12345",
            "status": "in-use",
            "is_orphaned": False
        }
    ]
    ebs_csv = FinOpsReportExporter.ebs_volumes_to_csv(ebs_vols)
    assert "vol-12345" in ebs_csv
    assert "0.64" in ebs_csv

    ebs_md = FinOpsReportExporter.ebs_volumes_to_markdown(ebs_vols)
    assert "CloudPulse EBS Storage & Attachment Audit" in ebs_md
    assert "vol-12345" in ebs_md

    # 4. EC2 Compute Exporters
    nodes = [
        {
            "instance_id": "i-test12345",
            "name": "worker",
            "instance_type": "t3.micro",
            "state": "running",
            "availability_zone": "us-east-1a",
            "public_ip": "1.2.3.4",
            "cost": 7.60,
            "metrics": {"cpu_utilization_avg": 0.5}
        }
    ]
    ec2_csv = FinOpsReportExporter.ec2_compute_to_csv(nodes)
    assert "i-test12345" in ec2_csv
    assert "t3.micro" in ec2_csv

    ec2_md = FinOpsReportExporter.ec2_compute_to_markdown(nodes)
    assert "CloudPulse EC2 Compute Inventory & Telemetry" in ec2_md
    assert "i-test12345" in ec2_md

    # 5. Network Exporters
    eips = [{"public_ip": "3.4.5.6", "allocation_id": "eipalloc-1", "association_id": None, "instance_id": None}]
    enis = [{"interface_id": "eni-1", "status": "in-use", "private_ip": "10.0.1.5", "public_ip": "3.4.5.6", "attached_instance_id": None}]
    net_csv = FinOpsReportExporter.network_to_csv(eips, enis, nodes)
    assert "eipalloc-1" in net_csv
    assert "3.4.5.6" in net_csv

    net_md = FinOpsReportExporter.network_to_markdown(eips, enis, nodes)
    assert "CloudPulse Networking & IPv4 Spend Audit" in net_md
    assert "eipalloc-1" in net_md

    # 6. Security Groups Exporters
    sgs = [
        {
            "group_id": "sg-12345",
            "group_name": "open-ssh",
            "inbound_rules": [
                {"protocol": "tcp", "from_port": 22, "to_port": 22, "source_cidr": "0.0.0.0/0", "is_open_to_world": True}
            ]
        }
    ]
    sg_csv = FinOpsReportExporter.security_groups_to_csv(sgs)
    assert "sg-12345" in sg_csv
    assert "Security Group ID" in sg_csv

    sg_md = FinOpsReportExporter.security_groups_to_markdown(sgs)
    assert "CloudPulse Security Groups & Ingress Exposure Audit" in sg_md
    assert "sg-12345" in sg_md

    # 7. CloudWatch Logs Exporters
    logs = [
        {
            "log_group_name": "/aws/lambda/test",
            "retention_in_days": None,
            "stored_bytes": 104857600,
            "stored_gb": 0.1,
            "is_never_expire": True,
            "cost": 0.03
        }
    ]
    logs_csv = FinOpsReportExporter.cloudwatch_logs_to_csv(logs)
    assert "/aws/lambda/test" in logs_csv
    assert "YES" in logs_csv

    logs_md = FinOpsReportExporter.cloudwatch_logs_to_markdown(logs)
    assert "CloudPulse CloudWatch Log Groups & Retention Audit" in logs_md
    assert "/aws/lambda/test" in logs_md


def test_cli_cost_category_filtering_and_file_export(capsys, tmp_path):
    from cli_main import cmd_cost
    import argparse

    mock_inventory = {
        "metadata": {"region": "us-east-1", "timestamp": "2026-09-18T20:00:00Z"},
        "compute": {
            "nodes": [
                {
                    "instance_id": "i-test12345",
                    "name": "api-server",
                    "instance_type": "t3.micro",
                    "state": "running",
                    "platform": "linux",
                    "architecture": "x86_64",
                    "cost": 7.60,
                    "public_ip": "1.2.3.4",
                    "metrics": {"cpu_utilization_avg": 0.25, "cpu_utilization_max": 2.5}
                }
            ]
        },
        "ec2_other_resources": {
            "ebs_volumes": [
                {
                    "volume_id": "vol-test123",
                    "size_gb": 8,
                    "volume_type": "gp3",
                    "cost": 0.64,
                    "attached_instance_id": "i-test12345",
                    "status": "in-use",
                    "is_orphaned": False
                }
            ],
            "elastic_ips": [],
            "amis": [],
            "network_interfaces": [],
            "ebs_snapshots": [],
            "cloudwatch_log_groups": [],
            "s3_buckets": [],
            "security_groups": []
        },
        "vpc_resources": {"nat_gateways": [], "vpc_endpoints": []}
    }

    with patch("cli_main.fetch_inventory_data", return_value=mock_inventory):
        # 1. Cost EC2 category in CSV format
        args = argparse.Namespace(url=None, instance_id="ec2", format="csv", output=None, json_only=False)
        cmd_cost(args)
        out = capsys.readouterr().out
        assert "Instance ID,Name,Instance Type" in out
        assert "i-test12345" in out

        # 2. Cost EBS category in Markdown format
        args = argparse.Namespace(url=None, instance_id="ebs", format="markdown", output=None, json_only=False)
        cmd_cost(args)
        out = capsys.readouterr().out
        assert "CloudPulse EBS Storage & Attachment Audit" in out
        assert "vol-test123" in out

        # 3. Cost Network category in Markdown format
        args = argparse.Namespace(url=None, instance_id="network", format="markdown", output=None, json_only=False)
        cmd_cost(args)
        out = capsys.readouterr().out
        assert "CloudPulse Networking & IPv4 Spend Audit" in out

        # 4. Cost account rollup with file export
        cost_out_file = tmp_path / "cost_rollup.md"
        args = argparse.Namespace(url=None, instance_id=None, format="markdown", output=str(cost_out_file), json_only=False)
        cmd_cost(args)
        assert cost_out_file.exists()
        file_text = cost_out_file.read_text()
        assert "CloudPulse FinOps Executive Spend Report" in file_text
        assert "\033[" not in file_text  # ANSI codes stripped!


def test_cli_inspect_categories_and_file_export(capsys, tmp_path):
    from cli_main import cmd_inspect
    import argparse

    mock_inventory = {
        "metadata": {"region": "us-east-1", "timestamp": "2026-09-18T20:00:00Z"},
        "compute": {
            "nodes": [
                {
                    "instance_id": "i-test12345",
                    "name": "api-server",
                    "instance_type": "t3.micro",
                    "state": "running",
                    "platform": "linux",
                    "architecture": "x86_64",
                    "cost": 7.60,
                    "public_ip": "1.2.3.4",
                    "metrics": {"cpu_utilization_avg": 0.25, "cpu_utilization_max": 2.5}
                }
            ]
        },
        "ec2_other_resources": {
            "ebs_volumes": [
                {
                    "volume_id": "vol-test123",
                    "size_gb": 8,
                    "volume_type": "gp3",
                    "cost": 0.64,
                    "attached_instance_id": "i-test12345",
                    "status": "in-use",
                    "is_orphaned": False
                }
            ],
            "elastic_ips": [],
            "amis": [],
            "network_interfaces": [],
            "ebs_snapshots": [],
            "cloudwatch_log_groups": [
                {
                    "log_group_name": "/aws/ec2/system",
                    "retention_in_days": 7,
                    "stored_bytes": 50000000,
                    "stored_gb": 0.05,
                    "is_never_expire": False,
                    "cost": 0.015
                }
            ],
            "s3_buckets": [],
            "security_groups": [
                {
                    "group_id": "sg-999",
                    "group_name": "web-sg",
                    "inbound_rules": [
                        {"protocol": "tcp", "from_port": 80, "to_port": 80, "source_cidr": "0.0.0.0/0", "is_open_to_world": True}
                    ]
                }
            ]
        },
        "vpc_resources": {"nat_gateways": [], "vpc_endpoints": []}
    }

    with patch("cli_main.fetch_inventory_data", return_value=mock_inventory):
        # 1. Inspect Security in CSV format
        args = argparse.Namespace(url=None, resource_id="security", format="csv", output=None, json_only=False)
        cmd_inspect(args)
        out = capsys.readouterr().out
        assert "Security Group ID,Group Name,VPC ID" in out
        assert "sg-999" in out

        # 2. Inspect Logs in Markdown format
        args = argparse.Namespace(url=None, resource_id="logs", format="markdown", output=None, json_only=False)
        cmd_inspect(args)
        out = capsys.readouterr().out
        assert "/aws/ec2/system" in out
        assert "CloudPulse CloudWatch Log Groups & Retention Audit" in out

        # 3. Inspect Full Inventory written to markdown file
        inv_file = tmp_path / "full_inventory.md"
        args = argparse.Namespace(url=None, resource_id=None, format="markdown", output=str(inv_file), json_only=False)
        cmd_inspect(args)
        assert inv_file.exists()
        inv_text = inv_file.read_text()
        assert "CloudPulse Comprehensive AWS Cloud Inventory Report" in inv_text
        assert "i-test12345" in inv_text
        assert "\033[" not in inv_text


def test_cli_notify_whatsapp_and_slack(capsys):
    from cli_main import cmd_notify
    import argparse

    # 1. WhatsApp Success
    with patch("services.notifier.finops_notifier.send_whatsapp_alert", return_value=True) as mock_wa:
        args = argparse.Namespace(channel="whatsapp", to="+919876543210", title="Test Alert", message="Spike detected")
        cmd_notify(args)
        out = capsys.readouterr().out
        assert "CLOUDPULSE MULTI-CHANNEL NOTIFICATION DISPATCHER" in out
        assert "WhatsApp message dispatched successfully" in out
        mock_wa.assert_called_once_with("Test Alert", "Spike detected", to_number="+919876543210")

    # 2. WhatsApp Failure
    with patch("services.notifier.finops_notifier.send_whatsapp_alert", return_value=False):
        args = argparse.Namespace(channel="whatsapp", to="+919876543210", title="Test Alert", message="Spike detected")
        cmd_notify(args)
        out = capsys.readouterr().out
        assert "Failed to dispatch WhatsApp message" in out

    # 3. Slack Dispatch
    with patch("cli_main.resolve_cli_inventory", return_value={"summary": {"estimated_monthly_spend": 100.0}}), \
         patch("services.notifier.finops_notifier.send_slack_alert", return_value=True) as mock_slack:
        args = argparse.Namespace(channel="slack", to=None, title="Slack Alert", message="Test Slack")
        cmd_notify(args)
        out = capsys.readouterr().out
        assert "Slack webhook alert dispatched successfully" in out
        mock_slack.assert_called_once()


def test_finops_notifier_twilio_auth():
    from services.notifier import FinOpsNotifier
    from unittest.mock import MagicMock

    # Case 1: API Key without Account SID -> diagnostic warning and None client
    notifier = FinOpsNotifier()
    notifier.twilio_api_key = "SK123"
    notifier.twilio_api_secret = "secret123"
    notifier.twilio_account_sid = None
    assert notifier._get_twilio_client() is None

    # Case 2: API Key with Account SID -> Client(api_key, api_secret, account_sid=account_sid)
    notifier.twilio_account_sid = "AC123"
    with patch("twilio.rest.Client") as mock_client:
        client_instance = notifier._get_twilio_client()
        mock_client.assert_called_once_with("SK123", "secret123", account_sid="AC123")

    # Case 3: send_whatsapp_alert successfully creates message
    mock_tw_client = MagicMock()
    mock_msg = MagicMock()
    mock_msg.sid = "SM999"
    mock_tw_client.messages.create.return_value = mock_msg

    with patch.object(notifier, "_get_twilio_client", return_value=mock_tw_client):
        success = notifier.send_whatsapp_alert(
            title="High Spend Detected",
            message="EC2 runaway cost",
            to_number="919876543210"
        )
        assert success is True
        mock_tw_client.messages.create.assert_called_once()
        call_kwargs = mock_tw_client.messages.create.call_args[1]
        assert call_kwargs["to"] == "whatsapp:+919876543210"
        assert "High Spend Detected" in call_kwargs["body"]



