export interface FeatureExplainerData {
  title: string
  category: 'FinOps' | 'Security' | 'Architecture' | 'Performance' | 'Reliability' | 'DevOps'
  description: string
  impact: string
  tip?: string
}

export const FEATURE_EXPLAINERS: Record<string, FeatureExplainerData> = {
  // Navigation / Views
  'nav-overview': {
    title: 'Executive Overview',
    category: 'FinOps',
    description: 'High-level real-time cockpit aggregating cloud spend, active node count, waste leakage, and security posture across accounts.',
    impact: 'Gives engineering leadership an immediate snapshot of health and potential ROI.',
    tip: 'Click to return to the executive metrics and quick alerts summary.',
  },
  'nav-inventory': {
    title: 'Compute Inventory',
    category: 'Architecture',
    description: 'Real-time catalogue of all EC2 instances, states (running/stopped), regions, and hourly running costs.',
    impact: 'Locate underutilized or abandoned instances running across any region.',
    tip: 'Filter by state or search by tag to pinpoint resources quickly.',
  },
  'nav-telemetry': {
    title: 'Telemetry & P95 Utilization',
    category: 'Performance',
    description: 'Continuous monitoring of CPU, RAM, Disk I/O, and Network throughput streamed from AWS CloudWatch and agents.',
    impact: 'Prevents over-provisioning by identifying workloads operating below 10% P95 CPU.',
    tip: 'Analyze the 30-day trendline before downsizing production nodes.',
  },
  'nav-security': {
    title: 'Security & Exposure Audit',
    category: 'Security',
    description: 'Automated vulnerability scanner checking for 0.0.0.0/0 public ingress on SSH/RDP/HTTP, unencrypted EBS, and exposed EIPs.',
    impact: 'Instantly closes attack surfaces and prevents catastrophic compliance breaches.',
    tip: 'Use the 1-Click Revoke action to eliminate open security group rules instantly.',
  },
  'nav-optimization': {
    title: 'Cost Optimization Engine',
    category: 'FinOps',
    description: 'Algorithmic recommendations including Spot instance migrations, right-sizing tiers, and unattached EBS volume pruning.',
    impact: 'Unlocks an average of 25% to 40% monthly infrastructure savings.',
    tip: 'Execute one-click remediation to downsize over-provisioned nodes automatically.',
  },
  'nav-scheduler': {
    title: 'Schedules & Pre-Warming',
    category: 'Reliability',
    description: 'Intelligent cron-driven start/stop schedules with automated warm-up routines before peak developer or customer hours.',
    impact: 'Eliminates 65% of staging and dev environment spend during off-peak hours.',
    tip: 'Set pre-warming 15 minutes before the daily 9 AM engineering standup.',
  },
  'nav-gitops-sla': {
    title: 'GitOps & SLA Watchdog',
    category: 'DevOps',
    description: 'Infrastructure-as-Code drift detector that compares live AWS state with Terraform/OpenTofu repos and enforces FinOps SLAs.',
    impact: 'Detects out-of-band manual changes that cause budget overruns and configuration drift.',
    tip: 'Integrates with GitHub Actions to alert engineers before PR merge.',
  },
  'nav-fleet': {
    title: 'Enterprise Fleet (100+ Nodes)',
    category: 'Architecture',
    description: 'Multi-account management console for enterprises running hundreds of nodes across AWS Organizations or multiple cloud profiles.',
    impact: 'Centralized visibility across distributed engineering teams and departmental budgets.',
    tip: 'Enroll secondary AWS accounts using IAM cross-account assume-role ARNs.',
  },
  'nav-cicd': {
    title: 'CI/CD & GitHub App Guardrails',
    category: 'DevOps',
    description: 'Automated pull request cost estimation comments and budget gatekeepers preventing expensive Terraform merges.',
    impact: 'Blocks inadvertent commits of expensive 64-core instances before they deploy.',
    tip: 'Configure cost increase thresholds (e.g. max +$100/mo) in repository settings.',
  },
  'nav-copilot': {
    title: 'AI FinOps Copilot',
    category: 'FinOps',
    description: 'Natural language AI assistant trained on your live cloud telemetry, billing records, and architectural best practices.',
    impact: 'Ask questions like "Which instances should I migrate to ARM Graviton?" for instant answers.',
    tip: 'Type conversational questions to generate custom cost breakdown reports.',
  },
  'nav-settings': {
    title: 'Settings & Notifications',
    category: 'DevOps',
    description: 'Configure Slack/Webhook alerting thresholds, currency conversions, API keys, and automated backup schedules.',
    impact: 'Keeps on-call teams alerted to abnormal cost spikes and budget burn rates.',
    tip: 'Connect a Slack incoming webhook to receive daily cost digest notifications.',
  },

  // Executive Metric Cards
  'metric-total-spend': {
    title: 'Total Monthly Spend',
    category: 'FinOps',
    description: 'Calculated 30-day projection of active compute and storage infrastructure costs based on current provisioning rates.',
    impact: 'Enables accurate budget forecasting and prevents surprise cloud bills.',
    tip: 'Switch currencies between USD and INR in the top context bar at any time.',
  },
  'metric-active-nodes': {
    title: 'Active Compute Nodes',
    category: 'Architecture',
    description: 'Total number of EC2 instances currently in the running state across all connected regions and VPCs.',
    impact: 'Tracks real-time capacity and helps spot instances left running inadvertently over weekends.',
    tip: 'Review stopped nodes to delete orphaned attached root EBS storage volumes.',
  },
  'metric-wasted-spend': {
    title: 'Monthly Wasted Spend',
    category: 'FinOps',
    description: 'Quantified capital leakage from idle instances (<5% CPU), unattached Elastic IPs, and orphaned EBS snapshot volumes.',
    impact: 'Direct recoverable cash that can be saved immediately without impacting production traffic.',
    tip: 'Review the Cost Optimization tab to reclaim these funds in just a few clicks.',
  },
  'metric-security-risks': {
    title: 'Critical Security Risks',
    category: 'Security',
    description: 'High-severity exposure findings including world-readable ports (0.0.0.0/0 on 22/3389) and unencrypted sensitive data volumes.',
    impact: 'Eliminates active penetration vectors that could lead to data exfiltration or ransomware.',
    tip: 'Click to open the Security & Exposure view and execute 1-click firewall revokes.',
  },

  // Global Controls & Actions
  'control-provider-filter': {
    title: 'Cloud Provider Filter',
    category: 'Architecture',
    description: 'Filter telemetry, inventory, and cost analytics across AWS, GCP, Azure, or view an aggregated multi-cloud view.',
    impact: 'Isolates provider-specific cost structures and comparisons.',
    tip: 'Choose "All Providers" for unified multi-cloud executive reporting.',
  },
  'control-currency-switcher': {
    title: 'Currency Normalization',
    category: 'FinOps',
    description: 'Toggles between US Dollar ($) and Indian Rupee (₹ Lakhs / Crores) using real-time forex normalization rates.',
    impact: 'Provides localized financial reporting for domestic finance and tax compliance teams.',
    tip: 'All table values, tooltips, and savings metrics recalculate instantaneously.',
  },
  'control-account-switcher': {
    title: 'Active Account Context',
    category: 'Architecture',
    description: 'Switch between registered AWS / cloud accounts, staging, production, and learner lab profiles without logging out.',
    impact: 'Seamless multi-tenant fleet administration with zero downtime.',
    tip: 'Select "Connect Cloud Account" to add additional accounts via IAM Role ARN.',
  },
  'control-pov-audit': {
    title: 'Executive PoV Audit',
    category: 'FinOps',
    description: 'Generates a formal, printable FinOps Proof of Value audit report detailing spend velocity, waste, and ROI trajectory.',
    impact: 'Ready-to-present executive deck for CTOs, CFOs, and board review.',
    tip: 'Download as HTML or JSON audit report for offline review.',
  },
  'control-connect-account': {
    title: 'Connect Cloud Account',
    category: 'Architecture',
    description: 'Securely link AWS accounts using read-only IAM Role Delegation, temporary session tokens, or local AWS CLI profiles.',
    impact: 'Provides non-invasive, agentless discovery of cloud resources in seconds.',
    tip: 'CloudPulse uses read-only SecurityAudit and CostOptimization policies.',
  },
  'action-savings-view': {
    title: 'Savings Opportunities',
    category: 'FinOps',
    description: 'Deep dive into algorithmic recommendations categorized by high, medium, and low effort savings.',
    impact: 'Prioritizes the highest financial impact actions for engineers first.',
    tip: 'Focus on High Severity recommendations to capture 80% of waste with 20% of effort.',
  },
}
