'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { CheckCircle2, Circle, Loader2, XCircle, ArrowLeft, Rocket } from 'lucide-react'

type StageStatus = 'pending' | 'running' | 'done' | 'error'

interface Stage {
  id: string
  label: string
  detail: string
  status: StageStatus
  result?: string
}

const INITIAL_STAGES: Stage[] = [
  { id: 'research', label: 'Product Research', detail: 'empire_os research_toolkit — 8-step Primary Research Flow', status: 'pending' },
  { id: 'product', label: 'Product & Funnel Creation', detail: 'Gumroad product + funnel structure + content + email + lead scoring + automation', status: 'pending' },
  { id: 'launch', label: 'Launch', detail: 'Activate traffic, email, and SEO for the funnel', status: 'pending' },
  { id: 'tracking', label: 'Customer Tracking', detail: 'Live funnel analytics: visitors, leads, conversions, revenue', status: 'pending' },
]

const EMPIRE_API = process.env.NEXT_PUBLIC_EMPIRE_API_URL || 'http://localhost:8100'
const ORCHESTRATOR_API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function StageIcon({ status }: { status: StageStatus }) {
  if (status === 'done') return <CheckCircle2 className="h-5 w-5 text-emerald-400" />
  if (status === 'running') return <Loader2 className="h-5 w-5 text-violet-400 animate-spin" />
  if (status === 'error') return <XCircle className="h-5 w-5 text-red-400" />
  return <Circle className="h-5 w-5 text-slate-600" />
}

export default function MissionControl() {
  const [stages, setStages] = useState<Stage[]>(INITIAL_STAGES)
  const [running, setRunning] = useState(false)
  const [live, setLive] = useState(false)
  const [productName, setProductName] = useState('')
  const [productDescription, setProductDescription] = useState('')
  const [productPrice, setProductPrice] = useState('29.99')
  const [targetAudience, setTargetAudience] = useState('')
  const [funnelId, setFunnelId] = useState<string | null>(null)

  const updateStage = (id: string, patch: Partial<Stage>) => {
    setStages((prev) => prev.map((s) => (s.id === id ? { ...s, ...patch } : s)))
  }

  const runPipeline = async () => {
    setRunning(true)
    setStages(INITIAL_STAGES.map((s) => ({ ...s, status: 'pending', result: undefined })))
    setFunnelId(null)

    // Stage 1: Research (empire_os) -- always real, pure computation, no external side effects
    updateStage('research', { status: 'running' })
    let researchSummary = ''
    try {
      const res = await fetch(`${EMPIRE_API}/engines/research_toolkit/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          state: { topic: productName || 'this product', data: [productDescription] },
        }),
      })
      const data = await res.json()
      const output = data.result?.research_output
      researchSummary = output?.summary || 'No summary generated'
      updateStage('research', {
        status: 'done',
        result: `${output?.insights?.length ?? 0} insights, ${output?.gaps?.length ?? 0} gaps identified`,
      })
    } catch (err) {
      updateStage('research', { status: 'error', result: 'empire_os API unreachable' })
      setRunning(false)
      return
    }

    // Stage 2: Product + Funnel -- gated by Live/Simulate
    updateStage('product', { status: 'running' })
    if (!live) {
      await new Promise((r) => setTimeout(r, 900))
      updateStage('product', { status: 'done', result: 'SIMULATED — no real product or funnel was created' })
      updateStage('launch', { status: 'done', result: 'SIMULATED — nothing was actually launched' })
      updateStage('tracking', { status: 'done', result: 'SIMULATED — no real analytics to show' })
      setRunning(false)
      return
    }

    try {
      const res = await fetch(`${ORCHESTRATOR_API}/funnel/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: `${productName} Funnel`,
          create_product: true,
          product_name: productName,
          product_description: `${productDescription}\n\nResearch summary: ${researchSummary}`,
          product_price: parseFloat(productPrice),
          product_tags: [],
          target_audience: { description: targetAudience },
          goals: ['increase_sales'],
          auto_launch: true,
        }),
      })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      setFunnelId(data.funnel_id || data._id || null)
      updateStage('product', { status: 'done', result: `Funnel created: ${data.funnel_id || data._id || 'unknown id'}` })
      updateStage('launch', { status: 'done', result: 'Traffic, email, and SEO activated' })
    } catch (err: any) {
      updateStage('product', { status: 'error', result: err.message || 'Failed to create funnel' })
      setRunning(false)
      return
    }

    // Stage 4: Tracking -- pull the real funnel back to show live analytics
    updateStage('tracking', { status: 'running' })
    try {
      const res = await fetch(`${ORCHESTRATOR_API}/funnels`)
      const data = await res.json()
      const created = data.funnels?.find((f: any) => f._id === funnelId) || data.funnels?.[0]
      updateStage('tracking', {
        status: 'done',
        result: created
          ? `${created.analytics?.visitors ?? 0} visitors, ${created.analytics?.leads ?? 0} leads, $${created.analytics?.revenue ?? 0} revenue`
          : 'Funnel created — analytics will populate as traffic arrives',
      })
    } catch {
      updateStage('tracking', { status: 'error', result: 'Could not fetch tracking data' })
    }

    setRunning(false)
  }

  return (
    <main className="min-h-screen bg-[#0a0a0f] text-[#e8e8f0]">
      <div className="container mx-auto px-4 py-8 max-w-3xl">
        <Link href="/" className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-slate-200 mb-6">
          <ArrowLeft className="h-4 w-4" /> Back to funnels
        </Link>

        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-1">Mission Control</h1>
          <p className="text-slate-400 text-sm">
            One button: research the product, create and launch the funnel, then track real customers.
          </p>
        </div>

        <Card className="bg-[#111118] border-[#1e1e2e] p-6 mb-6 space-y-4">
          <div className="grid gap-2">
            <Label htmlFor="mc-name">Product Name</Label>
            <Input id="mc-name" value={productName} onChange={(e) => setProductName(e.target.value)} placeholder="e.g., Deterministic Prompt Pack" className="bg-[#0a0a0f] border-[#2a2a3a]" />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="mc-desc">Product Description</Label>
            <Textarea id="mc-desc" value={productDescription} onChange={(e) => setProductDescription(e.target.value)} rows={3} placeholder="What it is, who it's for, why it's different" className="bg-[#0a0a0f] border-[#2a2a3a]" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="grid gap-2">
              <Label htmlFor="mc-price">Price ($)</Label>
              <Input id="mc-price" type="number" step="0.01" value={productPrice} onChange={(e) => setProductPrice(e.target.value)} className="bg-[#0a0a0f] border-[#2a2a3a]" />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="mc-audience">Target Audience</Label>
              <Input id="mc-audience" value={targetAudience} onChange={(e) => setTargetAudience(e.target.value)} placeholder="e.g., Indie founders" className="bg-[#0a0a0f] border-[#2a2a3a]" />
            </div>
          </div>

          <div className="flex items-center justify-between pt-2 border-t border-[#1e1e2e]">
            <div>
              <div className="text-sm font-medium">{live ? 'LIVE — will really create a Gumroad product' : 'SIMULATE — nothing real happens'}</div>
              <div className="text-xs text-slate-500">Research always runs for real (pure computation, no cost, no external effect).</div>
            </div>
            <button
              type="button"
              onClick={() => setLive((v) => !v)}
              className={`relative h-7 w-12 rounded-full transition-colors ${live ? 'bg-red-500' : 'bg-[#2a2a3a]'}`}
              aria-pressed={live}
              aria-label="Toggle live mode"
            >
              <span className={`absolute top-1 h-5 w-5 rounded-full bg-white transition-transform ${live ? 'translate-x-6' : 'translate-x-1'}`} />
            </button>
          </div>

          <Button
            onClick={runPipeline}
            disabled={running || !productName || !productDescription}
            size="lg"
            className="w-full bg-violet-600 hover:bg-violet-700 text-white"
          >
            {running ? <Loader2 className="mr-2 h-5 w-5 animate-spin" /> : <Rocket className="mr-2 h-5 w-5" />}
            {running ? 'Running…' : live ? 'Go — Run For Real' : 'Go — Simulate'}
          </Button>
        </Card>

        <div className="space-y-3">
          {stages.map((stage) => (
            <Card key={stage.id} className="bg-[#111118] border-[#1e1e2e] p-4">
              <div className="flex items-start gap-3">
                <div className="mt-0.5"><StageIcon status={stage.status} /></div>
                <div className="flex-1 min-w-0">
                  <div className="font-medium">{stage.label}</div>
                  <div className="text-xs text-slate-500">{stage.detail}</div>
                  {stage.result && (
                    <div className={`text-xs mt-1 ${stage.status === 'error' ? 'text-red-400' : 'text-emerald-400'}`}>
                      {stage.result}
                    </div>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </main>
  )
}
