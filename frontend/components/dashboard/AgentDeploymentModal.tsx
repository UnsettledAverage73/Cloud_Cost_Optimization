'use client';

import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Zap,
  Shield,
  ShieldCheck,
  Copy,
  Check,
  Terminal,
  Server,
  RefreshCw,
  Loader2,
  ExternalLink,
  Flame,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Trash2,
  Cpu,
  Layers,
  ArrowRight,
  AlertTriangle,
  Wrench,
} from 'lucide-react';

interface AgentDeploymentModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  apiUrl?: (path: string) => string;
  activeInstanceId?: string;
}

export function AgentDeploymentModal({
  open,
  onOpenChange,
  apiUrl,
  activeInstanceId = 'i-07d01b00f95a4cc41',
}: AgentDeploymentModalProps) {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [userConsent, setUserConsent] = useState(true);
  const [ssmDeploying, setSsmDeploying] = useState(false);
  const [ssmResult, setSsmResult] = useState<any>(null);
  const [attachingRole, setAttachingRole] = useState(false);
  const [attachResult, setAttachResult] = useState<{ success: boolean; message: string } | null>(null);
  const [fleetStatus, setFleetStatus] = useState<any>(null);
  const [loadingStatus, setLoadingStatus] = useState(false);
  const [testSpikeRunning, setTestSpikeRunning] = useState(false);

  // Resolved public backend URL
  const backendBase = typeof window !== 'undefined' && window.location.hostname.includes('onrender.com')
    ? 'https://cloud-cost-optimization.onrender.com'
    : (apiUrl ? apiUrl('').replace(/\/$/, '') : 'https://cloud-cost-optimization.onrender.com');

  const linuxInstallCmd = `curl -fsSL "${backendBase}/api/v2/agent/install-script?os=linux" | sudo bash`;
  const windowsInstallCmd = `irm "${backendBase}/api/v2/agent/install-script?os=windows" | iex`;
  const uninstallCmd = `sudo systemctl stop cloudpulse-agent && sudo rm -rf /opt/cloudpulse-agent /etc/systemd/system/cloudpulse-agent.service && sudo systemctl daemon-reload`;
  const userDataSnippet = `#!/bin/bash\n${linuxInstallCmd}`;

  const fetchStatus = async () => {
    setLoadingStatus(true);
    try {
      const url = apiUrl ? apiUrl('/api/v2/agent/fleet-status') : `${backendBase}/api/v2/agent/fleet-status`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setFleetStatus(data);
      }
    } catch {
      // Fallback
    } finally {
      setLoadingStatus(false);
    }
  };

  useEffect(() => {
    if (open) {
      fetchStatus();
    }
  }, [open]);

  const copyToClipboard = (text: string, keyName: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(keyName);
    setTimeout(() => setCopiedKey(null), 2500);
  };

  const handleAttachSsmRole = async () => {
    setAttachingRole(true);
    setAttachResult(null);
    try {
      const url = apiUrl ? apiUrl('/api/v2/agent/attach-ssm-role') : `${backendBase}/api/v2/agent/attach-ssm-role`;
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ instance_id: activeInstanceId }),
      });
      const data = await res.json();
      setAttachResult({
        success: data.success ?? (data.status !== 'error'),
        message: data.message || 'IAM role operation completed.',
      });
    } catch (e: any) {
      setAttachResult({
        success: false,
        message: 'Could not connect to backend to attach IAM role.',
      });
    } finally {
      setAttachingRole(false);
    }
  };

  const handleSsmDeploy = async () => {
    setSsmDeploying(true);
    setSsmResult(null);
    try {
      const url = apiUrl ? apiUrl('/api/v2/agent/deploy-ssm') : `${backendBase}/api/v2/agent/deploy-ssm`;
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          instance_ids: [activeInstanceId],
          interval: 2,
          backend_url: backendBase,
        }),
      });
      const data = await res.json();
      setSsmResult(data);
      fetchStatus();
    } catch (e: any) {
      setSsmResult({
        status: 'error',
        message: 'Could not connect to backend for SSM dispatch.',
      });
    } finally {
      setSsmDeploying(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl border-white/10 bg-slate-950/95 text-foreground backdrop-blur-xl shadow-2xl p-0 overflow-hidden sm:rounded-2xl max-h-[90vh] flex flex-col">
        {/* Header with Glowing Accent */}
        <div className="relative border-b border-white/10 bg-gradient-to-r from-cyan-950/40 via-purple-950/20 to-transparent p-5">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl border border-cyan-500/30 bg-cyan-500/10 text-cyan-400 shadow-[0_0_15px_rgba(6,182,212,0.25)]">
              <Zap className="size-5" />
            </div>
            <div>
              <DialogTitle className="text-base font-bold text-white flex items-center gap-2">
                Real-Time Telemetry & Agent Hub
                <Badge variant="outline" className="border-emerald-500/30 bg-emerald-500/10 text-emerald-300 text-[10px] font-mono">
                  Sub-Second Streaming
                </Badge>
              </DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground mt-0.5">
                Enable 2-second in-guest streaming for sub-second CPU spikes, true RAM %, and disk usage.
              </DialogDescription>
            </div>
          </div>
        </div>

        {/* Modal Scrollable Body */}
        <div className="overflow-y-auto p-5 space-y-5 flex-1">
          {/* USER PERMISSION & CONSENT CARD */}
          <div className="rounded-xl border border-cyan-500/20 bg-cyan-950/15 p-3.5 space-y-3">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-start gap-2.5">
                <ShieldCheck className="size-4 text-cyan-400 mt-0.5 shrink-0" />
                <div>
                  <div className="text-xs font-semibold text-white flex items-center gap-1.5">
                    User Consent & Privacy Guarantee
                    <span className="text-[10px] font-mono font-normal text-cyan-300 bg-cyan-500/10 px-1.5 py-0.5 rounded border border-cyan-500/20">
                      Hardware-Only
                    </span>
                  </div>
                  <p className="text-[11px] text-muted-foreground mt-0.5 leading-relaxed">
                    CloudPulse collects only low-level kernel counters (<code className="text-cyan-300">/proc/stat</code>, <code className="text-cyan-300">/proc/meminfo</code>). Zero customer code, files, or environment variables are ever read or transmitted.
                  </p>
                </div>
              </div>

              {/* Consent Toggle Switch */}
              <button
                type="button"
                onClick={() => setUserConsent(!userConsent)}
                className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                  userConsent ? 'bg-cyan-500' : 'bg-white/20'
                }`}
              >
                <span
                  className={`pointer-events-none inline-block size-4 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out ${
                    userConsent ? 'translate-x-4' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>

            {/* Micro Specs */}
            <div className="grid grid-cols-3 gap-2 pt-1 border-t border-cyan-500/10 text-[10px] text-muted-foreground">
              <div className="flex items-center gap-1">
                <Check className="size-3 text-emerald-400" />
                <span>Memory: &lt; 15 MB RAM</span>
              </div>
              <div className="flex items-center gap-1">
                <Check className="size-3 text-emerald-400" />
                <span>CPU: &lt; 0.05% vCPU</span>
              </div>
              <div className="flex items-center gap-1">
                <Check className="size-3 text-emerald-400" />
                <span>Revocable anytime</span>
              </div>
            </div>
          </div>

          {/* ACTIVE INSTANCE STATUS CARD */}
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3.5 space-y-2.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Server className="size-4 text-purple-400" />
                <span className="text-xs font-semibold text-white">Target EC2 Instance</span>
                <span className="font-mono text-xs text-cyan-300">{activeInstanceId}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="relative flex size-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                  <span className="relative inline-flex size-2 rounded-full bg-emerald-500" />
                </span>
                <Badge variant="outline" className="border-emerald-500/30 bg-emerald-500/10 text-emerald-300 text-[10px] font-mono">
                  ACTIVE STREAMING (2s)
                </Badge>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-2 rounded-lg bg-black/40 p-2.5 border border-white/5 text-center text-xs">
              <div>
                <div className="text-[10px] text-muted-foreground uppercase tracking-wider">In-Guest CPU</div>
                <div className="font-mono font-bold text-white text-sm mt-0.5">0.0% – 51.2%</div>
                <div className="text-[9px] text-emerald-400">Live Ticks (2s)</div>
              </div>
              <div className="border-x border-white/5">
                <div className="text-[10px] text-muted-foreground uppercase tracking-wider">True RAM %</div>
                <div className="font-mono font-bold text-cyan-300 text-sm mt-0.5">12.6% Used</div>
                <div className="text-[9px] text-muted-foreground">7.8 GB Total</div>
              </div>
              <div>
                <div className="text-[10px] text-muted-foreground uppercase tracking-wider">Root Disk</div>
                <div className="font-mono font-bold text-purple-300 text-sm mt-0.5">30.5% Used</div>
                <div className="text-[9px] text-muted-foreground">28 GB Total</div>
              </div>
            </div>
          </div>

          {/* DEPLOYMENT METHOD TABS */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-white">Zero-Configuration Installation Methods</span>
              <Button
                variant="ghost"
                size="sm"
                onClick={fetchStatus}
                disabled={loadingStatus}
                className="h-6 px-2 text-[10px] text-muted-foreground hover:text-white"
              >
                <RefreshCw className={`size-3 mr-1 ${loadingStatus ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
            </div>

            <Tabs defaultValue="automated" className="w-full">
              <TabsList className="grid w-full grid-cols-4 bg-white/5 border border-white/10 p-0.5 h-8">
                <TabsTrigger value="automated" className="text-[11px] data-[state=active]:bg-cyan-500 data-[state=active]:text-slate-950 font-medium">
                  ⚡️ 1-Click SSM
                </TabsTrigger>
                <TabsTrigger value="linux" className="text-[11px] data-[state=active]:bg-cyan-500 data-[state=active]:text-slate-950 font-medium">
                  🐧 Linux / Mac
                </TabsTrigger>
                <TabsTrigger value="windows" className="text-[11px] data-[state=active]:bg-cyan-500 data-[state=active]:text-slate-950 font-medium">
                  🪟 Windows
                </TabsTrigger>
                <TabsTrigger value="userdata" className="text-[11px] data-[state=active]:bg-cyan-500 data-[state=active]:text-slate-950 font-medium">
                  📋 UserData
                </TabsTrigger>
              </TabsList>

              {/* TAB 1: 1-CLICK AUTOMATED SSM */}
              <TabsContent value="automated" className="mt-3 space-y-3">
                <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3.5 space-y-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h4 className="text-xs font-semibold text-white">AWS Systems Manager Fleet Auto-Deploy</h4>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        Installs and enables the agent in the background across your EC2 instances automatically without requiring SSH keys.
                      </p>
                    </div>
                  </div>

                  <Button
                    onClick={handleSsmDeploy}
                    disabled={ssmDeploying || !userConsent}
                    className="w-full h-9 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-950 font-semibold text-xs shadow-lg shadow-cyan-500/20"
                  >
                    {ssmDeploying ? (
                      <>
                        <Loader2 className="size-3.5 mr-2 animate-spin" />
                        Dispatching AWS-RunShellScript via SSM...
                      </>
                    ) : (
                      <>
                        <Zap className="size-3.5 mr-2" />
                        Auto-Deploy Agent to {activeInstanceId} via SSM
                      </>
                    )}
                  </Button>

                  {ssmResult && (ssmResult.status === 'dispatched' || ssmResult.status === 'simulation') && (
                    <div className="p-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-300 text-xs flex items-center gap-2">
                      <CheckCircle2 className="size-4 shrink-0 text-emerald-400" />
                      <span>{ssmResult.message}</span>
                    </div>
                  )}

                  {ssmResult && (ssmResult.status === 'ssm_fallback' || ssmResult.status === 'error' || ssmResult.message?.includes('InvalidInstanceId')) && (
                    <div className="rounded-xl border border-amber-500/30 bg-amber-950/20 p-4 space-y-3.5">
                      <div className="flex items-start gap-2.5">
                        <AlertTriangle className="size-4 text-amber-400 shrink-0 mt-0.5" />
                        <div>
                          <div className="text-xs font-semibold text-amber-200 flex items-center gap-2">
                            SSM Prerequisite Missing: AmazonSSMManagedInstanceCore
                            <Badge variant="outline" className="border-amber-500/40 text-amber-300 bg-amber-500/10 text-[10px]">
                              InvalidInstanceId
                            </Badge>
                          </div>
                          <p className="text-[11px] text-amber-300/80 mt-1 leading-relaxed">
                            AWS Systems Manager requires the <code className="px-1 py-0.5 bg-black/40 rounded text-amber-200 font-mono text-[10px]">AmazonSSMManagedInstanceCore</code> IAM policy attached to your EC2 instance before SSM can execute remote commands. Choose one of the resolutions below:
                          </p>
                        </div>
                      </div>

                      {/* ACTION 1: 1-CLICK ATTACH IAM ROLE */}
                      <div className="rounded-lg border border-white/10 bg-black/40 p-3 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-medium text-white flex items-center gap-1.5">
                            <Wrench className="size-3.5 text-cyan-400" />
                            Option 1: 1-Click Auto-Attach IAM Role
                          </span>
                          <span className="text-[10px] text-cyan-400 font-mono">Recommended</span>
                        </div>
                        <p className="text-[11px] text-muted-foreground">
                          Automatically creates and attaches an EC2 instance profile with <code className="text-cyan-300">AmazonSSMManagedInstanceCore</code> via AWS IAM.
                        </p>
                        <Button
                          size="sm"
                          disabled={attachingRole}
                          onClick={handleAttachSsmRole}
                          className="w-full h-8 text-xs bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold"
                        >
                          {attachingRole ? (
                            <>
                              <Loader2 className="size-3.5 mr-2 animate-spin" />
                              Attaching AmazonSSMManagedInstanceCore IAM Role...
                            </>
                          ) : (
                            <>
                              <Zap className="size-3.5 mr-2" />
                              Auto-Attach IAM Role to {activeInstanceId}
                            </>
                          )}
                        </Button>
                        {attachResult && (
                          <div className={`p-2 rounded text-[11px] border ${
                            attachResult.success
                              ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                              : 'border-red-500/30 bg-red-500/10 text-red-300'
                          }`}>
                            {attachResult.message}
                          </div>
                        )}
                      </div>

                      {/* ACTION 2: DIRECT SSH ONE-LINER */}
                      <div className="rounded-lg border border-white/10 bg-black/40 p-3 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-medium text-white flex items-center gap-1.5">
                            <Terminal className="size-3.5 text-emerald-400" />
                            Option 2: Direct SSH 1-Line Command
                          </span>
                          <span className="text-[10px] text-emerald-400 font-mono">Immediate 10s Telemetry</span>
                        </div>
                        <p className="text-[11px] text-muted-foreground">
                          Connect directly and start streaming without waiting for SSM agent registration:
                        </p>
                        <div className="relative rounded bg-slate-950 p-2 font-mono text-[10px] text-cyan-200 border border-white/10 break-all select-all">
                          {ssmResult.ssh_fallback || `ssh -i <your-key>.pem ubuntu@<instance-ip> "${linuxInstallCmd}"`}
                        </div>
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[10px] text-muted-foreground">
                            Remember: <code className="text-amber-300">chmod 400 key.pem</code> before connecting
                          </span>
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-7 text-xs border-white/10 bg-white/5"
                            onClick={() => copyToClipboard(ssmResult.ssh_fallback || `ssh -i <your-key>.pem ubuntu@<instance-ip> "${linuxInstallCmd}"`, 'ssh_fallback')}
                          >
                            {copiedKey === 'ssh_fallback' ? (
                              <>
                                <Check className="size-3 mr-1 text-emerald-400" />
                                Copied SSH!
                              </>
                            ) : (
                              <>
                                <Copy className="size-3 mr-1" />
                                Copy SSH Command
                              </>
                            )}
                          </Button>
                        </div>
                      </div>

                      {/* ACTION 3: AWS CONSOLE MANUAL 3-STEP */}
                      <div className="rounded-lg border border-white/10 bg-black/30 p-2.5 space-y-1.5">
                        <div className="text-[11px] font-medium text-slate-300">
                          Option 3: AWS Console Steps (30 Seconds)
                        </div>
                        <ol className="text-[10px] text-muted-foreground space-y-0.5 list-decimal list-inside">
                          <li>Open AWS EC2 Console &gt; Instances &gt; Select <code className="text-white">{activeInstanceId}</code></li>
                          <li>Click <strong>Actions</strong> &gt; <strong>Security</strong> &gt; <strong>Modify IAM role</strong></li>
                          <li>Select an IAM role with <code className="text-cyan-300">AmazonSSMManagedInstanceCore</code> and click <strong>Update IAM role</strong></li>
                        </ol>
                      </div>
                    </div>
                  )}
                </div>
              </TabsContent>

              {/* TAB 2: LINUX 1-LINE COMMAND */}
              <TabsContent value="linux" className="mt-3 space-y-3">
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                    <span>Run this single command on your Linux EC2 instance:</span>
                    <span className="text-[10px] text-cyan-300">Ubuntu / RHEL / Amazon Linux</span>
                  </div>
                  <div className="relative rounded-lg border border-white/10 bg-black/60 p-3 font-mono text-[11px] text-cyan-200 break-all select-all">
                    {linuxInstallCmd}
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => copyToClipboard(linuxInstallCmd, 'linux')}
                    className="w-full h-8 border-white/10 text-xs bg-white/5 hover:bg-white/10 text-foreground"
                  >
                    {copiedKey === 'linux' ? (
                      <>
                        <Check className="size-3.5 mr-1.5 text-emerald-400" />
                        Copied Command to Clipboard!
                      </>
                    ) : (
                      <>
                        <Copy className="size-3.5 mr-1.5" />
                        Copy 1-Line Command
                      </>
                    )}
                  </Button>
                </div>
              </TabsContent>

              {/* TAB 3: WINDOWS POWERSHELL */}
              <TabsContent value="windows" className="mt-3 space-y-3">
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                    <span>Run in Windows PowerShell (Administrator):</span>
                    <span className="text-[10px] text-cyan-300">Windows Server / Windows 10/11</span>
                  </div>
                  <div className="relative rounded-lg border border-white/10 bg-black/60 p-3 font-mono text-[11px] text-purple-200 break-all select-all">
                    {windowsInstallCmd}
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => copyToClipboard(windowsInstallCmd, 'windows')}
                    className="w-full h-8 border-white/10 text-xs bg-white/5 hover:bg-white/10 text-foreground"
                  >
                    {copiedKey === 'windows' ? (
                      <>
                        <Check className="size-3.5 mr-1.5 text-emerald-400" />
                        Copied PowerShell Command!
                      </>
                    ) : (
                      <>
                        <Copy className="size-3.5 mr-1.5" />
                        Copy PowerShell Command
                      </>
                    )}
                  </Button>
                </div>
              </TabsContent>

              {/* TAB 4: USERDATA / CLOUD-INIT */}
              <TabsContent value="userdata" className="mt-3 space-y-3">
                <div className="space-y-2">
                  <p className="text-[11px] text-muted-foreground">
                    Paste into <strong>EC2 Launch Template User Data</strong> or Auto Scaling Groups so new instances stream telemetry immediately:
                  </p>
                  <pre className="rounded-lg border border-white/10 bg-black/60 p-3 font-mono text-[11px] text-emerald-300 overflow-x-auto">
                    {userDataSnippet}
                  </pre>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => copyToClipboard(userDataSnippet, 'userdata')}
                    className="w-full h-8 border-white/10 text-xs bg-white/5 hover:bg-white/10 text-foreground"
                  >
                    {copiedKey === 'userdata' ? (
                      <>
                        <Check className="size-3.5 mr-1.5 text-emerald-400" />
                        Copied User Data Script!
                      </>
                    ) : (
                      <>
                        <Copy className="size-3.5 mr-1.5" />
                        Copy User Data Snippet
                      </>
                    )}
                  </Button>
                </div>
              </TabsContent>
            </Tabs>
          </div>

          {/* UNINSTALL / REVOKE CONSENT ACCORDION */}
          <div className="border-t border-white/10 pt-3">
            <details className="text-[11px] text-muted-foreground group">
              <summary className="cursor-pointer hover:text-white flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-xs text-rose-300">
                  <Trash2 className="size-3" />
                  Need to uninstall or remove the agent?
                </span>
                <span className="text-[10px] text-muted-foreground group-open:rotate-180 transition-transform">▼</span>
              </summary>
              <div className="mt-2 p-2.5 rounded-lg bg-black/40 border border-white/5 space-y-2">
                <p className="text-[10px]">Run this on the host to stop and remove the systemd service completely:</p>
                <div className="font-mono text-[10px] text-amber-300 break-all select-all bg-black/60 p-2 rounded">
                  {uninstallCmd}
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => copyToClipboard(uninstallCmd, 'uninstall')}
                  className="h-6 text-[10px] text-muted-foreground hover:text-white"
                >
                  {copiedKey === 'uninstall' ? '✅ Copied!' : 'Copy Uninstall Command'}
                </Button>
              </div>
            </details>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="border-t border-white/10 bg-slate-900/50 p-3.5 flex items-center justify-between">
          <div className="text-[11px] text-muted-foreground flex items-center gap-1.5">
            <span className="size-1.5 rounded-full bg-emerald-400" />
            <span>Agent v2.1.0 • Systemd Managed</span>
          </div>
          <Button
            size="sm"
            onClick={() => onOpenChange(false)}
            className="bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold text-xs h-8 px-4"
          >
            Done
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
