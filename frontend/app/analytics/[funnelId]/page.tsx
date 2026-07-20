'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { ArrowLeft, BarChart3, Users, DollarSign, TrendingUp, Mail, Target } from 'lucide-react'

interface AnalyticsData {
  funnel: any
  analytics: any
  gumroad: {
    product: any
    total_sales: number
    total_revenue: number
  }
  traffic: {
    campaigns: number
    total_impressions: number
  }
  leads: {
    total: number
    avg_score: number
  }
  email: {
    campaigns: number
    total_sent: number
  }
}

export default function AnalyticsPage() {
  const params = useParams()
  const router = useRouter()
  const funnelId = params.funnelId as string
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchAnalytics()
  }, [funnelId])

  const fetchAnalytics = async () => {
    try {
      const response = await fetch(`http://localhost:8000/analytics/${funnelId}`)
      if (response.ok) {
        const data = await response.json()
        setAnalytics(data)
      }
    } catch (error) {
      console.error('Error fetching analytics:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-600">Loading analytics...</div>
      </div>
    )
  }

  if (!analytics) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-600">Failed to load analytics</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center mb-8">
          <Button 
            variant="ghost" 
            onClick={() => router.back()}
            className="mr-4"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back
          </Button>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Analytics Dashboard</h1>
            <p className="text-gray-600 mt-1">{analytics.funnel?.name || 'Funnel'}</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Revenue</CardTitle>
              <DollarSign className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">${analytics.gumroad.total_revenue.toLocaleString()}</div>
              <p className="text-xs text-muted-foreground mt-1">
                {analytics.gumroad.total_sales} sales
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Leads</CardTitle>
              <Users className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{analytics.leads.total}</div>
              <p className="text-xs text-muted-foreground mt-1">
                Avg score: {analytics.leads.avg_score.toFixed(2)}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Traffic</CardTitle>
              <Target className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{analytics.traffic.total_impressions.toLocaleString()}</div>
              <p className="text-xs text-muted-foreground mt-1">
                {analytics.traffic.campaigns} campaigns
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Emails Sent</CardTitle>
              <Mail className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{analytics.email.total_sent.toLocaleString()}</div>
              <p className="text-xs text-muted-foreground mt-1">
                {analytics.email.campaigns} campaigns
              </p>
            </CardContent>
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <BarChart3 className="mr-2 h-5 w-5" />
                Funnel Analytics
              </CardTitle>
              <CardDescription>Overall funnel performance metrics</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {analytics.analytics && Object.keys(analytics.analytics).length > 0 ? (
                Object.entries(analytics.analytics).map(([key, value]) => (
                  <div key={key} className="flex justify-between items-center">
                    <span className="text-sm text-muted-foreground capitalize">
                      {key.replace(/_/g, ' ')}
                    </span>
                    <span className="font-semibold">
                      {typeof value === 'number' ? value.toLocaleString() : String(value)}
                    </span>
                  </div>
                ))
              ) : (
                <p className="text-sm text-muted-foreground">No analytics data available</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <TrendingUp className="mr-2 h-5 w-5" />
                Conversion Metrics
              </CardTitle>
              <CardDescription>Conversion and performance data</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Conversion Rate</span>
                <span className="font-semibold">
                  {analytics.leads.total > 0 
                    ? ((analytics.gumroad.total_sales / analytics.leads.total) * 100).toFixed(2) + '%'
                    : '0%'}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Avg Order Value</span>
                <span className="font-semibold">
                  ${analytics.gumroad.total_sales > 0 
                    ? (analytics.gumroad.total_revenue / analytics.gumroad.total_sales).toFixed(2)
                    : '0.00'}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Cost per Lead</span>
                <span className="font-semibold">
                  ${analytics.traffic.total_impressions > 0 
                    ? (analytics.gumroad.total_revenue / analytics.leads.total).toFixed(2)
                    : '0.00'}
                </span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
