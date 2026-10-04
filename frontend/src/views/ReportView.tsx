import { useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertTriangle, BadgeCheck, BadgeX, Download, ExternalLink, FileText, Loader2, Play, Plus, Printer,
  ShieldQuestion,
} from 'lucide-react'
import { fmtTime, getReport } from '../api'
import { useLang } from '../i18n'
import type { Category, Claim, Meta, Report } from '../types'
import PrintReport from '../components/PrintReport'
import SummaryCard from '../components/SummaryCard'
import { CAT_COLOR } from '../ui'

const SEBI_RA = 'https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRecognisedFpi=yes&intmId=14'

export default function ReportView({ id, meta }: { id: string; meta: Meta | null }) {
  const { t, lang } = useLang()
  const [report, setReport] = useState<Report | null>(null)
  const [err, setErr] = useState('')
  const [showWeak, setShowWeak] = useState(false)
  const [filter, setFilter] = useState<Category | 'all'>('all')
  const [tab, setTab] = useState<'findings' | 'transcript'>('findings')
  const [active, setActive] = useState<number | null>(null)
  // Lite embed: show the thumbnail until the user plays or seeks, then load the real player.
  const [playFrom, setPlayFrom] = useState<number | null>(null)
  const iframe = useRef<HTMLIFrameElement>(null)
  const playerBox = useRef<HTMLDivElement>(null)

  useEffect(() => {
    getReport(id).then(setReport).catch((e) => setErr(e.message))
  }, [id])

  const visible = useMemo(
    () => (report?.claims ?? []).filter((c) => (showWeak || c.confidence >= 0.5) && (filter === 'all' || c.category === filter)),
    [report, showWeak, filter],
  )
  const counts = useMemo(() => {
    const m = new Map<Category, number>()
    for (const c of report?.claims ?? []) if (showWeak || c.confidence >= 0.5) m.set(c.category, (m.get(c.category) ?? 0) + 1)
    return m
  }, [report, showWeak])

  if (err) return <p className="p-10 text-center text-red-500">{err}</p>
  if (!report) return <Loader2 className="mx-auto mt-20 size-8 animate-spin text-slate-400" />

  const { source } = report
  const cat = (c: Category) => meta?.categories[c]?.[lang] ?? c
  const seek = (s: number) => {
    if (playFrom === null) {
      setPlayFrom(Math.floor(s))
    } else {
      iframe.current?.contentWindow?.postMessage(JSON.stringify({ event: 'command', func: 'seekTo', args: [s, true] }), '*')
      iframe.current?.contentWindow?.postMessage(JSON.stringify({ event: 'command', func: 'playVideo', args: [] }), '*')
    }
    playerBox.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
  const printReport = () => {
    // The browser uses the page title as the default PDF file name.
    const prev = document.title
    document.title = `Nirikshak audit - ${source.title}`.replace(/[\\/:*?"<>|]+/g, ' ').slice(0, 120)
    window.addEventListener('afterprint', () => (document.title = prev), { once: true })
    window.print()
  }

  const exportJson = () => {
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `nirikshak-${report.id}.json`
    a.click()
    URL.revokeObjectURL(a.href)
  }

  const flagged = new Set(report.claims.filter((c) => c.where === 'transcript' && (showWeak || c.confidence >= 0.5)).map((c) => c.start))
  const totalTime = Object.values(report.timings).reduce((a, b) => a + b, 0)

  return (
    <>
    <PrintReport report={report} catLabel={cat} />
    <div className="mx-auto max-w-7xl px-4 py-6 print:hidden">
      {/* Title row */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-xl sm:text-2xl font-bold leading-snug">{source.title}</h1>
          <p className="mt-1 text-sm text-slate-500">
            {source.channel && <span className="font-medium text-slate-700 dark:text-slate-300">{source.channel}</span>}
            {source.duration > 0 && <> · {fmtTime(source.duration)}</>}
            {' · '}
            {source.transcript_source === 'whisper' ? t.whisper : t.captions}
            {source.language && <> ({t.langNames[source.language] ?? source.language})</>}
          </p>
        </div>
        <div className="no-print flex gap-2">
          <a href="#/" className="btn" title={t.newAudit}><Plus className="size-4" /> <span className="hidden sm:inline">{t.newAudit}</span></a>
          <button onClick={exportJson} className="btn" title={t.exportJson}><Download className="size-4" /> <span className="hidden sm:inline">{t.exportJson}</span></button>
          <button onClick={printReport} className="btn" title={t.downloadPdf}><Printer className="size-4" /> <span className="hidden sm:inline">{t.downloadPdf}</span></button>
        </div>
      </div>

      <div className="mt-6">
        <SummaryCard report={report} catLabel={cat} onSeek={source.video_id ? seek : undefined} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        {/* Left column */}
        <div className="min-w-0 space-y-6">
          {source.video_id ? (
            <div ref={playerBox} className="relative overflow-hidden rounded-2xl bg-black shadow-lg aspect-video no-print">
              {playFrom === null ? (
                <button onClick={() => setPlayFrom(0)} className="group absolute inset-0" aria-label="Play video">
                  <img src={`https://i.ytimg.com/vi/${source.video_id}/hqdefault.jpg`} alt="" className="size-full object-cover opacity-90 group-hover:opacity-100" />
                  <span className="absolute inset-0 grid place-items-center">
                    <span className="grid size-16 place-items-center rounded-full bg-black/70 text-white group-hover:bg-red-600 transition">
                      <Play className="size-7 translate-x-0.5" fill="currentColor" />
                    </span>
                  </span>
                </button>
              ) : (
                <iframe
                  ref={iframe}
                  className="size-full"
                  src={`https://www.youtube-nocookie.com/embed/${source.video_id}?enablejsapi=1&rel=0&autoplay=1&start=${playFrom}`}
                  title={source.title}
                  allow="autoplay; encrypted-media; picture-in-picture"
                  allowFullScreen
                />
              )}
            </div>
          ) : null}

          {/* Timeline */}
          {source.duration > 0 && (
            <div className="card">
              <p className="label">{t.timeline}</p>
              <div className="relative mt-3 h-10 rounded-lg bg-slate-100 dark:bg-slate-800">
                {report.claims
                  .filter((c) => c.where === 'transcript' && (showWeak || c.confidence >= 0.5))
                  .map((c, i) => (
                    <button
                      key={i}
                      title={`${fmtTime(c.start)} · ${cat(c.category)}`}
                      onClick={() => { seek(c.start); setActive(report.claims.indexOf(c)) }}
                      className={`absolute top-1 bottom-1 w-1.5 -ml-0.75 rounded-full ${CAT_COLOR[c.category]} hover:scale-y-110 hover:w-2.5 transition-all`}
                      style={{ left: `${(c.start / source.duration) * 100}%`, opacity: 0.35 + c.confidence * 0.65 }}
                    />
                  ))}
              </div>
              <div className="mt-1 flex justify-between text-xs text-slate-400 font-mono">
                <span>0:00</span>
                <span>{fmtTime(source.duration / 2)}</span>
                <span>{fmtTime(source.duration)}</span>
              </div>
            </div>
          )}

          {/* Tabs */}
          <div className="card p-0! overflow-hidden">
            <div className="flex items-center justify-between gap-2 border-b border-slate-200 dark:border-slate-800 px-4">
              <div className="flex">
                {(['findings', 'transcript'] as const).map((k) => (
                  <button
                    key={k}
                    onClick={() => setTab(k)}
                    className={`px-3 py-3 text-sm font-semibold border-b-2 -mb-px ${
                      tab === k ? 'border-amber-400 text-slate-900 dark:text-white' : 'border-transparent text-slate-500'
                    }`}
                  >
                    {k === 'findings' ? `${t.findings} (${visible.length})` : t.transcript}
                  </button>
                ))}
              </div>
              <label className="flex items-center gap-2 text-xs text-slate-500 cursor-pointer select-none">
                <input type="checkbox" checked={showWeak} onChange={(e) => setShowWeak(e.target.checked)} className="accent-amber-500" />
                {t.showWeak}
              </label>
            </div>

            {tab === 'findings' ? (
              <div className="p-4">
                <div className="flex flex-wrap gap-1.5 mb-4">
                  <Chip on={filter === 'all'} onClick={() => setFilter('all')}>{t.all}</Chip>
                  {[...counts.entries()].map(([c, n]) => (
                    <Chip key={c} on={filter === c} onClick={() => setFilter(c)}>
                      <span className={`size-2 rounded-full ${CAT_COLOR[c]}`} /> {cat(c)} <span className="text-slate-400">{n}</span>
                    </Chip>
                  ))}
                </div>
                {visible.length === 0 ? (
                  <p className="py-8 text-center text-slate-500">{t.noFindings}</p>
                ) : (
                  <ul className="space-y-3">
                    {visible.map((c) => {
                      const idx = report.claims.indexOf(c)
                      return (
                        <ClaimCard key={idx} c={c} label={cat(c.category)} active={active === idx}
                          onSeek={source.video_id && c.where === 'transcript' ? () => { seek(c.start); setActive(idx) } : undefined} />
                      )
                    })}
                  </ul>
                )}
              </div>
            ) : (
              <div className="max-h-[560px] overflow-y-auto p-2 text-sm leading-relaxed">
                {report.segments.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => source.video_id && seek(s.start)}
                    className={`flex w-full gap-3 rounded-md px-2 py-1 text-left hover:bg-slate-100 dark:hover:bg-slate-800 ${
                      flagged.has(s.start) ? 'bg-red-500/10 ring-1 ring-red-500/30' : ''
                    }`}
                  >
                    <span className="shrink-0 font-mono text-xs text-slate-400 pt-0.5 w-12">{fmtTime(s.start)}</span>
                    <span>{s.text}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right column */}
        <aside className="space-y-6 order-first lg:order-none">
          <RegistryCard report={report} />

          <div className="card">
            <p className="label">{t.verifyReport}</p>
            <ul className="mt-3 space-y-2 text-sm text-slate-600 dark:text-slate-300 list-disc pl-4">
              <li>{t.todo2}</li>
              <li>{t.todo3}</li>
            </ul>
            <div className="mt-3 flex flex-wrap gap-2 text-xs no-print">
              <a className="link" href={SEBI_RA} target="_blank" rel="noreferrer">{t.sebiList} <ExternalLink className="size-3" /></a>
              <a className="link" href="https://cybercrime.gov.in" target="_blank" rel="noreferrer">cybercrime.gov.in <ExternalLink className="size-3" /></a>
              <a className="link" href="https://scores.sebi.gov.in" target="_blank" rel="noreferrer">SEBI SCORES <ExternalLink className="size-3" /></a>
            </div>
          </div>

          <p className="text-xs text-slate-400">
            {t.analysedWith} <span className="font-mono">{report.model}</span> · {t.took} {Math.round(totalTime)}{t.seconds}
          </p>
        </aside>
      </div>
    </div>
    </>
  )
}

function Chip({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition ${
        on ? 'border-slate-900 bg-slate-900 text-white dark:border-white dark:bg-white dark:text-slate-900' : 'border-slate-200 dark:border-slate-700 hover:border-slate-400'
      }`}
    >
      {children}
    </button>
  )
}

function ClaimCard({ c, label, active, onSeek }: { c: Claim; label: string; active: boolean; onSeek?: () => void }) {
  const { t, lang } = useLang()
  const why = lang === 'hi' && c.why_hi ? c.why_hi : c.why_en
  return (
    <li className={`rounded-xl border p-4 transition ${active ? 'border-amber-400 ring-2 ring-amber-400/30' : 'border-slate-200 dark:border-slate-800'}`}>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        {c.where === 'transcript' ? (
          <button
            onClick={onSeek}
            disabled={!onSeek}
            className="inline-flex items-center gap-1 rounded-md bg-slate-900 px-2 py-1 font-mono font-medium text-white dark:bg-slate-100 dark:text-slate-900 disabled:opacity-70"
          >
            {onSeek && <Play className="size-3" />} {fmtTime(c.start)}
          </button>
        ) : (
          <span className="inline-flex items-center gap-1 rounded-md bg-slate-200 dark:bg-slate-800 px-2 py-1 font-medium">
            <FileText className="size-3" /> {t.description}
          </span>
        )}
        <span className="inline-flex items-center gap-1.5 font-semibold">
          <span className={`size-2 rounded-full ${CAT_COLOR[c.category]}`} /> {label}
        </span>
        <span className={`rounded px-1.5 py-0.5 font-medium ${c.severity === 3 ? 'bg-red-500/15 text-red-600 dark:text-red-400' : c.severity === 2 ? 'bg-amber-500/15 text-amber-700 dark:text-amber-400' : 'bg-slate-500/15 text-slate-500'}`}>
          {t.severity[c.severity]}
        </span>
        <span className="ml-auto inline-flex items-center gap-2 text-slate-400">
          <span className="rounded border border-slate-200 dark:border-slate-700 px-1.5 py-0.5">{t[`origin_${c.origin}`]}</span>
          <span className="inline-flex items-center gap-1" title={t.confidence}>
            <span className="h-1.5 w-12 rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden">
              <span className="block h-full bg-slate-500" style={{ width: `${c.confidence * 100}%` }} />
            </span>
            {Math.round(c.confidence * 100)}%
          </span>
        </span>
      </div>
      <blockquote className="mt-3 border-l-4 border-amber-400 pl-3 text-[15px] font-medium leading-relaxed">“{c.quote}”</blockquote>
      <p className="mt-2 text-sm text-slate-600 dark:text-slate-400 leading-relaxed" lang={lang}>{why}</p>
    </li>
  )
}

function RegistryCard({ report }: { report: Report }) {
  const { t } = useLang()
  const r = report.registry
  const good = r.verdict === 'verified' || r.verdict === 'matched' || r.verdict === 'guests_registered'
  const bad = ['number_not_found', 'not_registered', 'claimed_unverified', 'registered_other'].includes(r.verdict)
  const Icon = good ? BadgeCheck : bad ? BadgeX : ShieldQuestion
  const typo = Object.values(r.number_results).some((h) => h && h.score < 100)
  const checks = r.checks ?? []
  return (
    <div className="card">
      <p className="label">{t.registry}</p>
      <div className={`mt-3 flex items-start gap-3 rounded-xl p-3 ${good ? 'bg-emerald-500/10' : bad ? 'bg-red-500/10' : 'bg-amber-500/10'}`}>
        <Icon className={`size-6 shrink-0 ${good ? 'text-emerald-600' : bad ? 'text-red-600' : 'text-amber-600'}`} />
        <div className="min-w-0">
          <p className="font-semibold">{r.verdict === 'verified' && typo ? t.verifiedTypo : t.verdict[r.verdict]}</p>
          {r.entity && (
            <p className="mt-1 text-sm font-medium">
              {r.entity.name} · {t.catNames[r.entity.category] ?? r.entity.category}{' '}
              <span className="font-mono text-xs text-slate-500">{r.entity.reg_no}</span>
            </p>
          )}
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">{t.verdictHelp[r.verdict]}</p>
        </div>
      </div>

      {checks.length > 0 ? (
        <div className="mt-4">
          <p className="text-xs font-semibold text-slate-500">{t.checked}</p>
          <ul className="mt-2 space-y-2 text-sm">
            {checks.map((c, i) => {
              const h = c.hits[0]
              return (
                <li key={i} className="flex gap-2">
                  {h ? <BadgeCheck className="mt-0.5 size-4 shrink-0 text-emerald-600" /> : <BadgeX className="mt-0.5 size-4 shrink-0 text-slate-400" />}
                  <div className="min-w-0">
                    <p className="truncate">
                      <span className={c.kind === 'name' ? 'font-medium' : 'font-mono text-xs'}>{c.query}</span>
                      <span className="text-xs text-slate-500"> · {t.roles[c.role] ?? c.role}</span>
                    </p>
                    <p className="text-xs text-slate-500 truncate">
                      {h ? (
                        <>
                          {h.how === 'near_number' && <span className="text-amber-600">{t.typoMatch} </span>}
                          {h.name} · {t.catNames[h.category] ?? h.category} <span className="font-mono">{h.reg_no}</span>
                        </>
                      ) : t.notInRegister}
                    </p>
                  </div>
                </li>
              )
            })}
          </ul>
        </div>
      ) : (
        r.numbers_found.length > 0 && (
          <div className="mt-4">
            <p className="text-xs font-semibold text-slate-500">{t.numbersQuoted}</p>
            <ul className="mt-1 space-y-1 text-sm">
              {r.numbers_found.map((n) => {
                const hit = r.number_results[n]
                return (
                  <li key={n} className="flex flex-wrap items-center gap-x-2">
                    {hit ? <BadgeCheck className="size-4 text-emerald-600" /> : <BadgeX className="size-4 text-red-600" />}
                    <span className="font-mono">{n}</span>
                    {hit && <span className="truncate text-slate-500">· {hit.name}</span>}
                  </li>
                )
              })}
            </ul>
          </div>
        )
      )}

      <div className="mt-4 flex items-center justify-between text-sm">
        <span className="text-slate-500">{t.disclaimer}</span>
        <span className={`inline-flex items-center gap-1 font-semibold ${r.disclaimer_found ? 'text-emerald-600' : 'text-amber-600'}`}>
          {r.disclaimer_found ? <BadgeCheck className="size-4" /> : <AlertTriangle className="size-4" />}
          {r.disclaimer_found ? t.disclaimerYes : t.disclaimerNo}
        </span>
      </div>
      <a className="link mt-3 no-print" href={SEBI_RA} target="_blank" rel="noreferrer">
        {t.verifyOn} <ExternalLink className="size-3" />
      </a>
    </div>
  )
}
