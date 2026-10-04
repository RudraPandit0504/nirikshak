import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, BadgeCheck, CircleAlert, FileText, Loader2, Play, ShieldCheck, Square, Volume2 } from 'lucide-react'
import { fmtTime } from '../api'
import { useLang } from '../i18n'
import type { Category, Report } from '../types'
import { CAT_COLOR } from '../ui'
import { RiskGauge } from './Risk'

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

export default function SummaryCard({ report, catLabel, onSeek }: {
  report: Report
  catLabel: (c: Category) => string
  onSeek?: (t: number) => void
}) {
  const { t, lang } = useLang()
  const s = report.summary?.[lang]
  const fallback = lang === 'hi' && report.summary_hi ? report.summary_hi : report.summary_en
  const { state, toggle } = useReadAloud(report.id, lang, fallback)
  const tone = { low: 'border-emerald-500', medium: 'border-amber-500', high: 'border-red-500' }[report.risk_level]

  return (
    <section className={`card border-l-4 ${tone}`}>
      <div className="flex flex-col sm:flex-row gap-5 sm:items-center">
        <RiskGauge level={report.risk_level} score={report.risk_score} />
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <p className="label">{t.summary}</p>
            <button
              onClick={toggle}
              className="no-print inline-flex shrink-0 items-center gap-1.5 rounded-full border border-amber-500/40 bg-amber-500/10 px-3 py-1 text-xs font-semibold text-amber-700 dark:text-amber-400 hover:bg-amber-500/20"
            >
              {state === 'loading' ? <Loader2 className="size-3.5 animate-spin" /> : state === 'playing' ? <Square className="size-3.5" /> : <Volume2 className="size-3.5" />}
              {state === 'loading' ? t.preparingAudio : state === 'playing' ? t.stop : t.listen}
            </button>
          </div>
          <h2 className="mt-2 text-lg sm:text-xl font-bold leading-snug" lang={lang}>{s?.headline ?? fallback}</h2>
          {s && <p className="mt-2 leading-relaxed text-slate-700 dark:text-slate-300" lang={lang}>{s.overview}</p>}
        </div>
      </div>

      {s && (
        <div className="mt-6 grid gap-6 md:grid-cols-2">
          <div>
            <p className="label flex items-center gap-1.5"><CircleAlert className="size-3.5" /> {t.mainConcerns}</p>
            {s.concerns.length === 0 ? (
              <p className="mt-2 text-sm text-slate-500">{t.noFindings}</p>
            ) : (
              <ul className="mt-3 space-y-3">
                {s.concerns.map((c, i) => (
                  <li key={i} className="flex gap-3 text-sm">
                    {c.where === 'transcript' ? (
                      <button
                        onClick={() => onSeek?.(c.start)}
                        disabled={!onSeek}
                        className="no-print h-6 shrink-0 inline-flex items-center gap-1 rounded-md bg-slate-900 px-1.5 font-mono text-xs text-white dark:bg-slate-100 dark:text-slate-900"
                      >
                        {onSeek && <Play className="size-3" />}{fmtTime(c.start)}
                      </button>
                    ) : (
                      <span className="h-6 shrink-0 inline-flex items-center gap-1 rounded-md bg-slate-200 dark:bg-slate-800 px-1.5 text-xs">
                        <FileText className="size-3" /> {t.inDescription}
                      </span>
                    )}
                    <div className="min-w-0">
                      <p className="font-semibold flex items-center gap-1.5">
                        <span className={`size-2 rounded-full ${CAT_COLOR[c.category]}`} /> {catLabel(c.category)}
                      </p>
                      <p className="text-slate-600 dark:text-slate-400" lang={lang}>{c.why}</p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="space-y-5">
            <div>
              <p className="label flex items-center gap-1.5"><ShieldCheck className="size-3.5" /> {t.registrationStatus}</p>
              <p className="mt-2 text-sm text-slate-700 dark:text-slate-300" lang={lang}>{s.registration}</p>
            </div>
            <div>
              <p className="label flex items-center gap-1.5">
                {report.risk_level === 'low' ? <BadgeCheck className="size-3.5" /> : <AlertTriangle className="size-3.5" />} {t.whatYouShouldDo}
              </p>
              <ul className="mt-2 space-y-2 text-sm text-slate-700 dark:text-slate-300 list-disc pl-4" lang={lang}>
                {s.advice.map((a, i) => <li key={i}>{a}</li>)}
              </ul>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
