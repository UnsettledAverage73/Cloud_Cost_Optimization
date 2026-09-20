# CloudPulse Enterprise Private VPC Helm Chart

Deploy CloudPulse inside your private Amazon EKS / Kubernetes VPC clusters with **Zero-Storage Ephemeral RAM mode**, native AWS IAM Roles for Service Accounts (IRSA), and non-root least-privilege security contexts.

---

## 🛡️ Enterprise Security & InfoSec Features

- **Zero-Storage Ephemeral RAM Mode (`ephemeralMode: true`)**: All DuckDB lakehouse analytics and cache indexes are held strictly in in-memory RAM buffers with an ephemeral `emptyDir` mount. No persistent volumes (EBS/EFS) storing sensitive cloud inventory or cost data.
- **IAM Roles for Service Accounts (IRSA)**: No long-lived AWS Access Keys or Secrets. Uses OIDC federation token exchange with AWS Security Token Service (STS).
- **Non-Root Pod Security Context**: Runs as unprivileged UID `10001` with `readOnlyRootFilesystem: true` and all Linux capabilities dropped (`drop: ["ALL"]`).
- **Network Isolation**: Strict `NetworkPolicy` permitting ingress only to port 8000 and egress restricted to DNS (`53`) and AWS HTTPS APIs (`443`).

---

## 🚀 Quickstart Installation

### 1. Configure AWS IRSA (Terraform)

```hcl
module "cloudpulse_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.30"

  role_name = "CloudPulseFinOpsReadOnlyRole"

  role_policy_arns = {
    CostExplorer = "arn:aws:iam::aws:policy/CostOptimizationHubReadOnlyAccess"
    EC2ReadOnly  = "arn:aws:iam::aws:policy/AmazonEC2ReadOnlyAccess"
  }

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["finops:cloudpulse-sa"]
    }
  }
}
```

### 2. Install the Helm Chart

```bash
# Add namespace
kubectl create namespace finops

# Install with your IRSA role ARN
helm upgrade --install cloudpulse ./deploy/helm/cloudpulse \
  --namespace finops \
  --set aws.irsaRoleArn="arn:aws:iam::123456789012:role/CloudPulseFinOpsReadOnlyRole" \
  --set currency="USD" \
  --set ephemeralMode=true
```

### 3. Verify Deployment

```bash
kubectl get pods -n finops -l app.kubernetes.io/name=cloudpulse
kubectl logs -n finops -l app.kubernetes.io/name=cloudpulse --tail=50
```

---

## ⚙️ Configuration Reference

| Parameter | Description | Default |
| :--- | :--- | :--- |
| `replicaCount` | Number of pods for high availability | `2` |
| `ephemeralMode` | Enables Zero-Storage RAM mode (DuckDB in memory) | `true` |
| `aws.irsaRoleArn` | AWS IAM Role ARN for EKS ServiceAccount OIDC | `""` |
| `aws.readOnlyMode` | Enforces read-only FinOps analysis without mutations | `true` |
| `currency` | Default reporting currency (`USD` or `INR`) | `"USD"` |
| `exchangeRate` | USD to INR conversion rate | `84.00` |
| `securityContext.readOnlyRootFilesystem` | Mounts root filesystem as read-only | `true` |
| `securityContext.capabilities.drop` | Drops all Linux kernel capabilities | `["ALL"]` |
| `autoscaling.enabled` | Enables HorizontalPodAutoscaler | `true` |
| `ingress.enabled` | Exposes service via AWS ALB Ingress Controller | `false` |
| `networkPolicy.enabled` | Restricts ingress/egress network flows | `true` |
| `env.OPENCOST_API_URL` | OpenCost endpoint for container telemetry | `http://opencost.opencost:9003` |

---

## 📄 License
Copyright © 2026 CloudPulse FinOps Platform. All rights reserved.
