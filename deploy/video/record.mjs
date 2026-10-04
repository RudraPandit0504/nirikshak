// Records the demo: drives the real app in Chrome (DevTools protocol), captures a screencast,
// shows a fake cursor + captions in the page, and logs scene/skip markers for assembly.
// usage: node record.mjs <base-url> <out-dir>
import { spawn } from 'node:child_process'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'

const [base, out] = process.argv.slice(2)
const HERE = new URL('.', import.meta.url).pathname
mkdirSync(`${out}/frames`, { recursive: true })
const narr = Object.fromEntries(JSON.parse(readFileSync(`${HERE}/narration.json`, 'utf8')).map((s) => [s.id, s.text]))
const durs = JSON.parse(readFileSync(`${out}/durations.json`, 'utf8'))

const W = 1280, H = 720, DPR = 1.5
const port = 9500 + Math.floor(Math.random() * 300)
// GPU rendering through ANGLE/OpenGL: the software renderer only manages ~5 fps with the glass blur.
const chrome = spawn('google-chrome', ['--headless=new', `--remote-debugging-port=${port}`, '--hide-scrollbars',
  '--enable-gpu', '--use-angle=gl', '--ignore-gpu-blocklist',
  `--window-size=${W},${H}`, '--autoplay-policy=no-user-gesture-required', '--force-device-scale-factor=1.5',
  `--user-data-dir=${out}/chrome-profile`, 'about:blank'], { stdio: 'ignore' })
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

let wsUrl
for (let i = 0; i < 60 && !wsUrl; i++) {
  await sleep(200)
  try { wsUrl = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find((t) => t.type === 'page')?.webSocketDebuggerUrl } catch { /* starting */ }
}
const ws = new WebSocket(wsUrl)
await new Promise((r) => (ws.onopen = r))
let id = 0
const pending = new Map()
const frames = []
ws.onmessage = (m) => {
  const msg = JSON.parse(m.data)
  if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id) }
  if (msg.method === 'Page.screencastFrame') {
    const { data, metadata, sessionId } = msg.params
    const f = `${out}/frames/${String(frames.length).padStart(6, '0')}.jpg`
    writeFileSync(f, Buffer.from(data, 'base64'))
    frames.push({ f, t: Date.now() / 1000 })
    send('Page.screencastFrameAck', { sessionId })
  }
}
const send = (method, params = {}) => new Promise((r) => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })) })
const ev = async (expr) => (await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true })).result?.result?.value

// In-page helpers: cursor, click ripple, captions, smooth scrolling, typing.
const HELPERS = `
window.__demo = {
  ensure() {
    if (document.getElementById('__cur')) return
    const st = document.createElement('style'); st.textContent = \`
      #__cur{position:fixed;z-index:99999;left:0;top:0;width:26px;height:26px;pointer-events:none;transition:transform .7s cubic-bezier(.22,1,.36,1);filter:drop-shadow(0 3px 6px rgba(0,0,0,.35))}
      .__rip{position:fixed;z-index:99998;width:16px;height:16px;margin:-8px 0 0 -8px;border-radius:50%;background:rgba(255,149,0,.55);pointer-events:none;animation:__r .6s ease-out forwards}
      @keyframes __r{to{transform:scale(4.5);opacity:0}}
      #__cap{position:fixed;z-index:99997;left:50%;bottom:22px;transform:translateX(-50%);max-width:1040px;width:calc(100% - 120px);padding:12px 22px;border-radius:20px;
        background:rgba(12,16,26,.72);backdrop-filter:blur(18px) saturate(160%);color:#fff;font:500 17px/1.45 Geist,Inter,system-ui,sans-serif;text-align:center;box-shadow:0 10px 40px -10px rgba(0,0,0,.6);transition:opacity .35s}
      #__skip{position:fixed;z-index:99997;right:24px;top:86px;padding:8px 14px;border-radius:999px;background:rgba(12,16,26,.75);color:#fff;font:600 14px Geist,system-ui;opacity:0;transition:opacity .3s}\`
    document.head.appendChild(st)
    const c = document.createElement('div'); c.id='__cur'
    c.innerHTML = '<svg viewBox="0 0 24 24" width="26" height="26"><path d="M4 2l16 9-7 2-3 7z" fill="#fff" stroke="#111" stroke-width="1.5" stroke-linejoin="round"/></svg>'
    c.style.transform = 'translate(640px,400px)'; document.body.appendChild(c)
    const cap = document.createElement('div'); cap.id='__cap'; cap.style.opacity=0; document.body.appendChild(cap)
    const sk = document.createElement('div'); sk.id='__skip'; document.body.appendChild(sk)
  },
  caption(t) { this.ensure(); const c=document.getElementById('__cap'); c.textContent=t; c.style.opacity=t?1:0 },
  skipChip(t) { this.ensure(); const s=document.getElementById('__skip'); s.textContent=t; s.style.opacity=1; setTimeout(()=>s.style.opacity=0, 1600) },
  find(q) {
    if (q.startsWith('css:')) return document.querySelector(q.slice(4))
    if (q.startsWith('tab:')) return [...document.querySelectorAll('[role=tab]')].find(e => e.textContent.includes(q.slice(4)))
    const els = [...document.querySelectorAll('button,a,[role=tab],label,h1,h2,p,span')].filter(e => e.offsetParent && e.textContent.trim().includes(q))
    return els.sort((a,b) => a.textContent.length - b.textContent.length)[0]
  },
  async point(q) {
    this.ensure(); const el = this.find(q); if (!el) return 'NF:' + q
    el.scrollIntoView({block:'center', behavior:'smooth'}); await new Promise(r=>setTimeout(r,700))
    const r = el.getBoundingClientRect(); const x = r.left + Math.min(r.width/2, 60), y = r.top + r.height/2
    document.getElementById('__cur').style.transform = 'translate('+x+'px,'+y+'px)'; await new Promise(r=>setTimeout(r,800))
    return {x, y, el}
  },
  async click(q) {
    const p = await this.point(q); if (typeof p === 'string') return p
    const rp = document.createElement('div'); rp.className='__rip'; rp.style.left=p.x+'px'; rp.style.top=p.y+'px'; document.body.appendChild(rp); setTimeout(()=>rp.remove(),700)
    p.el.click(); return 'ok'
  },
  async type(sel, text, ms) {
    const el = document.querySelector(sel); el.focus()
    const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype
    const set = Object.getOwnPropertyDescriptor(proto, 'value').set
    for (let i = 1; i <= text.length; i += 3) { set.call(el, text.slice(0, i)); el.dispatchEvent(new Event('input', {bubbles:true})); await new Promise(r=>setTimeout(r, ms)) }
    set.call(el, text); el.dispatchEvent(new Event('input', {bubbles:true}))
  },
  async scroll(dy, ms) { const steps = Math.max(1, Math.round(ms/16)); for (let i=0;i<steps;i++){ window.scrollBy(0, dy/steps); await new Promise(r=>setTimeout(r,16)) } },
  async scrollTo(q) { const el = this.find(q); if (!el) return 'NF'; const y = el.getBoundingClientRect().top + window.scrollY - 110; await this.scroll(y - window.scrollY, 900); return 'ok' },
}`

const markers = { scenes: [], skips: [] }
let sceneStart = 0
const scene = async (sid, fn) => {
  skippedInScene = 0 // only waits cut *inside* this scene shorten it (fixes 40 s of dead air)
  await ev(`__demo.caption(${JSON.stringify(narr[sid])})`)
  sceneStart = Date.now()
  markers.scenes.push({ id: sid, t: Date.now() / 1000 })
  await fn()
  const left = durs[sid] * 1000 + 700 - (Date.now() - sceneStart - skippedInScene)
  if (left > 0) await sleep(left)
  await ev("__demo.caption('')")
}
let skippedInScene = 0
const skipUntil = async (cond, label, timeout = 240) => {
  const t0 = Date.now() / 1000
  for (let i = 0; i < timeout * 2; i++) { if (await ev(cond)) break; await sleep(500) }
  const t1 = Date.now() / 1000
  markers.skips.push({ from: t0 + 0.6, to: t1 - 0.2, label })
  skippedInScene += Math.max(0, (t1 - t0 - 0.8) * 1000)
  // Show the real waiting time that was cut, not a guess.
  await ev(`__demo.skipChip(${JSON.stringify(label.replace('{s}', Math.round(t1 - t0)))})`)
}
const go = async (hash, wait = 1800) => { await ev(`location.hash = ${JSON.stringify(hash)}`); await sleep(wait); await ev('__demo.ensure()') }

await send('Page.enable')
await send('Runtime.enable')
await send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: DPR, mobile: false })
await send('Page.addScriptToEvaluateOnNewDocument', { source: HELPERS })
await send('Page.navigate', { url: `${base}/?lang=en#/` })
await sleep(3000)
await ev('__demo.ensure()')
await send('Page.startScreencast', { format: 'jpeg', quality: 88, maxWidth: W * DPR, maxHeight: H * DPR, everyNthFrame: 2 }) // 30 fps is plenty and halves the frames written
await sleep(600)

const MSG = 'Dear Customer, your Zerodha DEMAT account will be blocked today due to KYC pending.\nUpdate your KYC immediately: http://zerodha-kyc-update.in/verify\nOur executive will call you, please share the OTP to complete verification.\nNo charges, only ₹99 processing fee to UPI kyc.help@ybl'
const VIDEO = 'https://www.youtube.com/watch?v=ea_OptyJBqw'
let fresh = ''
const R = JSON.parse(readFileSync(`${out}/ids.json`, 'utf8'))

const HOME = 'css:header a[href="#/"]'
// 1. Intro: introduce the three modes on the home page
await scene('intro', async () => {
  await sleep(7500)
  await ev("__demo.point('tab:YouTube video')"); await sleep(2600)
  await ev("__demo.point('tab:WhatsApp message')"); await sleep(2600)
  await ev("__demo.point('tab:Creator')")
})
// 2. WhatsApp message
await scene('msg_paste', async () => {
  await sleep(2500)
  await ev("__demo.click('tab:WhatsApp message')"); await sleep(1200)
  await ev(`__demo.type('textarea', ${JSON.stringify(MSG)}, 16)`); await sleep(800)
  await ev("__demo.point('Or drop a screenshot')"); await sleep(2200)
  await ev("__demo.point('Check message')")
})
await ev("__demo.click('Check message')")
await skipUntil("location.hash.includes('/report/')", '⏩  {s} s later (sped up)')
await sleep(1500)
await ev('__demo.ensure()')
await scene('msg_report', async () => {
  await ev("__demo.point('High risk')"); await sleep(2000)
  await ev("__demo.scrollTo('Main concerns')"); await sleep(9000)
  await ev("__demo.scrollTo('What you should do')"); await sleep(9000)
  await ev("__demo.click('tab:Forwarded message')"); await sleep(900)
})
// 3. Finfluencer video: audit it live from the home page
await ev(`__demo.click(${JSON.stringify(HOME)})`); await sleep(1500)
await scene('vid_audit', async () => {
  await sleep(2500)
  await ev("__demo.click('tab:YouTube video')"); await sleep(1000)
  await ev(`__demo.type('input[type=url], form input', ${JSON.stringify(VIDEO)}, 40)`); await sleep(700)
  await ev("__demo.click('Audit video')")
  await sleep(9000) // let the progress stages show while the narration explains them
})
await skipUntil("location.hash.includes('/report/') || document.body.innerText.includes('Audit failed')", '⏩  audit finished: {s} s later (sped up)', 900)
if (!(await ev("location.hash.includes('/report/')"))) { console.error('live audit failed'); chrome.kill(); process.exit(2) }
await sleep(2000)
await ev('__demo.ensure()')
fresh = (await ev('location.hash')).split('/report/')[1]
await scene('vid_report', async () => {
  await sleep(2500)
  await ev("__demo.point('Risk score')"); await sleep(4000)
  await ev("__demo.scrollTo('Main concerns')"); await sleep(4000)
  await ev("__demo.point('Guaranteed')")
})
await scene('vid_registry', async () => {
  await ev("__demo.scrollTo('Ask about this video')"); await sleep(300)
  await ev('__demo.scroll(480, 1200)'); await sleep(1200)
  await ev("__demo.point('No SEBI')"); await sleep(5000)
  await ev("__demo.point('Risk disclaimer')")
})
await scene('vid_findings', async () => {
  await ev("__demo.scrollTo('Show weak signals')"); await sleep(2500)
  await ev('__demo.scroll(380, 1600)')
})
// 4. Ask the video
await ev("__demo.scrollTo('Ask about this video')")
await scene('ask', async () => {
  await ev("__demo.point('Ask about this video')"); await sleep(3500)
  await ev("__demo.click('Did they promise guaranteed returns?')")
  await skipUntil("!document.body.innerText.includes('Thinking')", '⏩  {s} s later (sped up)')
  await sleep(800)
})
await scene('ask_refuse', async () => {
  await ev("__demo.point(\"css:input[aria-label^='Ask anything']\")")
  await ev(`__demo.type("input[aria-label^='Ask anything']", 'Should I buy these coins?', 30)`)
  await ev("document.querySelector(\"input[aria-label^='Ask anything']\").form.requestSubmit()")
  await skipUntil("document.body.innerText.includes('Not investment advice')", '⏩  {s} s later (sped up)')
  await sleep(500); await ev("__demo.scrollTo('Not investment advice')")
})
// 5. Hindi
await scene('hindi', async () => {
  await ev('window.scrollTo({top:0, behavior:"smooth"})'); await sleep(900)
  await ev("__demo.click('हिं')"); await sleep(3500)
  await ev("__demo.point('सुनें')"); await sleep(3000)
  await ev("__demo.scrollTo('मुख्य खतरे')")
})
await ev('window.scrollTo({top:0, behavior:"smooth"})'); await sleep(700)
await ev("__demo.click('EN')"); await sleep(800)
// 6. Creator profiles, reached from the Creator tab on the home page
await ev(`__demo.click(${JSON.stringify(HOME)})`); await sleep(1500)
await scene('profile', async () => {
  await sleep(1500)
  await ev("__demo.click('tab:Creator')"); await sleep(1500)
  await ev("__demo.point('css:form input')"); await sleep(2500)
  await ev("__demo.point('tab:8')"); await sleep(2000)
  await ev("__demo.scrollTo('Creator profiles')"); await sleep(1500)
  await ev(`__demo.click('css:a[href="#/profile/${R.badProfile}"]')`); await sleep(3500)
  await ev("__demo.ensure()")
  await ev("__demo.scrollTo('How often red flags appear')"); await sleep(3500)
  await ev("__demo.point('Guaranteed or unrealistic returns')")
})
await ev(`__demo.click(${JSON.stringify(HOME)})`); await sleep(1200)
await scene('profile_good', async () => {
  await ev("__demo.scrollTo('Creator profiles')"); await sleep(800)
  await ev(`__demo.click('css:a[href="#/profile/${R.goodProfile}"]')`); await sleep(3000)
  await ev("__demo.ensure()")
  await ev("__demo.point('Quoted registration number is valid')"); await sleep(3000)
  await ev("__demo.scrollTo('Risk across recent videos')")
})
// 7. Outro
await ev(`__demo.click(${JSON.stringify(HOME)})`); await sleep(1200)
await scene('outro', async () => {
  await sleep(2000)
  await ev("__demo.point('tab:YouTube video')")
})
await ev("__demo.caption('')")
await sleep(1200)
await send('Page.stopScreencast')
markers.end = Date.now() / 1000
writeFileSync(`${out}/frames.json`, JSON.stringify(frames))
writeFileSync(`${out}/markers.json`, JSON.stringify(markers, null, 1))
writeFileSync(`${out}/fresh.txt`, fresh)
console.log('fresh report', fresh, 'frames', frames.length, 'scenes', markers.scenes.length, 'skips', markers.skips.length)
ws.close()
chrome.kill()
