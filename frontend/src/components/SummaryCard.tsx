import { useEffect, useRef, useState, type ReactNode } from 'react'
import { AlertTriangle, BadgeCheck, CircleAlert, FileText, Loader2, Play, ShieldCheck, Square, Volume2 } from 'lucide-react'
import { fmtPos } from '../api'
import { useLang } from '../i18n'
import type { Category, Report } from '../types'
import { CAT_COLOR, LEVEL_HEX } from '../ui'
import { RiskGauge } from './Risk'
import Glass from './ui/Glass'
import { Button } from './ui/Button'

type AudioState = 'idle' | 'loading' | 'playing'

/** Plays the server-generated (Kokoro) reading of the summary; falls back to the
 *  browser's own voice only if the server can't produce audio. */
function useReadAloud(reportId: string, lang: 'en' | 'hi', fallbackText: string) {
  const [state, setState] = useState<AudioState>('idle')
  const audio = useRef<HTMLAudioElement | null>(null)

  const stop = () => {
    audio.current?.pause()
    audio.current = null
    window.speechSynthesis?.cancel()
    setState('idle')
  }

  useEffect(() => stop, [reportId, lang]) // stop when leaving the page or switching language

  const browserVoice = () => {
    const synth = window.speechSynthesis
    if (!synth) return setState('idle')
    const u = new SpeechSynthesisUtterance(fallbackText)
    u.lang = lang === 'hi' ? 'hi-IN' : 'en-IN'
    u.onend = () => setState('idle')
    synth.speak(u)
    setState('playing')
  }

  const toggle = () => {
    if (state !== 'idle') return stop()
    setState('loading')
    const a = new Audio(`/api/reports/${reportId}/speech?lang=${lang}`)
    audio.current = a
    a.onplaying = () => setState('playing')
    a.onended = () => setState('idle')
    a.onerror = () => {
      if (audio.current === a) browserVoice()
    }
    a.play().catch(() => {
      /* onerror handles real failures */
    })
  }

  return { state, toggle }
}

/** Top of the report: score orb, title, verdict headline, overview and actions. */
export function ReportHero({ report, meta, actions }: { report: Report; meta: ReactNode; actions: ReactNode }) {
  const { t, lang } = useLang()
  const s = report.summary?.[lang]
  const fallback = lang === 'hi' && report.summary_hi ? report.summary_hi : report.summary_en
  const { state, toggle } = useReadAloud(report.id, lang, fallback)
  const color = LEVEL_HEX[report.risk_level]

  return (
    <Glass strong className="overflow-hidden p-6 sm:p-8">
      <div aria-hidden className="pointer-events-none absolute -right-24 -top-24 size-72 rounded-full opacity-25" style={{ background: `radial-gradient(closest-side, ${color}, transparent)` }} />
      <div className="relative flex flex-col gap-7 md:flex-row md:items-center">
        <RiskGauge level={report.risk_level} score={report.risk_score} />
        <div className="min-w-0 flex-1">
          <div className="text-[13px] text-ink-3">{meta}</div>
          <h1 className="display mt-2 text-[clamp(1.5rem,3vw,2.25rem)] leading-tight text-ink">
            {report.source.kind === 'message' ? t.msgTitle : report.source.title}
          </h1>
          <p className="mt-4 text-lg font-semibold leading-snug" lang={lang} style={{ color: `color-mix(in oklab, ${color} 70%, var(--ink))` }}>
            {s?.headline ?? fallback}
          </p>
          {s && <p className="mt-2 max-w-3xl leading-relaxed text-ink-2" lang={lang}>{s.overview}</p>}
          <div className="mt-6 flex flex-wrap items-center gap-2 no-print">
            <Button variant="primary" onClick={toggle}>
              {state === 'loading' ? <Loader2 className="size-4 animate-spin" /> : state === 'playing' ? <Square className="size-4" /> : <Volume2 className="size-4" />}
              {state === 'loading' ? t.preparingAudio : state === 'playing' ? t.stop : t.listen}
            </Button>
            {actions}
          </div>
        </div>
      </div>
    </Glass>
  )
}

/** Below the hero: main concerns, registration status and what to do. */
export function ReportBrief({ report, catLabel, onSeek }: {
  report: Report
  catLabel: (c: Category) => string
  onSeek?: (t: number) => void
}) {
  const { t, lang } = useLang()
  const s = report.summary?.[lang]
  if (!s) return null

  return (
    <div className="grid gap-5 lg:grid-cols-[1.25fr_1fr]">
      <Glass className="p-6">
        <p className="eyebrow flex items-center gap-1.5"><CircleAlert className="size-3.5" /> {t.mainConcerns}</p>
        {s.concerns.length === 0 ? (
          <p className="mt-3 text-sm text-ink-2">{t.noFindings}</p>
        ) : (
          <ul className="mt-4 space-y-2">
            {s.concerns.map((c, i) => (
              <li key={i} className="glass-inset flex gap-3 p-3.5">
                {c.where === 'transcript' ? (
                  <button
                    onClick={() => onSeek?.(c.start)}
                    disabled={!onSeek}
                    className="no-print inline-flex h-7 shrink-0 items-center gap-1 rounded-full bg-[var(--ink)] px-2.5 font-mono text-xs font-medium text-[var(--bg)] transition active:scale-95"
                  >
                    {onSeek && <Play className="size-3" fill="currentColor" />}{fmtPos(c.start, report.source.kind === 'message', t.askLine)}
                  </button>
                ) : (
                  <span className="inline-flex h-7 shrink-0 items-center gap-1 rounded-full bg-[var(--glass-inset)] px-2.5 text-xs text-ink-2 shadow-[inset_0_0_0_1px_var(--hairline)]">
                    <FileText className="size-3" /> {t.inDescription}
                  </span>
                )}
                <div className="min-w-0">
                  <p className="flex items-center gap-1.5 text-sm font-semibold text-ink">
                    <span className={`size-2 rounded-full ${CAT_COLOR[c.category]}`} /> {catLabel(c.category)}
                  </p>
                  <p className="mt-0.5 text-sm leading-relaxed text-ink-2" lang={lang}>{c.why}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Glass>

      <div className="grid gap-5">
        <Glass className="p-6">
          <p className="eyebrow flex items-center gap-1.5"><ShieldCheck className="size-3.5" /> {t.registrationStatus}</p>
          <p className="mt-3 text-sm leading-relaxed text-ink-2" lang={lang}>{s.registration}</p>
        </Glass>
        <Glass className="p-6">
          <p className="eyebrow flex items-center gap-1.5">
            {report.risk_level === 'low' ? <BadgeCheck className="size-3.5" /> : <AlertTriangle className="size-3.5" />} {t.whatYouShouldDo}
          </p>
          <ul className="mt-3 space-y-2.5" lang={lang}>
            {s.advice.map((a, i) => (
              <li key={i} className="flex gap-2.5 text-sm leading-relaxed text-ink-2">
                <span className="mt-2 size-1.5 shrink-0 rounded-full bg-[linear-gradient(135deg,#ff9500,#ff5e3a)]" />
                {a}
              </li>
            ))}
          </ul>
        </Glass>
      </div>
    </div>
  )
}
