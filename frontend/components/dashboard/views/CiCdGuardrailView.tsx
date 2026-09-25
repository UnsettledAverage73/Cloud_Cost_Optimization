'use client'

import React, { useState, useEffect } from 'react'
import {
  AlertTriangle,
  Check,
  Copy,
  GitPullRequest,
  Loader2,
  Play,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { SectionTitle } from '@/components/dashboard'
import { formatCurrency, formatInteger } from '@/lib/formatters'
import type { Currency } from '@/types/dashboard'

export function CiCdGuardrailView({ currency = 'USD', apiUrl }: { currency: 'USD' | 'INR'; apiUrl: (path: string) => string }) {
  const [appStatus, setAppStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [filePath, setFilePath] = useState('terraform/compute.tf');
  const [diffText, setDiffText] = useState(
`--- a/terraform/compute.tf
+++ b/terraform/compute.tf
@@ -14,3 +14,3 @@
 resource "aws_instance" "worker_fleet" {
-  instance_type = "m5.2xlarge"
+  instance_type = "t4g.small"
   count         = 3
 }`
  );
  const [analysisResult, setAnalysisResult] = useState<any>(null);
  const [copiedWebhook, setCopiedWebhook] = useState(false);
  const [activePreset, setActivePreset] = useState(0);

  const PRESETS = [
    {
      label: 'Fleet Downsizing (Cost Reduction)',
      filePath: 'terraform/compute.tf',
      diff: `--- a/terraform/compute.tf\n+++ b/terraform/compute.tf\n@@ -14,3 +14,3 @@\n resource "aws_instance" "worker_fleet" {\n-  instance_type = "m5.2xlarge"\n+  instance_type = "t4g.small"\n   count         = 3\n }`,
    },
    {
      label: 'High-Spec GPU Spikes (> $500/mo Policy Breach)',
      filePath: 'terraform/ml_nodes.tf',
      diff: `--- a/terraform/ml_nodes.tf\n+++ b/terraform/ml_nodes.tf\n@@ -1,4 +1,8 @@\n+resource "aws_instance" "ai_cluster" {\n+  instance_type = "p4d.24xlarge"\n+  count         = 2\n+  ebs_block_device {\n+    volume_type = "io2"\n+    volume_size = 1000\n+    iops        = 50000\n+  }\n+}`,
    },
    {
      label: 'EBS gp2 to gp3 Storage Upgrade',
      filePath: 'terraform/storage.tf',
      diff: `--- a/terraform/storage.tf\n+++ b/terraform/storage.tf\n@@ -5,3 +5,3 @@\n resource "aws_ebs_volume" "primary_disk" {\n-  type = "gp2"\n+  type = "gp3"\n   size = 500\n }`,
    },
  ];

  useEffect(() => {
    let cancelled = false;
    const fetchStatus = async () => {
      try {
        const res = await fetch(apiUrl('/api/v2/github/status'));
        if (res.ok && !cancelled) setAppStatus(await res.json());
      } catch (err) {
        console.error('Failed to fetch github app status:', err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchStatus();
    return () => { cancelled = true; };
  }, [apiUrl]);

  const handleAnalyze = async () => {
    setAnalyzing(true);
    setAnalysisResult(null);
    try {
      const res = await fetch(apiUrl('/api/v2/github/analyze-pr'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          diff: diffText,
          file_path: filePath,
          currency,
          rate: 84.0,
          pull_number: 142,
        }),
      });
      if (res.ok) {
        setAnalysisResult(await res.json());
      }
    } catch (err) {
      console.error('Diff analysis failed:', err);
    } finally {
      setAnalyzing(false);
    }
  };

  const selectPreset = (idx: number) => {
    setActivePreset(idx);
    const p = PRESETS[idx];
    setFilePath(p.filePath);
    setDiffText(p.diff);
    setAnalysisResult(null);
  };

  const webhookEndpoint = apiUrl('/api/v2/github/webhook');
  const checkStatus = analysisResult?.check_run?.conclusion || 'neutral';
  const monthlyDelta = analysisResult?.analysis?.monthly_cost_delta_usd ?? 0;

  return (
    <>
      <SectionTitle
        eyebrow="FinOps Shift-Left CI/CD"
        title="Native GitHub App & PR Cost Guardrails"
        description="Automated cost impact diff analysis on Pull Requests before merging to prevent cloud bill shock."
        status={
          <Badge variant="outline" className="border-cyan-400/30 bg-cyan-400/10 text-cyan-300">
            PR Policy Enforcement
          </Badge>
        }
      />

      <div className="mb-6 grid gap-6 lg:grid-cols-3">
        <Card className="border-white/8 bg-card/70 lg:col-span-1">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                <GitPullRequest className="size-4 text-cyan-400" />
                GitHub App Status
              </CardTitle>
              <Badge variant="outline" className="border-emerald-400/30 bg-emerald-400/10 text-emerald-300 text-[11px]">
                {appStatus?.status === 'active' ? 'Active & Ready' : 'Configured'}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4 text-xs">
            <div>
              <span className="text-muted-foreground block">Application Name</span>
              <span className="font-semibold text-foreground text-sm">{appStatus?.app_name || 'CloudPulse FinOps Guardrail'}</span>
            </div>
            <div>
              <span className="text-muted-foreground block">Cost Spike Guardrail Policy</span>
              <span className="font-semibold text-amber-300">
                Block merge if PR spend delta &gt; ${appStatus?.spike_threshold_usd || 500}.00/mo
              </span>
            </div>
            <div>
              <span className="text-muted-foreground block">Supported CI/CD Engines</span>
              <div className="flex flex-wrap gap-1 mt-1">
                {(appStatus?.supported_providers || ['GitHub Actions', 'GitLab CI', 'Bitbucket']).map((p: string) => (
                  <Badge key={p} variant="outline" className="border-white/10 text-[10px]">{p}</Badge>
                ))}
              </div>
            </div>
            <div className="pt-2 border-t border-white/8">
              <span className="text-muted-foreground block mb-1">GitHub Webhook URL</span>
              <div className="flex items-center gap-1.5">
                <Input
                  readOnly
                  value={webhookEndpoint}
                  className="font-mono text-[11px] h-8 border-white/10 bg-white/5"
                />
                <Button
                  variant="outline"
                  size="sm"
                  className="h-8 border-white/10 px-2.5 shrink-0"
                  onClick={() => {
                    navigator.clipboard.writeText(webhookEndpoint);
                    setCopiedWebhook(true);
                    setTimeout(() => setCopiedWebhook(false), 2000);
                  }}
                >
                  {copiedWebhook ? <Check className="size-3 text-emerald-400" /> : <Copy className="size-3" />}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-white/8 bg-card/70 lg:col-span-2">
          <CardHeader>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <CardTitle className="text-base font-semibold">Interactive PR Diff Simulator</CardTitle>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Test Terraform HCL or cloud diffs against FinOps budget policies in real time.
                </p>
              </div>
              <Button
                size="sm"
                className="bg-cyan-400 text-slate-950 hover:bg-cyan-300 font-medium text-xs"
                onClick={handleAnalyze}
                disabled={analyzing}
              >
                {analyzing ? <Loader2 className="mr-1.5 size-3.5 animate-spin" /> : <Play className="mr-1.5 size-3.5" />}
                Run Guardrail Analysis
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <span className="text-xs text-muted-foreground block mb-1.5">Select Test Scenarios:</span>
              <div className="flex flex-wrap gap-2">
                {PRESETS.map((p, idx) => (
                  <Button
                    key={p.label}
                    type="button"
                    variant={activePreset === idx ? 'default' : 'outline'}
                    size="sm"
                    className={`text-xs h-7 ${activePreset === idx ? 'bg-cyan-500 text-slate-950 hover:bg-cyan-400' : 'border-white/10 bg-white/5'}`}
                    onClick={() => selectPreset(idx)}
                  >
                    {p.label}
                  </Button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
              <div className="sm:col-span-2">
                <label className="text-xs text-muted-foreground block mb-1">Target Infrastructure File Path</label>
                <Input
                  value={filePath}
                  onChange={e => setFilePath(e.target.value)}
                  className="font-mono text-xs h-8 border-white/10 bg-white/5"
                />
              </div>
            </div>

            <div>
              <label className="text-xs text-muted-foreground block mb-1">Git Diff / Terraform Plan Content</label>
              <textarea
                value={diffText}
                onChange={e => setDiffText(e.target.value)}
                rows={7}
                className="w-full rounded-lg border border-white/10 bg-black/60 p-3 font-mono text-xs text-emerald-300 focus:outline-none focus:ring-1 focus:ring-cyan-400"
                placeholder="Paste git diff or Terraform HCL change here..."
              />
            </div>
          </CardContent>
        </Card>
      </div>

      {analysisResult && (
        <Card className="border-white/8 bg-card/70 mb-6">
          <CardHeader>
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <CardTitle className="text-base flex items-center gap-2">
                <GitPullRequest className="size-4 text-cyan-400" />
                Guardrail Evaluation &amp; GitHub PR Comment Preview
              </CardTitle>
              <Badge
                variant="outline"
                className={`text-xs font-bold px-3 py-1 ${
                  checkStatus === 'failure'
                    ? 'border-red-400/40 bg-red-400/10 text-red-300'
                    : checkStatus === 'action_required'
                    ? 'border-amber-400/40 bg-amber-400/10 text-amber-300'
                    : 'border-emerald-400/40 bg-emerald-400/10 text-emerald-300'
                }`}
              >
                CHECK-RUN: {checkStatus.toUpperCase()}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div
              className={`p-4 rounded-lg border text-xs flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 ${
                checkStatus === 'failure'
                  ? 'border-red-400/30 bg-red-400/10 text-red-200'
                  : checkStatus === 'action_required'
                  ? 'border-amber-400/30 bg-amber-400/10 text-amber-200'
                  : 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200'
              }`}
            >
              <div className="flex items-center gap-2">
                {checkStatus === 'failure' ? (
                  <ShieldAlert className="size-5 text-red-400 shrink-0" />
                ) : checkStatus === 'action_required' ? (
                  <AlertTriangle className="size-5 text-amber-400 shrink-0" />
                ) : (
                  <ShieldCheck className="size-5 text-emerald-400 shrink-0" />
                )}
                <div>
                  <div className="font-semibold text-sm">
                    {checkStatus === 'failure'
                      ? '🚨 Merge Blocked: Cost Increase Breaches $500/mo FinOps Policy'
                      : checkStatus === 'action_required'
                      ? '⚠️ Warning: PR introduces moderate cost increase'
                      : '✅ FinOps Guardrail Passed: PR reduces infrastructure spend or maintains budget'}
                  </div>
                  <div className="text-[11px] opacity-90 mt-0.5">
                    {analysisResult.check_run?.output?.summary || 'Evaluated against organization FinOps baseline'}
                  </div>
                </div>
              </div>
              <div className="text-left sm:text-right shrink-0 font-mono pt-1 sm:pt-0 border-t sm:border-t-0 border-white/10">
                <div className="text-xs text-muted-foreground">Monthly Net Delta</div>
                <div className={`text-base font-bold ${monthlyDelta > 0 ? 'text-red-400' : 'text-emerald-300'}`}>
                  {monthlyDelta > 0 ? `+${formatCurrency(monthlyDelta, currency)}` : formatCurrency(monthlyDelta, currency)}/mo
                </div>
              </div>
            </div>

            <div>
              <span className="text-xs text-muted-foreground block mb-2 font-medium">Rendered GitHub PR Bot Comment:</span>
              <pre className="max-h-80 overflow-auto rounded-lg border border-white/10 bg-slate-950 p-4 font-mono text-xs text-slate-200 whitespace-pre-wrap">
                {analysisResult.comment_markdown || analysisResult.check_run?.output?.text}
              </pre>
            </div>
          </CardContent>
        </Card>
      )}
    </>
  );
}


export default CiCdGuardrailView
