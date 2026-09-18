import urllib.parse
import json
import uuid

CLOUDPULSE_SAAS_ACCOUNT_ID = "012345678901"  # Production SaaS AWS Account ID

def generate_cloudformation_yaml(external_id: str, allow_remediation: bool = False) -> str:
    """
    Generates an enterprise CloudFormation YAML template that grants CloudPulse
    least-privilege read-only FinOps access (and optional safe remediation access)
    with strict ExternalId trust policy.
    """
    remediation_policy_block = """
        - PolicyName: CloudPulseSafeRemediation
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Sid: SafeStorageRemediation
                Effect: Allow
                Action:
                  - ec2:CreateSnapshot
                  - ec2:DeleteVolume
                  - ec2:ModifyVolume
                  - ec2:ReleaseAddress
                Resource: '*'
                Condition:
                  StringNotEquals:
                    aws:ResourceTag/Production: 'true'
    """ if allow_remediation else ""

    yaml_template = f"""AWSTemplateFormatVersion: '2010-09-09'
Description: 'CloudPulse Enterprise FinOps IAM Integration Stack'

Parameters:
  CloudPulseAccountId:
    Type: String
    Default: '{CLOUDPULSE_SAAS_ACCOUNT_ID}'
    Description: 'The AWS Account ID of the CloudPulse SaaS Platform'

  CloudPulseExternalId:
    Type: String
    Default: '{external_id}'
    Description: 'Unique ExternalId for secure cross-account STS authentication'

Resources:
  CloudPulseFinOpsRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: CloudPulseFinOpsRole
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              AWS: !Sub 'arn:aws:iam::${{CloudPulseAccountId}}:root'
            Action: 'sts:AssumeRole'
            Condition:
              StringEquals:
                'sts:ExternalId': !Ref CloudPulseExternalId
      Policies:
        - PolicyName: CloudPulseFinOpsReadOnly
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Sid: BillingAndCostExplorer
                Effect: Allow
                Action:
                  - ce:GetCostAndUsage
                  - ce:GetDimensionValues
                  - ce:GetCostForecast
                  - ce:GetReservationUtilization
                  - ce:GetSavingsPlansUtilization
                  - ce:GetRightsizingRecommendation
                Resource: '*'
              - Sid: ResourceMetadataAndMetrics
                Effect: Allow
                Action:
                  - ec2:Describe*
                  - rds:Describe*
                  - s3:List*
                  - s3:GetBucket*
                  - cloudwatch:GetMetricData
                  - cloudwatch:GetMetricStatistics
                  - cloudwatch:ListMetrics
                  - logs:DescribeLogGroups
                  - pricing:GetProducts
                  - pricing:DescribeServices
                Resource: '*'
{remediation_policy_block}

Outputs:
  RoleArn:
    Description: 'ARN of the CloudPulse FinOps Role to input into CloudPulse'
    Value: !GetAtt CloudPulseFinOpsRole.Arn
"""
    return yaml_template

def generate_quick_create_url(external_id: str, stack_name: str = "CloudPulse-FinOps-Integration", region: str = "us-east-1") -> str:
    """
    Generates a 1-click AWS Management Console Quick-Create Stack URL.
    DevOps engineers simply click the link and click 'Create Stack'.
    """
    base_url = f"https://console.aws.amazon.com/cloudformation/home?region={region}#/stacks/create/review"
    params = {
        "stackName": stack_name,
        "param_CloudPulseAccountId": CLOUDPULSE_SAAS_ACCOUNT_ID,
        "param_CloudPulseExternalId": external_id
    }
    return f"{base_url}?{urllib.parse.urlencode(params)}"

def get_onboarding_package(org_id: str, allow_remediation: bool = False) -> dict:
    """Generates a complete onboarding payload for a customer organization."""
    ext_id = f"cp-{uuid.uuid4().hex[:16]}"
    yaml_content = generate_cloudformation_yaml(external_id=ext_id, allow_remediation=allow_remediation)
    quick_url = generate_quick_create_url(external_id=ext_id)
    return {
        "external_id": ext_id,
        "saas_account_id": CLOUDPULSE_SAAS_ACCOUNT_ID,
        "quick_create_url": quick_url,
        "template_yaml": yaml_content,
        "required_permissions": [
            "ce:GetCostAndUsage (Cost Explorer spend data)",
            "ec2:Describe* (Instances, EBS volumes, EIPs, NAT Gateways)",
            "rds:Describe* (Databases & clusters)",
            "cloudwatch:GetMetricData (CPU & Network utilization)",
            "pricing:GetProducts (Live AWS pricing catalog)"
        ]
    }
