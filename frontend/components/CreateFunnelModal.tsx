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

interface CreateFunnelModalProps {
  onClose: () => void
  onSuccess: () => void
}

export function CreateFunnelModal({ onClose, onSuccess }: CreateFunnelModalProps) {
  const [loading, setLoading] = useState(false)
  const [formData, setFormData] = useState({
    name: '',
    gumroad_product_id: '',
    target_audience_description: '',
    goals: 'increase_sales'
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)

    try {
      const response = await fetch('http://localhost:8000/funnel/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: formData.name,
          gumroad_product_id: formData.gumroad_product_id,
          target_audience: {
            description: formData.target_audience_description
          },
          goals: [formData.goals],
          auto_launch: true
        })
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
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Create Autonomous Funnel</DialogTitle>
          <DialogDescription>
            Set up a fully autonomous traffic funnel for your Gumroad product
          </DialogDescription>
        </DialogHeader>
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
      </DialogContent>
    </Dialog>
  )
}
