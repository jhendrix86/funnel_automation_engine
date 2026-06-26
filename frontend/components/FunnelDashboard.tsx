'use client'

import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Play, Pause, BarChart3, Users, DollarSign, TrendingUp } from 'lucide-react'

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

interface FunnelDashboardProps {
  funnel: Funnel
  onUpdate: () => void
}

export function FunnelDashboard({ funnel, onUpdate }: FunnelDashboardProps) {
  const [loading, setLoading] = useState(false)

  const handleLaunch = async () => {
    setLoading(true)
    try {
      const response = await fetch(`http://localhost:8000/funnel/${funnel._id}/launch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          launch_traffic: true,
          launch_email_campaign: true,
          launch_seo: true
        })
      })
      if (response.ok) {
        onUpdate()
      }
    } catch (error) {
      console.error('Error launching funnel:', error)
    } finally {
      setLoading(false)
    }
  }

  const handlePause = async () => {
    setLoading(true)
    try {
      const response = await fetch(`http://localhost:8000/funnel/${funnel._id}/pause`, {
        method: 'POST'
      })
      if (response.ok) {
        onUpdate()
      }
    } catch (error) {
      console.error('Error pausing funnel:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleResume = async () => {
    setLoading(true)
    try {
      const response = await fetch(`http://localhost:8000/funnel/${funnel._id}/resume`, {
        method: 'POST'
      })
      if (response.ok) {
        onUpdate()
      }
    } catch (error) {
      console.error('Error resuming funnel:', error)
    } finally {
      setLoading(false)
    }
  }

  const statusColors = {
    draft: 'bg-gray-100 text-gray-800',
    active: 'bg-green-100 text-green-800',
    paused: 'bg-yellow-100 text-yellow-800'
  }

  return (
    <Card className="hover:shadow-lg transition-shadow">
      <CardHeader>
        <div className="flex justify-between items-start">
          <div>
            <CardTitle className="text-xl">{funnel.name}</CardTitle>
            <CardDescription className="mt-1">{funnel.productName}</CardDescription>
          </div>
          <span className={`px-3 py-1 rounded-full text-xs font-medium ${statusColors[funnel.status as keyof typeof statusColors]}`}>
            {funnel.status}
          </span>
        </div>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="overview" className="w-full">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="analytics">Analytics</TabsTrigger>
            <TabsTrigger value="actions">Actions</TabsTrigger>
          </TabsList>
          
          <TabsContent value="overview" className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="flex items-center space-x-2">
                <Users className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-sm text-muted-foreground">Leads</p>
                  <p className="text-2xl font-bold">{funnel.analytics.leads}</p>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                <DollarSign className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-sm text-muted-foreground">Revenue</p>
                  <p className="text-2xl font-bold">${funnel.analytics.revenue.toLocaleString()}</p>
                </div>
              </div>
            </div>
          </TabsContent>
          
          <TabsContent value="analytics" className="space-y-4">
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Visitors</span>
                <span className="font-semibold">{funnel.analytics.visitors.toLocaleString()}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Conversions</span>
                <span className="font-semibold">{funnel.analytics.conversions}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Conversion Rate</span>
                <span className="font-semibold">{funnel.analytics.conversionRate.toFixed(2)}%</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Avg Order Value</span>
                <span className="font-semibold">
                  ${funnel.analytics.conversions > 0 
                    ? (funnel.analytics.revenue / funnel.analytics.conversions).toFixed(2)
                    : '0.00'}
                </span>
              </div>
            </div>
          </TabsContent>
          
          <TabsContent value="actions" className="space-y-3">
            {funnel.status === 'draft' ? (
              <Button 
                onClick={handleLaunch} 
                disabled={loading}
                className="w-full"
                size="lg"
              >
                <Play className="mr-2 h-4 w-4" />
                Launch Funnel
              </Button>
            ) : funnel.status === 'active' ? (
              <Button 
                onClick={handlePause} 
                disabled={loading}
                variant="outline"
                className="w-full"
              >
                <Pause className="mr-2 h-4 w-4" />
                Pause Funnel
              </Button>
            ) : (
              <Button 
                onClick={handleResume} 
                disabled={loading}
                className="w-full"
              >
                <Play className="mr-2 h-4 w-4" />
                Resume Funnel
              </Button>
            )}
            
            <Button 
              variant="outline" 
              className="w-full"
              onClick={() => window.open(`/analytics/${funnel._id}`, '_blank')}
            >
              <BarChart3 className="mr-2 h-4 w-4" />
              View Analytics
            </Button>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}
