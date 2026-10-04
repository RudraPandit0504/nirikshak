import { useState } from 'react'
import { fmtTime } from '../api'
import { useLang } from '../i18n'
import type { Category, Claim, Lang, Report } from '../types'

/** Full audit report laid out for A4 paper. Hidden on screen, shown only when printing,
 *  so "Save as PDF" produces a self-contained document rather than a screenshot of the UI. */

const L = {
  en: {
    title: 'Audit report', generated: 'Generated', reportId: 'Report ID',
    video: 'Video', channel: 'Channel', link: 'Link', duration: 'Duration', language: 'Spoken language',
    transcript: 'Transcript source', captions: 'YouTube captions', whisper: 'Whisper speech-to-text (local)', upload: 'Uploaded file',
    audited: 'Audited', models: 'AI models (run locally)',
    verdict: 'Verdict', riskScore: 'Risk score', level: { low: 'Low risk', medium: 'Caution', high: 'High risk' },
    summary: 'Summary', concerns: 'Main concerns', registration: 'SEBI registration', advice: 'What you should do',
    glance: 'Findings at a glance', category: 'Category', count: 'Findings', highest: 'Highest severity', none: 'No warning signs were found.',
    registry: 'SEBI registration check', regVerdict: 'Result', numbers: 'Registration numbers quoted in the video',
    number: 'Number quoted', inRegistry: 'In SEBI registry', entity: 'Registered entity', validity: 'Validity',
    yes: 'Yes', near: 'Near match (typo)', no: 'Not found', similar: 'Similar registered names (not proof of identity)',
    disclaimer: 'Risk disclaimer', found: 'Found', notFound: 'Not found',
    findings: 'All findings', weak: 'Weak signals (confidence below 50%, shown for completeness)',
    time: 'Time', sev: 'Severity', conf: 'Confidence', source: 'Detected by', quote: 'What was said', why: 'Why it matters',
    desc: 'Description', severity: ['', 'Mild', 'Serious', 'Severe'], origin: { llm: 'AI', rules: 'Keyword', 'llm+rules': 'AI + keyword' },
    help: 'Verify and report',
    helpItems: [
      'Check any adviser or analyst: SEBI registered intermediaries list, sebi.gov.in → Intermediaries / Market Infrastructure Institutions → Recognised Intermediaries.',
      'Cyber-fraud helpline: call 1930, or report at cybercrime.gov.in.',
      'Complaints against SEBI-registered entities: SEBI SCORES, scores.sebi.gov.in.',
    ],
    method: 'How this audit was made',
    methodItems: [
      'The transcript comes from the video\'s captions, or from Whisper speech-to-text running on this computer.',
      'A keyword scanner (English, Hinglish, Hindi) and a local AI model (Qwen 2.5 7B) look for statements in 8 categories of investor harm. Every finding must quote the transcript word-for-word, otherwise it is discarded.',
      'Registration numbers and the channel name are checked against a copy of SEBI\'s public registry of Research Analysts and Investment Advisers.',
      'The risk score (0-100) adds up the strongest findings of each kind, so several different red flags count more than one repeated phrase.',
    ],
    limits: 'Limitations: Nirikshak audits what is said. It does not judge whether any stock or product is good, and it is not investment advice. AI can make mistakes, so check each quoted moment yourself.',
    appendix: 'Appendix: full transcript', flaggedNote: 'Lines marked ⚑ contain a finding.',
    page: 'Nirikshak · निरीक्षक · local-first audit of finance-influencer videos',
  },
  hi: {
    title: 'ऑडिट रिपोर्ट', generated: 'बनाई गई', reportId: 'रिपोर्ट ID',
    video: 'वीडियो', channel: 'चैनल', link: 'लिंक', duration: 'अवधि', language: 'बोली गई भाषा',
    transcript: 'ट्रांसक्रिप्ट कहाँ से', captions: 'YouTube कैप्शन', whisper: 'Whisper (आवाज़ से टेक्स्ट, इसी कंप्यूटर पर)', upload: 'अपलोड की गई फ़ाइल',
    audited: 'जाँच की तारीख', models: 'AI मॉडल (इसी कंप्यूटर पर)',
    verdict: 'नतीजा', riskScore: 'जोखिम स्कोर', level: { low: 'कम जोखिम', medium: 'सावधान रहें', high: 'ज़्यादा जोखिम' },
    summary: 'सारांश', concerns: 'मुख्य खतरे', registration: 'SEBI रजिस्ट्रेशन', advice: 'आपको क्या करना चाहिए',
    glance: 'खतरे के संकेत: एक नज़र में', category: 'किस तरह का', count: 'कितने', highest: 'सबसे गंभीर', none: 'कोई खास खतरे का संकेत नहीं मिला।',
    registry: 'SEBI रजिस्ट्रेशन की जाँच', regVerdict: 'परिणाम', numbers: 'वीडियो में बताए गए रजिस्ट्रेशन नंबर',
    number: 'बताया गया नंबर', inRegistry: 'SEBI सूची में', entity: 'रजिस्टर्ड संस्था', validity: 'वैधता',
    yes: 'हाँ', near: 'मिलता-जुलता (टाइपो)', no: 'नहीं मिला', similar: 'मिलते-जुलते रजिस्टर्ड नाम (इससे पहचान पक्की नहीं होती)',
    disclaimer: 'जोखिम की चेतावनी (डिस्क्लेमर)', found: 'है', notFound: 'नहीं है',
    findings: 'सभी खतरे के संकेत', weak: 'कमज़ोर संकेत (भरोसा 50% से कम, सिर्फ़ जानकारी के लिए)',
    time: 'समय', sev: 'गंभीरता', conf: 'भरोसा', source: 'किसने पकड़ा', quote: 'क्या कहा गया', why: 'यह क्यों मायने रखता है',
    desc: 'डिस्क्रिप्शन', severity: ['', 'हल्का', 'गंभीर', 'बहुत गंभीर'], origin: { llm: 'AI', rules: 'कीवर्ड', 'llm+rules': 'AI + कीवर्ड' },
    help: 'जाँचें और शिकायत करें',
    helpItems: [
      'किसी भी सलाहकार या एनालिस्ट को पैसे देने से पहले जाँचें: SEBI की रजिस्टर्ड लोगों की सूची, sebi.gov.in।',
      'साइबर-ठगी हेल्पलाइन: 1930 पर कॉल करें, या cybercrime.gov.in पर शिकायत करें।',
      'SEBI में रजिस्टर्ड किसी कंपनी या सलाहकार की शिकायत: SEBI SCORES, scores.sebi.gov.in।',
    ],
    method: 'यह जाँच कैसे की गई',
    methodItems: [
      'वीडियो में क्या कहा गया, यह YouTube कैप्शन से या इसी कंप्यूटर पर चलने वाले Whisper से लिया गया।',
      'एक कीवर्ड जाँच (अंग्रेज़ी, हिंग्लिश, हिंदी) और इसी कंप्यूटर पर चलने वाला AI मॉडल (Qwen 2.5 7B) निवेशकों को नुकसान पहुँचाने वाली 8 तरह की बातें ढूँढते हैं। हर संकेत के साथ वीडियो की हूबहू लाइन देनी होती है, वरना उसे हटा दिया जाता है।',
      'रजिस्ट्रेशन नंबर और चैनल का नाम SEBI की रिसर्च एनालिस्ट और इन्वेस्टमेंट एडवाइज़र की सार्वजनिक सूची से मिलाए जाते हैं।',
      'जोखिम स्कोर (0-100) हर तरह के सबसे मज़बूत संकेतों को जोड़कर बनता है। इसलिए कई अलग-अलग खतरे, एक ही बात बार-बार कहने से ज़्यादा गिने जाते हैं।',
    ],
    limits: 'ध्यान दें: निरीक्षक सिर्फ़ यह जाँचता है कि वीडियो में क्या कहा गया। यह किसी शेयर या प्रोडक्ट को अच्छा या बुरा नहीं बताता, और यह निवेश की सलाह नहीं है। AI से गलती हो सकती है, इसलिए बताया गया हिस्सा खुद भी देखें।',
    appendix: 'पूरी ट्रांसक्रिप्ट', flaggedNote: '⚑ वाली लाइनों में खतरे का संकेत मिला है।',
    page: 'Nirikshak · निरीक्षक · फाइनेंस वीडियो की जाँच, आपके अपने कंप्यूटर पर',
  },
} as const

const LEVEL_COLOR = { low: '#059669', medium: '#d97706', high: '#dc2626' }

function ytLink(id: string | null, t: number) {
  return id ? `https://youtu.be/${id}?t=${Math.floor(t)}` : null
}

function fmtDate(iso: string, lang: Lang) {
  try {
    return new Date(iso).toLocaleString(lang === 'hi' ? 'hi-IN' : 'en-IN', { dateStyle: 'medium', timeStyle: 'short' })
  } catch {
    return iso
  }
}

export default function PrintReport({ report, catLabel }: { report: Report; catLabel: (c: Category) => string }) {
  const { t, lang } = useLang()
  const p = L[lang]
  const { source, registry: reg } = report
  const s = report.summary?.[lang]
  const strong = report.claims.filter((c) => c.confidence >= 0.5)
  const weak = report.claims.filter((c) => c.confidence < 0.5)
  const why = (c: Claim) => (lang === 'hi' && c.why_hi ? c.why_hi : c.why_en)

  const byCat = new Map<Category, Claim[]>()
  for (const c of strong) byCat.set(c.category, [...(byCat.get(c.category) ?? []), c])
  const flaggedAt = new Map<number, Claim[]>()
  for (const c of strong) if (c.where === 'transcript') flaggedAt.set(c.start, [...(flaggedAt.get(c.start) ?? []), c])
  const typo = Object.values(reg.number_results).some((h) => h && h.score < 100)
  const [generatedAt] = useState(() => new Date().toISOString())

  return (
    <article className="print-report hidden print:block" lang={lang}>
      {/* Header */}
      <header className="pr-header">
        <div>
          <div className="pr-brand">Nirikshak · निरीक्षक</div>
          <h1>{p.title}</h1>
        </div>
        <div className="pr-score" style={{ borderColor: LEVEL_COLOR[report.risk_level], color: LEVEL_COLOR[report.risk_level] }}>
          <div className="pr-score-num">{report.risk_score}<span>/100</span></div>
          <div className="pr-score-label">{p.level[report.risk_level]}</div>
        </div>
      </header>

      {/* Video details */}
      <section className="pr-avoid">
        <table className="pr-kv">
          <tbody>
            <tr><th>{p.video}</th><td><strong>{source.title}</strong></td></tr>
            {source.channel && <tr><th>{p.channel}</th><td>{source.channel}</td></tr>}
            {source.url && <tr><th>{p.link}</th><td><a href={source.url}>{source.url}</a></td></tr>}
            {source.duration > 0 && <tr><th>{p.duration}</th><td>{fmtTime(source.duration)}</td></tr>}
            {source.language && <tr><th>{p.language}</th><td>{t.langNames[source.language] ?? source.language}</td></tr>}
            <tr><th>{p.transcript}</th><td>{source.kind === 'upload' ? `${p.upload} · ` : ''}{source.transcript_source === 'whisper' ? p.whisper : p.captions}</td></tr>
            <tr><th>{p.audited}</th><td>{fmtDate(report.created_at, lang)}</td></tr>
            <tr><th>{p.models}</th><td>{report.model} · Whisper large-v3-turbo</td></tr>
            <tr><th>{p.reportId}</th><td className="pr-mono">{report.id}</td></tr>
          </tbody>
        </table>
      </section>

      {/* Summary */}
      <section>
        <h2>{p.summary}</h2>
        <p className="pr-headline">{s?.headline ?? (lang === 'hi' ? report.summary_hi : report.summary_en)}</p>
        {s && <p>{s.overview}</p>}
        {s && s.concerns.length > 0 && (
          <>
            <h3>{p.concerns}</h3>
            <ol className="pr-list">
              {s.concerns.map((c, i) => (
                <li key={i}>
                  <strong>{c.where === 'transcript' ? fmtTime(c.start) : p.desc} · {catLabel(c.category)}:</strong> {c.why}
                </li>
              ))}
            </ol>
          </>
        )}
        {s && (
          <>
            <h3>{p.registration}</h3>
            <p>{s.registration}</p>
            <h3>{p.advice}</h3>
            <ul className="pr-list">{s.advice.map((a, i) => <li key={i}>{a}</li>)}</ul>
          </>
        )}
      </section>

      {/* At a glance */}
      <section className="pr-avoid">
        <h2>{p.glance}</h2>
        {byCat.size === 0 ? <p>{p.none}</p> : (
          <table className="pr-table">
            <thead><tr><th>{p.category}</th><th>{p.count}</th><th>{p.highest}</th></tr></thead>
            <tbody>
              {[...byCat.entries()].sort((a, b) => b[1].length - a[1].length).map(([c, list]) => (
                <tr key={c}>
                  <td>{catLabel(c)}</td>
                  <td>{list.length}</td>
                  <td>{p.severity[Math.max(...list.map((x) => x.severity))]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* Registry */}
      <section className="pr-avoid">
        <h2>{p.registry}</h2>
        <p><strong>{p.regVerdict}:</strong> {reg.verdict === 'verified' && typo ? t.verifiedTypo : t.verdict[reg.verdict]}. {t.verdictHelp[reg.verdict]}</p>
        {reg.numbers_found.length > 0 && (
          <>
            <h3>{p.numbers}</h3>
            <table className="pr-table">
              <thead><tr><th>{p.number}</th><th>{p.inRegistry}</th><th>{p.entity}</th><th>{p.validity}</th></tr></thead>
              <tbody>
                {reg.numbers_found.map((n) => {
                  const h = reg.number_results[n]
                  return (
                    <tr key={n}>
                      <td className="pr-mono">{n}</td>
                      <td>{!h ? p.no : h.reg_no !== n ? `${p.near}: ${h.reg_no}` : p.yes}</td>
                      <td>{h ? `${h.name} (${h.category})` : '-'}</td>
                      <td>{h?.validity || '-'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </>
        )}
        {reg.name_matches.length > 0 && (
          <>
            <h3>{p.similar}</h3>
            <ul className="pr-list">
              {reg.name_matches.map((h) => <li key={h.reg_no}><span className="pr-mono">{h.reg_no}</span> · {h.name} · {h.category} · {Math.round(h.score)}%</li>)}
            </ul>
          </>
        )}
        <p><strong>{p.disclaimer}:</strong> {reg.disclaimer_found ? p.found : p.notFound}
          {reg.disclaimer_quotes.length > 0 && <> · <em>“{reg.disclaimer_quotes[0]}”</em></>}</p>
      </section>

      {/* All findings */}
      <section>
        <h2>{p.findings} ({strong.length})</h2>
        {strong.length === 0 ? <p>{p.none}</p> : <FindingsTable claims={strong} p={p} why={why} catLabel={catLabel} videoId={source.video_id} />}
        {weak.length > 0 && (
          <>
            <h3>{p.weak}</h3>
            <FindingsTable claims={weak} p={p} why={why} catLabel={catLabel} videoId={source.video_id} compact />
          </>
        )}
      </section>

      {/* Help + method */}
      <section className="pr-avoid">
        <h2>{p.help}</h2>
        <ul className="pr-list">{p.helpItems.map((x, i) => <li key={i}>{x}</li>)}</ul>
      </section>
      <section className="pr-avoid">
        <h2>{p.method}</h2>
        <ul className="pr-list">{p.methodItems.map((x, i) => <li key={i}>{x}</li>)}</ul>
        <p className="pr-note">{p.limits}</p>
      </section>

      {/* Transcript appendix */}
      <section className="pr-appendix">
        <h2>{p.appendix}</h2>
        <p className="pr-note">{p.flaggedNote}</p>
        <table className="pr-transcript">
          <tbody>
            {report.segments.map((seg, i) => {
              const hits = flaggedAt.get(seg.start)
              return (
                <tr key={i} className={hits ? 'pr-flag' : ''}>
                  <td className="pr-mono">{fmtTime(seg.start)}</td>
                  <td>{hits && <strong>⚑ {[...new Set(hits.map((h) => catLabel(h.category)))].join(', ')}: </strong>}{seg.text}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </section>

      <footer className="pr-footer">{p.page} · {p.generated} {fmtDate(generatedAt, lang)}</footer>
    </article>
  )
}

function FindingsTable({ claims, p, why, catLabel, videoId, compact = false }: {
  claims: Claim[]
  p: (typeof L)[Lang]
  why: (c: Claim) => string
  catLabel: (c: Category) => string
  videoId: string | null
  compact?: boolean
}) {
  return (
    <table className={`pr-table pr-findings ${compact ? 'pr-compact' : ''}`}>
      <thead>
        <tr>
          <th>#</th><th>{p.time}</th><th>{p.category}</th><th>{p.sev}</th><th>{p.conf}</th><th>{p.source}</th>
        </tr>
      </thead>
      {claims.map((c, i) => {
        const link = c.where === 'transcript' ? ytLink(videoId, c.start) : null
        return (
          <tbody key={i} className="pr-avoid">
            <tr className="pr-row-head">
              <td>{i + 1}</td>
              <td className="pr-mono">{c.where === 'transcript' ? (link ? <a href={link}>{fmtTime(c.start)}</a> : fmtTime(c.start)) : p.desc}</td>
              <td>{catLabel(c.category)}</td>
              <td>{p.severity[c.severity]}</td>
              <td>{Math.round(c.confidence * 100)}%</td>
              <td>{p.origin[c.origin]}</td>
            </tr>
            <tr>
              <td />
              <td colSpan={5}>
                <div className="pr-quote">“{c.quote}”</div>
                {!compact && <div className="pr-why"><strong>{p.why}:</strong> {why(c)}</div>}
              </td>
            </tr>
          </tbody>
        )
      })}
    </table>
  )
}
