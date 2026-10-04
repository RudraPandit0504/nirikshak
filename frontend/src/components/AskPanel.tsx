import { useEffect, useRef, useState } from 'react'
import { ArrowUp, BookOpen, Loader2, MessageCircleQuestion, Mic, Play, ShieldAlert, Square } from 'lucide-react'
import { askReport, fmtTime, transcribeAudio } from '../api'
import { useLang } from '../i18n'
import type { AskAnswer } from '../types'
import Glass from './ui/Glass'

type Msg = { role: 'user'; text: string } | { role: 'assistant'; text: string; answer: AskAnswer }
type MicState = 'idle' | 'recording' | 'transcribing'

/** Chat about one audited video. History stays in this page only; nothing is saved. */
export default function AskPanel({ reportId, isMessage = false, onSeek }: {
  reportId: string
  isMessage?: boolean
  onSeek?: (t: number) => void
}) {
  const { t, lang } = useLang()
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [mic, setMic] = useState<MicState>('idle')
  const recorder = useRef<MediaRecorder | null>(null)
  const scroller = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: 'smooth' })
  }, [msgs, busy])

  const send = async (q: string) => {
    const question = q.trim()
    if (!question || busy) return
    setErr('')
    setInput('')
    // The model reasons in English; send its English answers back, not the Hindi translation.
    const history = msgs.map((m) => ({ role: m.role, text: m.role === 'assistant' ? m.answer.answer_en : m.text }))
    setMsgs((m) => [...m, { role: 'user', text: question }])
    setBusy(true)
    try {
      const answer = await askReport(reportId, question, lang, history)
      setMsgs((m) => [...m, { role: 'assistant', text: answer.answer, answer }])
    } catch (e) {
      setErr((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const toggleMic = async () => {
    if (mic === 'recording') {
      recorder.current?.stop()
      return
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setErr(t.askNoMic)
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const rec = new MediaRecorder(stream)
      const chunks: Blob[] = []
      rec.ondataavailable = (e) => chunks.push(e.data)
      rec.onstop = async () => {
        stream.getTracks().forEach((tr) => tr.stop())
        setMic('transcribing')
        try {
          const { text } = await transcribeAudio(new Blob(chunks, { type: rec.mimeType }))
          setInput((v) => (v ? `${v} ${text}` : text))
        } catch (e) {
          setErr((e as Error).message)
        } finally {
          setMic('idle')
        }
      }
      recorder.current = rec
      rec.start()
      setMic('recording')
    } catch {
      setErr(t.askNoMic)
    }
  }

  return (
    <Glass className="p-5 sm:p-7">
      <div className="flex items-start gap-3">
        <span className="grid size-11 shrink-0 place-items-center rounded-2xl text-white shadow-[inset_0_1px_0_rgba(255,255,255,.45),0_8px_20px_-10px_#5856d6]"
          style={{ background: 'linear-gradient(135deg,#5ac8fa,#5856d6)' }}>
          <MessageCircleQuestion className="size-5" />
        </span>
        <div>
          <h2 className="display text-xl">{t.askTitle}</h2>
          <p className="mt-0.5 text-sm text-ink-2">{t.askSub}</p>
        </div>
      </div>

      {msgs.length > 0 && (
        <div ref={scroller} className="mt-5 max-h-[460px] space-y-3 overflow-y-auto pr-1">
          {msgs.map((m, i) =>
            m.role === 'user' ? (
              <div key={i} className="flex justify-end">
                <p className="max-w-[85%] rounded-[22px] rounded-br-md bg-[linear-gradient(135deg,#0a84ff,#5856d6)] px-4 py-2.5 text-[15px] leading-relaxed text-white shadow-[inset_0_1px_0_rgba(255,255,255,.3),0_8px_20px_-12px_#0a84ff]">
                  {m.text}
                </p>
              </div>
            ) : (
              <div key={i} className="flex justify-start">
                <div className="glass-inset max-w-[90%] rounded-[22px]! rounded-bl-md! px-4 py-3">
                  {m.answer.kind !== 'video' && (
                    <span className="mb-2 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold"
                      style={m.answer.kind === 'refused'
                        ? { color: '#ff9f0a', background: 'color-mix(in oklab,#ff9f0a 14%,transparent)' }
                        : { color: '#5856d6', background: 'color-mix(in oklab,#5856d6 14%,transparent)' }}>
                      {m.answer.kind === 'refused' ? <ShieldAlert className="size-3" /> : <BookOpen className="size-3" />}
                      {m.answer.kind === 'refused' ? t.askRefused : t.askGeneral}
                    </span>
                  )}
                  <p className="text-[15px] leading-relaxed text-ink" lang={lang}>{m.text}</p>
                  {m.answer.citations.length > 0 && (
                    <div className="mt-2.5 flex flex-wrap gap-1.5">
                      {m.answer.citations.map((c) => (
                        <button
                          key={c.line}
                          onClick={() => onSeek?.(c.start)}
                          disabled={!onSeek}
                          title={c.quote}
                          className="inline-flex h-7 items-center gap-1 rounded-full bg-[var(--ink)] px-2.5 font-mono text-xs font-medium text-[var(--bg)] transition active:scale-95 disabled:opacity-80"
                        >
                          {onSeek && <Play className="size-3" fill="currentColor" />}
                          {isMessage ? `${t.askLine} ${c.line + 1}` : fmtTime(c.start)}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ),
          )}
          {busy && (
            <div className="flex justify-start">
              <div className="glass-inset inline-flex items-center gap-2 rounded-[22px]! rounded-bl-md! px-4 py-3 text-sm text-ink-2">
                <span className="flex gap-1">
                  {[0, 1, 2].map((d) => (
                    <span key={d} className="size-1.5 animate-bounce rounded-full bg-[var(--ink-3)]" style={{ animationDelay: `${d * 140}ms` }} />
                  ))}
                </span>
                {t.askThinking}
              </div>
            </div>
          )}
        </div>
      )}

      {msgs.length === 0 && (
        <div className="mt-5 flex flex-wrap gap-2">
          {t.askSuggest.map((s) => (
            <button key={s} onClick={() => send(s)} disabled={busy}
              className="glass-pill h-9 px-3.5 text-[13px] font-medium text-ink-2 transition hover:text-ink active:scale-95">
              {s}
            </button>
          ))}
        </div>
      )}

      {err && <p className="mt-3 text-sm text-[#ff3b30]">{err}</p>}

      <form onSubmit={(e) => { e.preventDefault(); send(input) }}
        className="glass-pill mt-5 flex items-center gap-1.5 p-1.5 pl-4">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={mic === 'recording' ? t.askRecording : mic === 'transcribing' ? t.askTranscribing : t.askPlaceholder}
          aria-label={t.askPlaceholder}
          disabled={mic !== 'idle'}
          className="min-w-0 flex-1 bg-transparent py-2 text-[15px] text-ink outline-none placeholder:text-ink-3"
        />
        <button type="button" onClick={toggleMic} disabled={mic === 'transcribing' || busy} title={t.askMic} aria-label={t.askMic}
          className={`grid size-10 shrink-0 place-items-center rounded-full transition active:scale-95 ${
            mic === 'recording' ? 'bg-[#ff3b30] text-white shadow-[0_0_0_6px_color-mix(in_oklab,#ff3b30_25%,transparent)] animate-pulse'
              : 'text-ink-2 hover:bg-[var(--glass-inset)] hover:text-ink'
          }`}>
          {mic === 'transcribing' ? <Loader2 className="size-[18px] animate-spin" /> : mic === 'recording' ? <Square className="size-4" fill="currentColor" /> : <Mic className="size-[18px]" />}
        </button>
        <button type="submit" disabled={!input.trim() || busy} aria-label="Send"
          className="grid size-10 shrink-0 place-items-center rounded-full bg-[linear-gradient(135deg,#ff9500,#ff5e3a)] text-white shadow-[inset_0_1px_0_rgba(255,255,255,.45),0_6px_16px_-6px_rgba(255,94,58,.7)] transition active:scale-95 disabled:opacity-40">
          {busy ? <Loader2 className="size-[18px] animate-spin" /> : <ArrowUp className="size-[18px]" strokeWidth={2.5} />}
        </button>
      </form>
    </Glass>
  )
}
