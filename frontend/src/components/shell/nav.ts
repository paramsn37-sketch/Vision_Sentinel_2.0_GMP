import { ChartLine, Cpu, MonitorPlay, PenTool, Settings, Siren, Upload } from 'lucide-react'

export const NAV = [
  { to: '/live', label: 'Live', icon: MonitorPlay, key: '1' },
  { to: '/incidents', label: 'Incidents', icon: Siren, key: '2' },
  { to: '/zones', label: 'Zones', icon: PenTool, key: '3' },
  { to: '/analytics', label: 'Analytics', icon: ChartLine, key: '4' },
  { to: '/uploads', label: 'Uploads', icon: Upload, key: '5' },
  { to: '/model', label: 'Model', icon: Cpu, key: '6' },
  { to: '/settings', label: 'Settings', icon: Settings, key: '7' },
] as const
