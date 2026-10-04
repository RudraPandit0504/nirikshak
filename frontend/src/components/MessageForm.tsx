import { useRef, useState } from 'react'
import { ImagePlus, Loader2, ScanSearch, X } from 'lucide-react'
import { checkMessage } from '../api'
import { useLang } from '../i18n'
import { Button } from './ui/Button'

/** Paste a forwarded tip or drop a screenshot of it. */
export default function MessageForm({ busy, run }: { busy: boolean; run: (start: () => Promise<{ job: string }>) => void }) {
  const { t } = useLang()
  const [text, setText] = useState('')
  const [image, setImage] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [keep, setKeep] = useState(true)
  const [drag, setDrag] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const pick = (f: File | undefined) => {
    if (!f || !f.type.startsWith('image/')) return
    setImage(f)
    setPreview(URL.createObjectURL(f))
  }
  const clear = () => {
    if (preview) URL.revokeObjectURL(preview)
    setImage(null)
    setPreview(null)
  }
  const can = !busy && (image || text.trim())

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); if (can) run(() => checkMessage(text, image, keep)) }}
      className="glass-strong mx-auto mt-10 max-w-3xl p-3 text-left"
    >
      {image ? (
        <div className="relative flex items-center gap-4 rounded-[20px] bg-[var(--glass-inset)] p-3 shadow-[inset_0_0_0_1px_var(--hairline)]">
          <img src={preview!} alt="" className="h-28 w-20 rounded-xl object-cover object-top shadow-md" />
          <div className="min-w-0 flex-1">
            <p className="truncate font-semibold text-ink">{image.name}</p>
            <p className="mt-1 text-sm text-ink-3">{t.msgScreenshotHint}</p>
          </div>
          <Button type="button" size="sm" variant="ghost" onClick={clear}><X className="size-4" /> {t.msgRemove}</Button>
        </div>
      ) : (
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onPaste={(e) => pick([...e.clipboardData.files].find((f) => f.type.startsWith('image/')))}
          placeholder={t.msgPlaceholder}
          rows={6}
          aria-label={t.msgPlaceholder}
          className="w-full resize-y rounded-[20px] bg-transparent px-4 py-3 text-base leading-relaxed text-ink outline-none placeholder:text-ink-3"
        />
      )}

      {!image && (
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files[0]) }}
          className={`mx-1 mb-1 flex w-[calc(100%-0.5rem)] items-center justify-center gap-2 rounded-[18px] border-2 border-dashed py-4 text-sm transition ${
            drag ? 'border-[#ff9500] bg-[color-mix(in_oklab,#ff9500_10%,transparent)] text-ink' : 'border-[var(--hairline)] text-ink-3 hover:text-ink-2'
          }`}
        >
          <ImagePlus className="size-5" /> {t.msgScreenshot}
          <span className="hidden text-xs sm:inline">· {t.msgScreenshotHint}</span>
        </button>
      )}
      <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={(e) => pick(e.target.files?.[0])} />

      <div className="mt-2 flex flex-wrap items-center justify-between gap-3 px-2 pb-1">
        <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-ink-2 select-none">
          <input type="checkbox" checked={keep} onChange={(e) => setKeep(e.target.checked)} className="size-4 accent-[#ff9500]" />
          {t.msgKeep}
        </label>
        <Button variant="primary" size="lg" disabled={!can}>
          {busy ? <Loader2 className="size-5 animate-spin" /> : <ScanSearch className="size-5" />} {t.msgCheck}
        </Button>
      </div>
    </form>
  )
}
