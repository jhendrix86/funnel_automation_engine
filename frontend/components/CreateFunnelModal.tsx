'use client'

import { useState } from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { API_BASE } from '@/lib/api'

interface CreateFunnelModalProps {
  onClose: () => void
  onSuccess: () => void
}

export function CreateFunnelModal({ onClose, onSuccess }: CreateFunnelModalProps) {
  const [loading, setLoading] = useState(false)
  const [mode, setMode] = useState<'existing' | 'new'>('existing')
  const [formData, setFormData] = useState({
    name: '',
    gumroad_product_id: '',
    target_audience_description: '',
    goals: 'increase_sales',
    // Product creation fields
    product_name: '',
    product_description: '',
    product_price: '',
    product_tags: ''
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)

    try {
      const payload: any = {
        name: formData.name,
        target_audience: {
          description: formData.target_audience_description
        },
        goals: [formData.goals],
        auto_launch: true
      }

      if (mode === 'new') {
        payload.create_product = true
        payload.product_name = formData.product_name
        payload.product_description = formData.product_description
        payload.product_price = parseFloat(formData.product_price)
        payload.product_tags = formData.product_tags.split(',').map(t => t.trim()).filter(t => t)
      } else {
        payload.gumroad_product_id = formData.gumroad_product_id
      }

      const response = await fetch(`${API_BASE}/funnel/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })

      if (response.ok) {
        onSuccess()
      } else {
        console.error('Failed to create funnel')
      }
    } catch (error) {
      console.error('Error creating funnel:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>Create Autonomous Funnel</DialogTitle>
          <DialogDescription>
            Set up a fully autonomous traffic funnel for your Gumroad product
          </DialogDescription>
        </DialogHeader>
        
        <Tabs value={mode} onValueChange={(v) => setMode(v as 'existing' | 'new')} className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="existing">Use Existing Product</TabsTrigger>
            <TabsTrigger value="new">Create New Product</TabsTrigger>
          </TabsList>
          
          <TabsContent value="existing">
            <form onSubmit={handleSubmit}>
              <div className="grid gap-4 py-4">
                <div className="grid gap-2">
                  <Label htmlFor="name">Funnel Name</Label>
                  <Input
                    id="name"
                    placeholder="My Product Funnel"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    required
                  />
                </div>
                
                <div className="grid gap-2">
                  <Label htmlFor="gumroad_product_id">Gumroad Product ID</Label>
                  <Input
                    id="gumroad_product_id"
                    placeholder="Your Gumroad product ID"
                    value={formData.gumroad_product_id}
                    onChange={(e) => setFormData({ ...formData, gumroad_product_id: e.target.value })}
                    required
                  />
                </div>
                
                <div className="grid gap-2">
                  <Label htmlFor="target_audience">Target Audience</Label>
                  <Input
                    id="target_audience"
                    placeholder="e.g., Developers, Entrepreneurs, Creators"
                    value={formData.target_audience_description}
                    onChange={(e) => setFormData({ ...formData, target_audience_description: e.target.value })}
                    required
                  />
                </div>
                
                <div className="grid gap-2">
                  <Label htmlFor="goals">Primary Goal</Label>
                  <select
                    id="goals"
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    value={formData.goals}
                    onChange={(e) => setFormData({ ...formData, goals: e.target.value })}
                  >
                    <option value="increase_sales">Increase Sales</option>
                    <option value="build_audience">Build Audience</option>
                    <option value="brand_awareness">Brand Awareness</option>
                    <option value="lead_generation">Lead Generation</option>
                  </select>
                </div>
              </div>
              
              <DialogFooter>
                <Button type="button" variant="outline" onClick={onClose}>
                  Cancel
                </Button>
                <Button type="submit" disabled={loading}>
                  {loading ? 'Creating...' : 'Create Funnel'}
                </Button>
              </DialogFooter>
            </form>
          </TabsContent>
          
          <TabsContent value="new">
            <form onSubmit={handleSubmit}>
              <div className="grid gap-4 py-4">
                <div className="grid gap-2">
                  <Label htmlFor="name">Funnel Name</Label>
                  <Input
                    id="name"
                    placeholder="My Product Funnel"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    required
                  />
                </div>
                
                <div className="grid gap-2">
                  <Label htmlFor="product_name">Product Name</Label>
                  <Input
                    id="product_name"
                    placeholder="Your product name"
                    value={formData.product_name}
                    onChange={(e) => setFormData({ ...formData, product_name: e.target.value })}
                    required
                  />
                </div>
                
                <div className="grid gap-2">
                  <Label htmlFor="product_description">Product Description</Label>
                  <Textarea
                    id="product_description"
                    placeholder="Describe your product..."
                    value={formData.product_description}
                    onChange={(e) => setFormData({ ...formData, product_description: e.target.value })}
                    required
                    rows={3}
                  />
                </div>
                
                <div className="grid gap-2">
                  <Label htmlFor="product_price">Price ($)</Label>
                  <Input
                    id="product_price"
                    type="number"
                    step="0.01"
                    placeholder="29.99"
                    value={formData.product_price}
                    onChange={(e) => setFormData({ ...formData, product_price: e.target.value })}
                    required
                  />
                </div>
                
                <div className="grid gap-2">
                  <Label htmlFor="product_tags">Tags (comma-separated)</Label>
                  <Input
                    id="product_tags"
                    placeholder="digital, course, tutorial"
                    value={formData.product_tags}
                    onChange={(e) => setFormData({ ...formData, product_tags: e.target.value })}
                  />
                </div>
                
                <div className="grid gap-2">
                  <Label htmlFor="target_audience">Target Audience</Label>
                  <Input
                    id="target_audience"
                    placeholder="e.g., Developers, Entrepreneurs, Creators"
                    value={formData.target_audience_description}
                    onChange={(e) => setFormData({ ...formData, target_audience_description: e.target.value })}
                    required
                  />
                </div>
                
                <div className="grid gap-2">
                  <Label htmlFor="goals">Primary Goal</Label>
                  <select
                    id="goals"
                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    value={formData.goals}
                    onChange={(e) => setFormData({ ...formData, goals: e.target.value })}
                  >
                    <option value="increase_sales">Increase Sales</option>
                    <option value="build_audience">Build Audience</option>
                    <option value="brand_awareness">Brand Awareness</option>
                    <option value="lead_generation">Lead Generation</option>
                  </select>
                </div>
              </div>
              
              <DialogFooter>
                <Button type="button" variant="outline" onClick={onClose}>
                  Cancel
                </Button>
                <Button type="submit" disabled={loading}>
                  {loading ? 'Creating...' : 'Create Product & Funnel'}
                </Button>
              </DialogFooter>
            </form>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  )
}
