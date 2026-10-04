import type { Category } from './types'

export const go = (path: string) => {
  window.location.hash = path
}

export const CAT_COLOR: Record<Category, string> = {
  guaranteed_returns: 'bg-red-500',
  stock_tip: 'bg-rose-500',
  price_prediction: 'bg-orange-500',
  urgency_fomo: 'bg-amber-500',
  paid_promotion: 'bg-violet-500',
  paid_group: 'bg-fuchsia-500',
  registration_claim: 'bg-sky-500',
  misleading_claim: 'bg-pink-500',
}
