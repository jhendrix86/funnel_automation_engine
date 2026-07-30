'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ArrowLeft, Cpu, Play, ChevronDown, ChevronUp } from 'lucide-react'

const EMPIRE_API = process.env.NEXT_PUBLIC_EMPIRE_API_URL || 'http://localhost:8100'

interface EngineDetail {
  name: string
  operators: string[]
}

export default function SystemPanel() {
  const [engines, setEngines] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [apiUp, setApiUp] = useState<boolean | null>(null)
  const [search, setSearch] = useState('')
  const [expanded, setExpanded] = useState<string | null>(null)
  const [details, setDetails] = useState<Record<string, EngineDetail>>({})
  const [runResults, setRunResults] = useState<Record<string, any>>({})
  const [runningEngine, setRunningEngine] = useState<string | null>(null)

  useEffect(() => {
    fetch(`${EMPIRE_API}/health`)
      .then((r) => r.json())
      .then(() => setApiUp(true))
      .catch(() => setApiUp(false))

    fetch(`${EMPIRE_API}/engines`)
      .then((r) => r.json())
      .then((d) => setEngines(d.engines || []))
      .catch(() => setApiUp(false))
      .finally(() => setLoading(false))
  }, [])

  const toggleExpand = async (name: string) => {
    if (expanded === name) {
      setExpanded(null)
      return
    }
    setExpanded(name)
    if (!details[name]) {
      try {
        const res = await fetch(`${EMPIRE_API}/engines/${name}`)
        const data = await res.json()
        setDetails((prev) => ({ ...prev, [name]: data }))
      } catch {
        // leave undetailed; card still shows the name
      }
    }
  }

  const runEngine = async (name: string) => {
    setRunningEngine(name)
    try {
      const res = await fetch(`${EMPIRE_API}/engines/${name}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ state: {} }),
      })
      const data = await res.json()
      setRunResults((prev) => ({ ...prev, [name]: data.result }))
    } catch (err) {
      setRunResults((prev) => ({ ...prev, [name]: { error: 'Request failed' } }))
    } finally {
      setRunningEngine(null)
    }
  }

  const filtered = engines.filter((e) => e.toLowerCase().includes(search.toLowerCase()))

  return (
    <main className="min-h-screen bg-[#0a0a0f] text-[#e8e8f0]">
      <div className="container mx-auto px-4 py-8 max-w-4xl">
        <Link href="/" className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-slate-200 mb-6">
          <ArrowLeft className="h-4 w-4" /> Back to funnels
        </Link>

        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-3">
            <Cpu className="h-7 w-7 text-violet-400" />
            <h1 className="text-3xl font-bold">System</h1>
          </div>
          {apiUp !== null && (
            <span className={`text-xs font-medium px-3 py-1 rounded-full border ${apiUp ? 'bg-[#39ff14]/10 text-[#39ff14] border-[#39ff14]/40' : 'bg-red-500/15 text-red-400 border-red-500/40'}`}>
              {apiUp ? `empire_os live · ${engines.length} engines` : 'empire_os API unreachable'}
            </span>
          )}
        </div>
        <p className="text-slate-400 text-sm mb-6">
          The empire_os engine registry, live. Click an engine to see its operators; run any engine with an empty state to see its default behavior.
        </p>

        {!loading && apiUp && (
          <Input
            placeholder="Search engines…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="bg-[#111118] border-[#2a2a3a] mb-6"
          />
        )}

        {loading ? (
          <div className="text-center py-12 text-slate-300">Loading engine registry…</div>
        ) : !apiUp ? (
          <Card className="bg-[#111118] border-[#1e1e2e] p-6 text-center text-slate-400">
            Could not reach the empire_os API at {EMPIRE_API}. Is the <code className="text-violet-400">empire-os-api</code> container running?
          </Card>
        ) : (
          <div className="grid gap-2">
            {filtered.map((name) => (
              <Card key={name} className="bg-[#111118] border-[#1e1e2e] overflow-hidden">
                <button
                  type="button"
                  onClick={() => toggleExpand(name)}
                  className="w-full flex items-center justify-between p-4 text-left hover:bg-white/[0.02] transition-colors"
                >
                  <span className="font-mono text-sm text-slate-200">{name}</span>
                  {expanded === name ? <ChevronUp className="h-4 w-4 text-slate-400" /> : <ChevronDown className="h-4 w-4 text-slate-400" />}
                </button>
                {expanded === name && (
                  <div className="px-4 pb-4 border-t border-[#1e1e2e] pt-3">
                    <div className="text-xs text-slate-300 mb-2">
                      Operators: {details[name]?.operators?.join(', ') || 'loading…'}
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => runEngine(name)}
                      disabled={runningEngine === name}
                      className="border-violet-500/40 text-violet-300 hover:bg-violet-500/10"
                    >
                      <Play className="h-3 w-3 mr-1.5" />
                      {runningEngine === name ? 'Running…' : 'Run with empty state'}
                    </Button>
                    {runResults[name] && (
                      <pre className="mt-3 text-xs bg-[#0a0a0f] border border-[#1e1e2e] rounded p-3 overflow-x-auto text-emerald-300">
                        {JSON.stringify(runResults[name], null, 2)}
                      </pre>
                    )}
                  </div>
                )}
              </Card>
            ))}
          </div>
        )}
      </div>
    </main>
  )
}
