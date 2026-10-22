import { create } from 'zustand'

type Theme = 'dark' | 'light'

const read = <T,>(k: string, d: T): T => {
  try {
    const v = localStorage.getItem(k)
    return v ? (JSON.parse(v) as T) : d
  } catch {
    return d
  }
}
const write = (k: string, v: unknown) => {
  try {
    localStorage.setItem(k, JSON.stringify(v))
  } catch {
    /* storage unavailable */
  }
}

interface UIState {
  theme: Theme
  railOpen: boolean
  paletteOpen: boolean
  setTheme: (t: Theme) => void
  toggleRail: () => void
  setPalette: (v: boolean) => void
}

export const applyTheme = (t: Theme) => document.documentElement.setAttribute('data-theme', t)

export const useUI = create<UIState>((set) => ({
  theme: read<Theme>('vs.theme', 'dark'),
  railOpen: read('vs.rail', false),
  paletteOpen: false,
  setTheme: (theme) => {
    write('vs.theme', theme)
    applyTheme(theme)
    set({ theme })
  },
  toggleRail: () =>
    set((s) => {
      write('vs.rail', !s.railOpen)
      return { railOpen: !s.railOpen }
    }),
  setPalette: (paletteOpen) => set({ paletteOpen }),
}))
