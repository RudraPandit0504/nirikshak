import type { Category } from './types'

export const go = (path: string) => {
  window.location.hash = path
}

// Apple system colours, so category dots match the glass UI in light and dark mode.
export const CAT_COLOR: Record<Category, string> = {
  guaranteed_returns: 'bg-[#ff3b30]',
  stock_tip: 'bg-[#ff2d55]',
  price_prediction: 'bg-[#ff9500]',
  urgency_fomo: 'bg-[#ffcc00]',
  paid_promotion: 'bg-[#af52de]',
  paid_group: 'bg-[#5856d6]',
  registration_claim: 'bg-[#32ade6]',
  misleading_claim: 'bg-[#ff6482]',
  credential_request: 'bg-[#bf1029]',
  suspicious_link: 'bg-[#a2845e]',
  upfront_payment: 'bg-[#ff6b00]',
  impersonation: 'bg-[#8e44ad]',
}

export const LEVEL_HEX: Record<'low' | 'medium' | 'high', string> = { low: '#34c759', medium: '#ff9f0a', high: '#ff3b30' }
