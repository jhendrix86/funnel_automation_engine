'use client'

import { useEffect, useState } from 'react'
import { FunnelDashboard } from '@/components/FunnelDashboard'
import { CreateFunnelModal } from '@/components/CreateFunnelModal'
import { Button } from '@/components/ui/button'
import { Plus } from 'lucide-react'

interface Funnel {
  _id: string
  name: string
  productName: string
  status: string
  analytics: {
    visitors: number
    leads: number
    conversions: number
    revenue: number
    conversionRate: number
  }
  createdAt: string
}

export default function Home() {
  const [funnels, setFunnels] = useState<Funnel[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreateModal, setShowCreateModal] = useState(false)

  useEffect(() => {
    fetchFunnels()
  }, [])

  const fetchFunnels = async () => {
    try {
      const response = await fetch('http://localhost:8000/funnels')
      const data = await response.json()
      setFunnels(data.funnels || [])
    } catch (error) {
      console.error('Error fetching funnels:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleFunnelCreated = () => {
    setShowCreateModal(false)
    fetchFunnels()
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
      <div className="container mx-auto px-4 py-8">
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-4xl font-bold text-slate-900 dark:text-slate-50 mb-2">
              Traffic Funnel Engine
            </h1>
            <p className="text-slate-600 dark:text-slate-400">
              Autonomous sales funnels for your Gumroad products
            </p>
          </div>
          <Button onClick={() => setShowCreateModal(true)} size="lg">
            <Plus className="mr-2 h-5 w-5" />
            Create Funnel
          </Button>
        </div>

        {loading ? (
          <div className="text-center py-12">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-current border-r-transparent align-[-0.125em] motion-reduce:animate-[spin_1.5s_linear_infinite]"></div>
            <p className="mt-4 text-slate-600 dark:text-slate-400">Loading funnels...</p>
          </div>
        ) : funnels.length === 0 ? (
          <div className="text-center py-12 bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700">
            <div className="text-6xl mb-4">🚀</div>
            <h2 className="text-2xl font-semibold text-slate-900 dark:text-slate-50 mb-2">
              No funnels yet
            </h2>
            <p className="text-slate-600 dark:text-slate-400 mb-6">
              Create your first autonomous funnel to start driving sales
            </p>
            <Button onClick={() => setShowCreateModal(true)} size="lg">
              <Plus className="mr-2 h-5 w-5" />
              Create Your First Funnel
            </Button>
          </div>
        ) : (
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {funnels.map((funnel) => (
              <FunnelDashboard key={funnel._id} funnel={funnel} onUpdate={fetchFunnels} />
            ))}
          </div>
        )}
      </div>

      {showCreateModal && (
        <CreateFunnelModal onClose={() => setShowCreateModal(false)} onSuccess={handleFunnelCreated} />
      )}
    </main>
  )
}
