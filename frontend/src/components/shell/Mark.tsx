/** Product mark: a camera aperture with one blade cut away (the sentinel's open eye). Drawn, single colour. */
export function Mark({ className = 'size-6' }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden fill="none">
      <rect x="2.5" y="2.5" width="19" height="19" rx="4" stroke="currentColor" strokeWidth="1.6" />
      <path d="M12 6.5a5.5 5.5 0 1 0 5.5 5.5H12V6.5Z" fill="currentColor" />
    </svg>
  )
}
