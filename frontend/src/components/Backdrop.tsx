/** The scene behind the glass: large soft colour fields plus fine grain.
 *  Glass needs something to refract; without it, "liquid glass" reads as plain grey.
 *  The fields are static radial gradients (no blur filter, no animation): an animated, blurred
 *  backdrop makes every glass card re-blur on every frame, which made phones lag. */
export default function Backdrop() {
  const blob = 'absolute rounded-full'
  const field = (color: string, opacity = 'var(--blob-opacity)') => ({
    background: `radial-gradient(closest-side, ${color}, transparent)`, opacity,
  })
  return (
    <div aria-hidden className="no-print pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div className={`${blob} -top-[30vh] -left-[20vw] h-[90vh] w-[90vh]`} style={field('var(--blob-a)')} />
      <div className={`${blob} -top-[5vh] -right-[25vw] h-[100vh] w-[100vh]`} style={field('var(--blob-b)')} />
      <div className={`${blob} -bottom-[40vh] left-[10vw] h-[95vh] w-[95vh]`} style={field('var(--blob-c)')} />
      <div className={`${blob} -bottom-[10vh] -right-[15vw] h-[65vh] w-[65vh]`} style={field('var(--blob-d)', 'calc(var(--blob-opacity) * .7)')} />
      {/* Grain keeps large gradients from banding and gives the glass a material feel. */}
      <svg className="absolute inset-0 h-full w-full opacity-[.035]">
        <filter id="grain"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" stitchTiles="stitch" /></filter>
        <rect width="100%" height="100%" filter="url(#grain)" />
      </svg>
    </div>
  )
}
