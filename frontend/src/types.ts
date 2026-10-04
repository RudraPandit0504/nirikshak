export type Lang = 'en' | 'hi'

export type Category =
  | 'guaranteed_returns'
  | 'stock_tip'
  | 'price_prediction'
  | 'urgency_fomo'
  | 'paid_promotion'
  | 'paid_group'
  | 'registration_claim'
  | 'misleading_claim'

export interface CategoryInfo {
  en: string
  hi: string
  about_en: string
  about_hi: string
}

export interface Meta {
  model: string
  stages: string[]
  categories: Record<Category, CategoryInfo>
  registry_size: number
}

export interface Segment {
  start: number
  end: number
  text: string
}

export interface Claim {
  start: number
  end: number
  quote: string
  category: Category
  severity: 1 | 2 | 3
  confidence: number
  why_en: string
  why_hi: string
  origin: 'llm' | 'rules' | 'llm+rules'
  where: 'transcript' | 'description'
}

export interface RegistryHit {
  reg_no: string
  name: string
  category: string
  validity: string
  score: number
  how?: 'number' | 'near_number' | 'name' | 'contact_person' | 'domain' | ''
}

export interface IdentityCheck {
  query: string
  kind: 'number' | 'name' | 'domain'
  role: 'channel' | 'owner' | 'speaker' | 'guest' | 'company' | 'website' | 'number'
  source: 'channel' | 'title' | 'description' | 'transcript'
  hits: RegistryHit[]
}

export type Verdict =
  | 'verified'
  | 'matched'
  | 'registered_other'
  | 'guests_registered'
  | 'number_not_found'
  | 'claimed_unverified'
  | 'possible_match'
  | 'not_registered'
  | 'unknown'

export interface RegistryCheck {
  claims_registration: boolean
  numbers_found: string[]
  number_results: Record<string, RegistryHit | null>
  name_matches: RegistryHit[]
  disclaimer_found: boolean
  disclaimer_quotes: string[]
  verdict: Verdict
  checks?: IdentityCheck[]
  entity?: RegistryHit | null
}

export interface Concern {
  start: number
  where: 'transcript' | 'description'
  category: Category
  severity: 1 | 2 | 3
  quote: string
  why: string
}

export interface Summary {
  headline: string
  overview: string
  concerns: Concern[]
  registration: string
  advice: string[]
}

export interface Report {
  id: string
  created_at: string
  source: {
    kind: 'youtube' | 'upload'
    url: string | null
    video_id: string | null
    title: string
    channel: string
    description: string
    duration: number
    language: string | null
    transcript_source: 'captions' | 'whisper' | null
  }
  segments: Segment[]
  claims: Claim[]
  registry: RegistryCheck
  risk_score: number
  risk_level: 'low' | 'medium' | 'high'
  summary_en: string
  summary_hi: string
  summary?: Record<Lang, Summary> | null
  model: string
  timings: Record<string, number>
}

export interface ReportListItem {
  id: string
  title: string
  channel: string
  video_id: string | null
  risk_score: number
  risk_level: 'low' | 'medium' | 'high'
  created_at: string
}

export type JobEvent =
  | { type: 'queued'; position: number }
  | { type: 'progress'; stage: string; frac: number; msg: string; msg_hi?: string }
  | { type: 'done'; id: string }
  | { type: 'error'; msg: string }

export interface AskAnswer {
  answer: string
  answer_en: string
  kind: 'video' | 'general' | 'refused'
  citations: { line: number; start: number; quote: string }[]
}
