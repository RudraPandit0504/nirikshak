import { useEffect, useRef, useState } from 'react'
import { AlertTriangle, AudioLines, Check, FileText, Link2, Loader2, ScanText, ShieldCheck, Sparkles } from 'lucide-react'
import { watchJob } from '../api'
import { go } from '../ui'
import { useLang } from '../i18n'
import type { Strings } from '../i18n'
import Glass from '../components/ui/Glass'
import { LinkButton } from '../components/ui/Button'

const STAGES = ['fetch', 'transcribe', 'scan', 'analyse', 'registry', 'summary'] as const
type Stage = (typeof STAGES)[number]
const ICONS = { fetch: Link2, transcribe: AudioLines, scan: ScanText, analyse: Sparkles, registry: ShieldCheck, summary: FileText }

export default function Job({ id }: { id: string }) {
  const { t, lang } = useLang()
  const [stage, setStage] = useState<Stage | null>(null)
  const [frac, setFrac] = useState(0)
  const [msgs, setMsgs] = useState<Partial<Record<Stage, { en: string; hi: string }>>>({})
  const [queued, setQueued] = useState(false)
  const [error, setError] = useState('')
  const [multi, setMulti] = useState<{ video: number; videos: number; title?: string } | null>(null)
  const lastVideo = useRef(0)

  useEffect(
    () =>
      watchJob(id, (ev) => {
        if (ev.type === 'queued') setQueued(ev.position > 0)
        else if (ev.type === 'progress') {
          setQueued(false)
          setStage(ev.stage as Stage)
          setFrac(ev.frac)
          const msg = { en: ev.msg, hi: ev.msg_hi ?? ev.msg }
          if (ev.videos && (ev.video ?? 0) !== lastVideo.current) {
            lastVideo.current = ev.video ?? 0
            setMsgs({ [ev.stage]: msg }) // a new video starts: reset the stage list
          } else {
            setMsgs((m) => ({ ...m, [ev.stage]: msg }))
          }
          if (ev.videos) setMulti({ video: ev.video ?? 0, videos: ev.videos, title: ev.title })
        } else if (ev.type === 'done') go(ev.kind === 'profile' ? `/profile/${ev.id}` : `/report/${ev.id}`)
        else if (ev.type === 'error') setError(ev.msg)
      }),
    [id],
  )

  const current = stage ? STAGES.indexOf(stage) : -1
  const single = ((Math.max(current, 0) + (stage ? frac : 0)) / STAGES.length) * 100
  // For a creator profile, the ring shows progress across all videos.
  const overall = Math.round(multi && multi.videos ? ((Math.max(multi.video - 1, 0) + single / 100) / multi.videos) * 100 : single)
  const title = error ? t.failed : queued ? t.queued : t.working
  const r = 52
  const c = 2 * Math.PI * r

  return (
    <div className="mx-auto max-w-2xl px-4 pt-12 sm:pt-20">
      <Glass strong className="p-6 sm:p-10">
        <div className="flex flex-col items-center text-center">
          {/* Progress ring */}
          <div className="relative size-40">
            <div className="absolute -inset-2 rounded-full opacity-50"
              style={{ background: `radial-gradient(closest-side, ${error ? '#ff3b30' : '#ff7a3d'}, transparent)` }} />
            <svg viewBox="0 0 120 120" className="absolute inset-0 -rotate-90">
              <defs>
                <linearGradient id="ring" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stopColor="#ff9500" /><stop offset="60%" stopColor="#ff5e3a" /><stop offset="100%" stopColor="#c644fc" />
                </linearGradient>
              </defs>
              <circle cx="60" cy="60" r={r} fill="none" stroke="var(--hairline)" strokeWidth="8" />
              <circle cx="60" cy="60" r={r} fill="none" stroke={error ? '#ff3b30' : 'url(#ring)'} strokeWidth="8" strokeLinecap="round"
                strokeDasharray={`${(c * (error ? 100 : overall)) / 100} ${c}`}
                style={{ transition: 'stroke-dasharray .8s var(--ease-out-soft)' }} />
            </svg>
            <div className="absolute inset-0 grid place-items-center">
              {error ? <AlertTriangle className="size-10 text-[#ff3b30]" /> : (
                <span className="display tabular text-[2.75rem]">{overall}<span className="text-lg text-ink-3">%</span></span>
              )}
            </div>
          </div>
          <h1 className="display mt-6 text-2xl sm:text-3xl">{title}</h1>
          {multi && multi.video > 0 && (
            <p className="mt-2 inline-flex max-w-md items-center gap-2 rounded-full bg-[var(--glass-inset)] px-3 py-1 text-sm text-ink-2 shadow-[inset_0_0_0_1px_var(--hairline)]">
              <span className="font-semibold text-ink">{t.videoOf.replace('{i}', String(multi.video)).replace('{n}', String(multi.videos))}</span>
              {multi.title && <span className="truncate">· {multi.title}</span>}
            </p>
          )}
          {!error && stage && msgs[stage] && (
            <p className="mt-2 max-w-md truncate text-sm text-ink-2">{msgs[stage]![lang]}</p>
          )}
        </div>

        <ol className="mt-8 grid gap-2">
          {STAGES.map((s, i) => {
            const done = i < current || (i === current && frac >= 1)
            const active = i === current && !done
            const Icon = ICONS[s]
            return (
              <li key={s}
                className={`flex min-w-0 items-center gap-3.5 rounded-2xl px-3.5 py-3 transition-all duration-500 ${active ? 'glass-inset' : ''}`}>
                <span className={`grid size-9 shrink-0 place-items-center rounded-full transition-all duration-500 ${
                  done ? 'bg-[#34c759] text-white shadow-[0_4px_14px_-4px_#34c759]'
                    : active ? 'bg-[linear-gradient(135deg,#ff9500,#ff5e3a)] text-white shadow-[0_4px_14px_-4px_#ff5e3a]'
                      : 'bg-[var(--glass-inset)] text-ink-3'
                }`}>
                  {done ? <Check className="size-4" strokeWidth={3} /> : active && !error ? <Loader2 className="size-4 animate-spin" /> : <Icon className="size-4" />}
                </span>
                <div className="min-w-0 flex-1 text-left">
                  <p className={`font-semibold ${!done && !active ? 'text-ink-3' : 'text-ink'}`}>{t[`stage_${s}` as keyof Strings] as string}</p>
                  {msgs[s] && <p className="truncate text-[13px] text-ink-3">{msgs[s]![lang]}</p>}
                </div>
                {done && <span className="shrink-0 text-xs font-medium text-[#34c759]">{t.stepsDone}</span>}
              </li>
            )
          })}
        </ol>

        {error && (
          <Glass tone="red" className="mt-6 rounded-2xl! p-4">
            <p className="text-sm text-ink">{error}</p>
            <LinkButton href="#/" variant="primary" size="sm" className="mt-3">{t.tryAgain}</LinkButton>
          </Glass>
        )}
      </Glass>
    </div>
  )
}
