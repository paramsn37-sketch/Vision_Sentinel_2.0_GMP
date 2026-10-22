// Heat colours for explanations: a perceptual dark-blue → teal → yellow → white ramp (close to "cividis"/"viridis"
// end-points, colour-blind safe). Lookup table of 256 RGB triples.
const STOPS: [number, [number, number, number]][] = [
  [0, [13, 8, 60]],
  [0.25, [33, 82, 140]],
  [0.5, [32, 146, 140]],
  [0.75, [148, 200, 70]],
  [0.9, [250, 230, 60]],
  [1, [255, 255, 230]],
]

export const LUT: Uint8ClampedArray = (() => {
  const lut = new Uint8ClampedArray(256 * 3)
  for (let i = 0; i < 256; i++) {
    const t = i / 255
    let k = 0
    while (k < STOPS.length - 2 && t > STOPS[k + 1][0]) k++
    const [t0, c0] = STOPS[k]
    const [t1, c1] = STOPS[k + 1]
    const u = (t - t0) / (t1 - t0)
    for (let j = 0; j < 3; j++) lut[i * 3 + j] = c0[j] + (c1[j] - c0[j]) * u
  }
  return lut
})()

/** Colour a grey heatmap in place; alpha follows heat so cold areas stay transparent. */
export function colorize(data: Uint8ClampedArray, opacity: number): void {
  for (let i = 0; i < data.length; i += 4) {
    const v = data[i]
    data[i] = LUT[v * 3]
    data[i + 1] = LUT[v * 3 + 1]
    data[i + 2] = LUT[v * 3 + 2]
    data[i + 3] = Math.round(Math.min(1, (v / 255) * 1.6) * opacity * 255)
  }
}
