import type { AskAnswer, JobEvent, Meta, Profile, ProfileListItem, Report, ReportListItem } from './types'

async function json<T>(r: Response): Promise<T> {
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`
    try {
      const body = await r.json()
      if (body?.detail) msg = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* not JSON */
    }
    throw new Error(msg)
  }
  return r.json() as Promise<T>
}

export const getMeta = () => fetch('/api/meta').then((r) => json<Meta>(r))
export const getReport = (id: string) => fetch(`/api/reports/${id}`).then((r) => json<Report>(r))
export const listReports = () => fetch('/api/reports').then((r) => json<ReportListItem[]>(r))

export function startUrl(url: string) {
  const body = new FormData()
  body.set('url', url)
  return fetch('/api/audit', { method: 'POST', body }).then((r) => json<{ job: string }>(r))
}

export function startUpload(file: File) {
  const body = new FormData()
  body.set('file', file)
  return fetch('/api/audit/upload', { method: 'POST', body }).then((r) => json<{ job: string }>(r))
}

export function watchJob(job: string, onEvent: (e: JobEvent) => void): () => void {
  const es = new EventSource(`/api/audit/${job}/events`)
  es.onmessage = (m) => {
    const ev = JSON.parse(m.data) as JobEvent
    onEvent(ev)
    if (ev.type === 'done' || ev.type === 'error') es.close()
  }
  es.onerror = () => {
    es.close()
    onEvent({ type: 'error', msg: 'Lost connection to the Nirikshak server.' })
  }
  return () => es.close()
}

export const fmtTime = (t: number) => {
  const h = Math.floor(t / 3600)
  const m = Math.floor((t % 3600) / 60)
  const s = Math.floor(t % 60)
  const mm = String(m).padStart(h ? 2 : 1, '0')
  return `${h ? `${h}:` : ''}${mm}:${String(s).padStart(2, '0')}`
}

/** Position of a finding: "3:54" in a video, "L3" in a message (lines are numbered from 1). */
export const fmtPos = (t: number, message: boolean, lineWord = 'L') => (message ? `${lineWord} ${Math.floor(t) + 1}` : fmtTime(t))

export function askReport(id: string, question: string, lang: string, history: { role: string; text: string }[]) {
  return fetch(`/api/reports/${id}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, lang, history }),
  }).then((r) => json<AskAnswer>(r))
}

export function transcribeAudio(blob: Blob) {
  const body = new FormData()
  body.set('file', blob, 'question.webm')
  return fetch('/api/transcribe', { method: 'POST', body }).then((r) => json<{ text: string; language: string }>(r))
}

export function checkMessage(text: string, image: File | null, save: boolean) {
  const body = new FormData()
  if (image) body.set('image', image)
  else body.set('text', text)
  body.set('save', String(save))
  return fetch('/api/check-message', { method: 'POST', body }).then((r) => json<{ job: string }>(r))
}

export const deleteReport = (id: string) => fetch(`/api/reports/${id}`, { method: 'DELETE' }).then((r) => json<{ deleted: string }>(r))

export function startProfile(url: string, n: number) {
  const body = new FormData()
  body.set('url', url)
  body.set('n', String(n))
  return fetch('/api/profile', { method: 'POST', body }).then((r) => json<{ job: string }>(r))
}
export const getProfile = (id: string) => fetch(`/api/profiles/${id}`).then((r) => json<Profile>(r))
export const listProfiles = () => fetch('/api/profiles').then((r) => json<ProfileListItem[]>(r))
export const isChannelUrl = (u: string) => /youtube\.com\/(@[\w.-]+|channel\/|c\/|user\/)/i.test(u) && !/[?&]v=|youtu\.be\//.test(u)
