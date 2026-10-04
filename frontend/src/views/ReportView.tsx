import { useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertTriangle, ArrowLeft, BadgeCheck, BadgeX, Braces, ExternalLink, FileText, Loader2, Play, Plus, Printer, Trash2,
  ShieldQuestion,
} from 'lucide-react'
import { deleteReport, fmtPos, fmtTime, getReport } from '../api'
import { useLang } from '../i18n'
import type { Category, Claim, Meta, Report } from '../types'
import AskPanel from '../components/AskPanel'
import PrintReport from '../components/PrintReport'
import { ReportBrief, ReportHero } from '../components/SummaryCard'
import Glass from '../components/ui/Glass'
import { Button, LinkButton } from '../components/ui/Button'
import Chip from '../components/ui/Chip'
import Segmented from '../components/ui/Segmented'
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

  if (err) return <Glass className="mx-auto mt-16 max-w-md p-8 text-center text-ink">{err}</Glass>
  if (!report) return <Loader2 className="mx-auto mt-24 size-8 animate-spin text-ink-3" />

  const { source } = report
  const isMessage = source.kind === 'message'
  const pos = (t0: number) => fmtPos(t0, isMessage, t.askLine)
  const remove = async () => {
    await deleteReport(report.id)
    window.location.hash = '/'
  }
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
  const metaLine = isMessage ? (
    <>
      <span className="font-semibold text-ink-2">{t.msgReceived}</span> · {report.segments.length} {t.lines}
      {' · '}<span className="font-mono">{new Date(report.created_at).toLocaleString(lang === 'hi' ? 'hi-IN' : 'en-IN', { dateStyle: 'medium', timeStyle: 'short' })}</span>
    </>
  ) : (
    <>
      {source.channel && <span className="font-semibold text-ink-2">{source.channel}</span>}
      {source.duration > 0 && <> · <span className="font-mono">{fmtTime(source.duration)}</span></>}
      {' · '}{source.transcript_source === 'whisper' ? t.whisper : t.captions}
      {source.language && <> ({t.langNames[source.language] ?? source.language})</>}
    </>
  )

  return (
    <>
      <PrintReport report={report} catLabel={cat} />
      <div className="mx-auto max-w-[1200px] px-4 pt-6 sm:px-6 sm:pt-8 print:hidden">
        <a href="#/" className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-ink-3 transition hover:text-ink">
          <ArrowLeft className="size-4" /> {t.backHome}
        </a>

        <ReportHero
          report={report}
          meta={metaLine}
          actions={
            <>
              <Button onClick={printReport}><Printer className="size-4" /> {t.downloadPdf}</Button>
              <Button onClick={exportJson} variant="ghost"><Braces className="size-4" /> JSON</Button>
              <LinkButton href="#/" variant="ghost"><Plus className="size-4" /> {t.newAudit}</LinkButton>
              {isMessage && <Button variant="ghost" onClick={remove}><Trash2 className="size-4" /> {t.msgDelete}</Button>}
            </>
          }
        />

        <div className="mt-5">
          <ReportBrief report={report} catLabel={cat} onSeek={source.video_id ? seek : undefined} />
        </div>

        <div className="mt-5">
          <AskPanel reportId={report.id} isMessage={isMessage} onSeek={source.video_id ? seek : undefined} />
        </div>

        <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_380px]">
          {/* Main column */}
          <div className="min-w-0 space-y-5">
            {source.video_id && (
              <Glass className="p-2">
                <div ref={playerBox} className="relative aspect-video overflow-hidden rounded-[22px] bg-black">
                  {playFrom === null ? (
                    <button onClick={() => setPlayFrom(0)} className="group absolute inset-0" aria-label="Play video">
                      <img src={`https://i.ytimg.com/vi/${source.video_id}/hqdefault.jpg`} alt="" className="size-full object-cover opacity-90 transition duration-700 group-hover:scale-[1.02] group-hover:opacity-100" />
                      <span className="absolute inset-0 grid place-items-center">
                        <span className="glass-pill grid size-20 place-items-center text-white transition duration-500 ease-[var(--ease-spring)] group-hover:scale-110"
                          style={{ background: 'rgba(255,255,255,.18)' }}>
                          <Play className="size-8 translate-x-0.5" fill="currentColor" />
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
              </Glass>
            )}

            {source.duration > 0 && (
              <Glass className="p-6">
                <p className="eyebrow">{t.timeline}</p>
                <div className="glass-inset relative mt-4 h-12 rounded-full!">
                  {report.claims
                    .filter((c) => c.where === 'transcript' && (showWeak || c.confidence >= 0.5))
                    .map((c, i) => (
                      <button
                        key={i}
                        title={`${fmtTime(c.start)} · ${cat(c.category)}`}
                        onClick={() => { seek(c.start); setActive(report.claims.indexOf(c)) }}
                        className={`absolute top-2 bottom-2 w-1.5 -ml-0.75 rounded-full ${CAT_COLOR[c.category]} transition-all duration-300 ease-[var(--ease-spring)] hover:top-1 hover:bottom-1 hover:w-2.5`}
                        style={{ left: `${Math.min(98.5, Math.max(1.5, (c.start / source.duration) * 100))}%`, opacity: 0.4 + c.confidence * 0.6 }}
                      />
                    ))}
                </div>
                <div className="mt-2 flex justify-between px-1 font-mono text-[11px] text-ink-3">
                  <span>0:00</span><span>{fmtTime(source.duration / 2)}</span><span>{fmtTime(source.duration)}</span>
                </div>
              </Glass>
            )}

            <Glass className="p-4 sm:p-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <Segmented
                  value={tab}
                  onChange={setTab}
                  options={[
                    { value: 'findings', label: <>{t.findings} <span className="font-mono text-ink-3">{visible.length}</span></> },
                    { value: 'transcript', label: isMessage ? t.msgTitle : t.transcript },
                  ]}
                  className="min-w-[260px]"
                />
                <Toggle checked={showWeak} onChange={setShowWeak} label={t.showWeak} />
              </div>

              {tab === 'findings' ? (
                <div className="mt-5">
                  <div className="mb-4 flex flex-wrap gap-2">
                    <Chip on={filter === 'all'} onClick={() => setFilter('all')}>{t.all}</Chip>
                    {[...counts.entries()].map(([c, n]) => (
                      <Chip key={c} on={filter === c} onClick={() => setFilter(c)}>
                        <span className={`size-2 rounded-full ${CAT_COLOR[c]}`} /> {cat(c)} <span className="font-mono opacity-60">{n}</span>
                      </Chip>
                    ))}
                  </div>
                  {visible.length === 0 ? (
                    <p className="py-10 text-center text-ink-3">{t.noFindings}</p>
                  ) : (
                    <ul className="space-y-3">
                      {visible.map((c) => {
                        const idx = report.claims.indexOf(c)
                        return (
                          <ClaimRow key={idx} c={c} label={cat(c.category)} active={active === idx} posLabel={pos(c.start)}
                            onSeek={source.video_id && c.where === 'transcript' ? () => { seek(c.start); setActive(idx) } : undefined} />
                        )
                      })}
                    </ul>
                  )}
                </div>
              ) : isMessage ? (
                <div className="mt-5 rounded-[24px] bg-[linear-gradient(160deg,#0b141a,#111b21)] p-4 sm:p-6">
                  <div className="max-w-xl rounded-[18px] rounded-tl-md bg-[#005c4b] px-4 py-3 shadow-lg">
                    {report.segments.map((s, i) => (
                      <p key={i} className={`flex gap-3 rounded-lg px-1.5 py-1 text-[15px] leading-relaxed text-[#e9edef] ${
                        flagged.has(s.start) ? 'bg-[rgba(255,59,48,.28)] shadow-[inset_0_0_0_1px_rgba(255,120,110,.6)]' : ''}`}>
                        <span className="w-6 shrink-0 pt-0.5 text-right font-mono text-[11px] text-[#8fd3c4]">{i + 1}</span>
                        <span className="min-w-0 break-words">{s.text}</span>
                      </p>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="mt-5 max-h-[600px] space-y-0.5 overflow-y-auto pr-1 text-[15px] leading-relaxed">
                  {report.segments.map((s, i) => (
                    <button
                      key={i}
                      onClick={() => source.video_id && seek(s.start)}
                      className={`flex w-full gap-4 rounded-2xl px-3 py-2 text-left transition hover:bg-[var(--glass-inset)] ${
                        flagged.has(s.start) ? 'bg-[color-mix(in_oklab,#ff3b30_10%,transparent)] shadow-[inset_0_0_0_1px_color-mix(in_oklab,#ff3b30_25%,transparent)]' : ''
                      }`}
                    >
                      <span className="w-12 shrink-0 pt-0.5 font-mono text-xs text-ink-3">{fmtTime(s.start)}</span>
                      <span className="text-ink">{s.text}</span>
                    </button>
                  ))}
                </div>
              )}
            </Glass>
          </div>

          {/* Side column */}
          <aside className="space-y-5 order-first lg:order-none">
            {(!isMessage || (report.registry.checks ?? []).length > 0) && <RegistryCard report={report} />}
            <Glass className="p-6">
              <p className="eyebrow">{t.verifyReport}</p>
              <ul className="mt-3 space-y-2.5 text-sm leading-relaxed text-ink-2">
                <li>{t.todo2}</li>
                <li>{t.todo3}</li>
              </ul>
              <div className="mt-4 flex flex-wrap gap-2">
                {[
                  [SEBI_RA, t.sebiList],
                  ['https://cybercrime.gov.in', 'cybercrime.gov.in'],
                  ['https://scores.sebi.gov.in', 'SEBI SCORES'],
                ].map(([href, label]) => (
                  <LinkButton key={href} href={href} target="_blank" rel="noreferrer" size="sm">
                    {label} <ExternalLink className="size-3" />
                  </LinkButton>
                ))}
              </div>
            </Glass>
            <p className="px-2 text-xs text-ink-3">
              {t.analysedWith} <span className="font-mono">{report.model}</span> · {t.took} {Math.round(totalTime)}{t.seconds}
            </p>
          </aside>
        </div>
      </div>
    </>
  )
}

function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <label className="inline-flex cursor-pointer select-none items-center gap-2.5 text-[13px] font-medium text-ink-2">
      {label}
      <button
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative h-[26px] w-[44px] rounded-full transition-colors duration-300 ${checked ? 'bg-[#34c759]' : 'bg-[var(--hairline)] shadow-[inset_0_0_0_1px_var(--hairline)]'}`}
      >
        <span className={`absolute left-0 top-[2px] size-[22px] rounded-full bg-white shadow-[0_2px_6px_rgba(0,0,0,.25)] transition-transform duration-300 ease-[var(--ease-spring)] ${checked ? 'translate-x-[20px]' : 'translate-x-[2px]'}`} />
      </button>
    </label>
  )
}

function ClaimRow({ c, label, active, onSeek, posLabel }: { c: Claim; label: string; active: boolean; onSeek?: () => void; posLabel: string }) {
  const { t, lang } = useLang()
  const why = lang === 'hi' && c.why_hi ? c.why_hi : c.why_en
  const sev = c.severity === 3 ? '#ff3b30' : c.severity === 2 ? '#ff9f0a' : '#8e8e93'
  return (
    <li className={`glass-inset p-4 transition-all duration-500 ${active ? 'shadow-[inset_0_0_0_2px_#ff9500,0_10px_30px_-12px_rgba(255,149,0,.5)]!' : ''}`}>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        {c.where === 'transcript' ? (
          <button
            onClick={onSeek}
            disabled={!onSeek}
            className="inline-flex h-7 items-center gap-1 rounded-full bg-[var(--ink)] px-2.5 font-mono font-medium text-[var(--bg)] transition active:scale-95 disabled:opacity-70"
          >
            {onSeek && <Play className="size-3" fill="currentColor" />} {posLabel}
          </button>
        ) : (
          <span className="inline-flex h-7 items-center gap-1 rounded-full bg-[var(--glass-inset)] px-2.5 font-medium text-ink-2 shadow-[inset_0_0_0_1px_var(--hairline)]">
            <FileText className="size-3" /> {t.description}
          </span>
        )}
        <span className="inline-flex items-center gap-1.5 text-[13px] font-semibold text-ink">
          <span className={`size-2 rounded-full ${CAT_COLOR[c.category]}`} /> {label}
        </span>
        <span className="rounded-full px-2 py-0.5 text-[11px] font-semibold"
          style={{ color: sev, background: `color-mix(in oklab, ${sev} 14%, transparent)` }}>
          {t.severity[c.severity]}
        </span>
        <span className="ml-auto inline-flex items-center gap-2 text-ink-3">
          <span className="rounded-full px-2 py-0.5 text-[11px] shadow-[inset_0_0_0_1px_var(--hairline)]">{t[`origin_${c.origin}`]}</span>
          <span className="inline-flex items-center gap-1.5 font-mono text-[11px]" title={t.confidence}>
            <span className="h-1 w-10 overflow-hidden rounded-full bg-[var(--hairline)]">
              <span className="block h-full rounded-full bg-[var(--ink-3)]" style={{ width: `${c.confidence * 100}%` }} />
            </span>
            {Math.round(c.confidence * 100)}%
          </span>
        </span>
      </div>
      <blockquote className="mt-3 border-l-[3px] border-[#ff9500] pl-3.5 text-[15px] font-medium leading-relaxed text-ink">“{c.quote}”</blockquote>
      <p className="mt-2 text-sm leading-relaxed text-ink-2" lang={lang}>{why}</p>
    </li>
  )
}

function RegistryCard({ report }: { report: Report }) {
  const { t } = useLang()
  const r = report.registry
  const good = r.verdict === 'verified' || r.verdict === 'matched' || r.verdict === 'guests_registered'
  const bad = ['number_not_found', 'not_registered', 'claimed_unverified', 'registered_other'].includes(r.verdict)
  const Icon = good ? BadgeCheck : bad ? BadgeX : ShieldQuestion
  const color = good ? '#34c759' : bad ? '#ff3b30' : '#ff9f0a'
  const typo = Object.values(r.number_results).some((h) => h && h.score < 100)
  const checks = r.checks ?? []
  return (
    <Glass className="p-6">
      <p className="eyebrow">{t.registry}</p>
      <div className="mt-4 flex items-start gap-3 rounded-[20px] p-4"
        style={{ background: `color-mix(in oklab, ${color} 13%, transparent)`, boxShadow: `inset 0 0 0 1px color-mix(in oklab, ${color} 25%, transparent)` }}>
        <Icon className="size-6 shrink-0" style={{ color }} />
        <div className="min-w-0">
          <p className="font-semibold text-ink">{r.verdict === 'verified' && typo ? t.verifiedTypo : t.verdict[r.verdict]}</p>
          {r.entity && (
            <p className="mt-1 text-sm font-medium text-ink">
              {r.entity.name} · {t.catNames[r.entity.category] ?? r.entity.category}{' '}
              <span className="font-mono text-xs text-ink-3">{r.entity.reg_no}</span>
            </p>
          )}
          <p className="mt-1 text-[13px] leading-relaxed text-ink-2">{t.verdictHelp[r.verdict]}</p>
        </div>
      </div>

      {checks.length > 0 ? (
        <div className="mt-5">
          <p className="eyebrow">{t.checked}</p>
          <ul className="mt-3 space-y-2.5 text-sm">
            {checks.map((c, i) => {
              const h = c.hits[0]
              return (
                <li key={i} className="flex gap-2.5">
                  {h ? <BadgeCheck className="mt-0.5 size-4 shrink-0 text-[#34c759]" /> : <BadgeX className="mt-0.5 size-4 shrink-0 text-ink-3" />}
                  <div className="min-w-0">
                    <p className="truncate">
                      <span className={c.kind === 'name' ? 'font-semibold text-ink' : 'font-mono text-xs text-ink'}>{c.query}</span>
                      <span className="text-xs text-ink-3"> · {t.roles[c.role] ?? c.role}</span>
                    </p>
                    <p className="truncate text-xs text-ink-3">
                      {h ? (
                        <>
                          {h.how === 'near_number' && <span className="text-[#ff9f0a]">{t.typoMatch} </span>}
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
          <div className="mt-5">
            <p className="eyebrow">{t.numbersQuoted}</p>
            <ul className="mt-2 space-y-1.5 text-sm">
              {r.numbers_found.map((n) => {
                const hit = r.number_results[n]
                return (
                  <li key={n} className="flex flex-wrap items-center gap-x-2">
                    {hit ? <BadgeCheck className="size-4 text-[#34c759]" /> : <BadgeX className="size-4 text-[#ff3b30]" />}
                    <span className="font-mono text-ink">{n}</span>
                    {hit && <span className="truncate text-ink-3">· {hit.name}</span>}
                  </li>
                )
              })}
            </ul>
          </div>
        )
      )}

      <div className="mt-5 flex items-center justify-between border-t hairline pt-4 text-sm">
        <span className="text-ink-2">{t.disclaimer}</span>
        <span className="inline-flex items-center gap-1 font-semibold" style={{ color: r.disclaimer_found ? '#34c759' : '#ff9f0a' }}>
          {r.disclaimer_found ? <BadgeCheck className="size-4" /> : <AlertTriangle className="size-4" />}
          {r.disclaimer_found ? t.disclaimerYes : t.disclaimerNo}
        </span>
      </div>
      <a className="link mt-4 text-sm" href={SEBI_RA} target="_blank" rel="noreferrer">
        {t.verifyOn} <ExternalLink className="size-3.5" />
      </a>
    </Glass>
  )
}
