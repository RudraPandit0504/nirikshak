import { useEffect, useRef, useState } from 'react'
import { ArrowRight, AudioLines, Clock, FileAudio, Languages, Link2, Loader2, Lock, ShieldCheck, Upload } from 'lucide-react'
import { listReports, startUpload, startUrl } from '../api'
import { go } from '../ui'
import { useLang } from '../i18n'
import type { ReportListItem } from '../types'
import { RiskPill } from '../components/Risk'
import Glass from '../components/ui/Glass'
import { Button } from '../components/ui/Button'

export default function Home() {
  const { t, lang } = useLang()
  const [url, setUrl] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [recent, setRecent] = useState<ReportListItem[] | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    listReports().then(setRecent).catch(() => setRecent([]))
  }, [])

  const run = async (start: () => Promise<{ job: string }>) => {
    setBusy(true)
    setErr('')
    try {
      const { job } = await start()
      go(`/job/${job}`)
    } catch (ex) {
      setErr((ex as Error).message)
      setBusy(false)
    }
  }

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (url.trim()) run(() => startUrl(url.trim()))
  }

  const features = [
    { icon: Clock, title: t.feat1Title, body: t.feat1Body, tint: '#ff9500' },
    { icon: ShieldCheck, title: t.feat2Title, body: t.feat2Body, tint: '#34c759' },
    { icon: Languages, title: t.feat3Title, body: t.feat3Body, tint: '#8b7cff' },
  ]

  return (
    <div className="mx-auto max-w-[1200px] px-4 sm:px-6">
      {/* Hero */}
      <section className="pt-14 pb-10 sm:pt-24 sm:pb-16 text-center">
        <p className="glass-pill mx-auto inline-flex h-8 items-center gap-2 px-3.5 text-xs font-medium text-ink-2">
          <span className="size-1.5 rounded-full bg-[linear-gradient(135deg,#ff9500,#c644fc)]" />
          {t.heroKicker}
        </p>
        <h1 className={`display mx-auto mt-6 max-w-4xl leading-[1.02] ${lang === 'hi' ? 'text-[clamp(2.4rem,6vw,4.6rem)]' : 'text-[clamp(2.6rem,7vw,5.4rem)]'}`}>
          {t.heroTitleA}
          <br />
          <span className="accent-gradient">{t.heroTitleB}</span>
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-[clamp(1rem,1.6vw,1.15rem)] leading-relaxed text-ink-2">{t.heroSub}</p>

        {/* Input capsule */}
        <form onSubmit={submit} className="glass-strong mx-auto mt-10 flex max-w-3xl items-center gap-2 rounded-full! p-2 pl-5">
          <Link2 className="size-5 shrink-0 text-ink-3" />
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder={t.urlPlaceholder}
            inputMode="url"
            aria-label={t.urlPlaceholder}
            className="min-w-0 flex-1 bg-transparent py-3 text-base text-ink outline-none placeholder:text-ink-3"
          />
          <Button variant="primary" size="lg" disabled={busy} className="shrink-0 px-6!">
            {busy ? <Loader2 className="size-5 animate-spin" /> : <ArrowRight className="size-5" />}
            <span className="hidden sm:inline">{t.audit}</span>
          </Button>
        </form>

        <div className="mt-5 flex flex-wrap items-center justify-center gap-3 text-sm text-ink-3">
          <span>{t.or}</span>
          <Button type="button" size="sm" onClick={() => fileRef.current?.click()} disabled={busy}>
            <Upload className="size-4" /> {t.upload}
          </Button>
          <span className="text-xs">{t.uploadHint}</span>
          <input ref={fileRef} type="file" accept="audio/*,video/*,.opus,.ogg,.m4a" className="hidden"
            onChange={(e) => e.target.files?.[0] && run(() => startUpload(e.target.files![0]))} />
        </div>

        {err && (
          <Glass tone="red" className="mx-auto mt-6 max-w-xl rounded-2xl! px-5 py-3 text-sm text-ink">{err}</Glass>
        )}

        <p className="mt-8 inline-flex items-center gap-2 text-xs text-ink-3">
          <Lock className="size-3.5" /> {t.privacy}
        </p>
      </section>

      {/* What it checks */}
      <section className="grid gap-4 sm:grid-cols-3">
        {features.map(({ icon: Icon, title, body, tint }) => (
          <Glass key={title} className="p-6">
            <span className="grid size-11 place-items-center rounded-2xl text-white"
              style={{ background: `linear-gradient(135deg, ${tint}, color-mix(in oklab, ${tint} 60%, #000))`, boxShadow: `inset 0 1px 0 rgba(255,255,255,.45), 0 8px 20px -10px ${tint}` }}>
              <Icon className="size-5" />
            </span>
            <h3 className="display mt-4 text-lg">{title}</h3>
            <p className="mt-1.5 text-sm leading-relaxed text-ink-2">{body}</p>
          </Glass>
        ))}
      </section>

      {/* Recent audits */}
      <section className="mt-16">
        <div className="mb-5 flex items-end justify-between">
          <h2 className="display text-2xl sm:text-3xl">{t.recent}</h2>
          {recent && recent.length > 0 && <span className="text-sm text-ink-3 tabular">{recent.length}</span>}
        </div>
        {recent === null ? (
          <Loader2 className="size-5 animate-spin text-ink-3" />
        ) : recent.length === 0 ? (
          <Glass className="p-8 text-center text-ink-2">{t.noRecent}</Glass>
        ) : (
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {recent.map((r) => (
              <a key={r.id} href={`#/report/${r.id}`} className="glass glass-hover group block overflow-hidden p-2">
                <div className="relative aspect-video overflow-hidden rounded-[20px] bg-[var(--glass-inset)]">
                  {r.video_id ? (
                    <img src={`https://i.ytimg.com/vi/${r.video_id}/mqdefault.jpg`} alt="" loading="lazy"
                      className="size-full object-cover transition-transform duration-700 ease-[var(--ease-out-soft)] group-hover:scale-[1.04]" />
                  ) : (
                    <div className="grid size-full place-items-center text-ink-3"><FileAudio className="size-10" /></div>
                  )}
                  <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-black/45 to-transparent" />
                  <div className="absolute left-2.5 top-2.5"><RiskPill level={r.risk_level} score={r.risk_score} /></div>
                </div>
                <div className="px-3 pb-3 pt-3.5">
                  <p className="line-clamp-2 font-semibold leading-snug text-ink">{r.title}</p>
                  <p className="mt-1.5 flex items-center gap-1.5 text-xs text-ink-3">
                    <AudioLines className="size-3.5" /> <span className="truncate">{r.channel}</span>
                    <span className="ml-auto shrink-0">{fmtDateShort(r.created_at, lang)}</span>
                  </p>
                </div>
              </a>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

function fmtDateShort(iso: string, lang: string) {
  try {
    return new Date(iso).toLocaleDateString(lang === 'hi' ? 'hi-IN' : 'en-IN', { day: 'numeric', month: 'short' })
  } catch {
    return ''
  }
}
