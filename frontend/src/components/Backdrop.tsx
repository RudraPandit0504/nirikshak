/** The scene behind the glass: large, softly drifting colour fields plus fine grain.
 *  Glass needs something to refract; without it, "liquid glass" reads as plain grey. */
export default function Backdrop() {
  const blob = 'absolute rounded-full blur-[110px] will-change-transform'
  return (
    <div aria-hidden className="no-print pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div className={`${blob} -top-[20vh] -left-[10vw] h-[60vh] w-[60vh] animate-drift-1`}
        style={{ background: 'var(--blob-a)', opacity: 'var(--blob-opacity)' }} />
      <div className={`${blob} top-[10vh] -right-[15vw] h-[70vh] w-[70vh] animate-drift-2`}
        style={{ background: 'var(--blob-b)', opacity: 'var(--blob-opacity)' }} />
      <div className={`${blob} -bottom-[25vh] left-[20vw] h-[65vh] w-[65vh] animate-drift-3`}
        style={{ background: 'var(--blob-c)', opacity: 'var(--blob-opacity)' }} />
      <div className={`${blob} bottom-[5vh] -right-[5vw] h-[40vh] w-[40vh] animate-drift-1`}
        style={{ background: 'var(--blob-d)', opacity: 'calc(var(--blob-opacity) * .7)', animationDelay: '-12s' }} />
      {/* Grain keeps large gradients from banding and gives the glass a material feel. */}
      <svg className="absolute inset-0 h-full w-full opacity-[.035] mix-blend-overlay">
        <filter id="grain"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" stitchTiles="stitch" /></filter>
        <rect width="100%" height="100%" filter="url(#grain)" />
      </svg>
    </div>
  )
}
