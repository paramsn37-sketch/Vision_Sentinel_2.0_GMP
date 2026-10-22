// Dev-only catalogue of every primitive in both themes (Phase 7 gate: screenshots of this route).
import { AlertTriangle, Pause, Play, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import {
  Button,
  Checkbox,
  Dialog,
  Drawer,
  EmptyState,
  Field,
  IconButton,
  Input,
  Kbd,
  Metric,
  Panel,
  SegmentedControl,
  Select,
  Skeleton,
  Slider,
  StatusPill,
  Switch,
  Table,
  TabList,
  TabPanel,
  Tabs,
  Td,
  Th,
  Tr,
  Textarea,
} from '@/components/ui'
import { applyTheme } from '@/stores/ui'

const swatches = ['--bg', '--bg-sunken', '--bg-raised', '--bg-hover', '--line', '--line-strong', '--fg', '--fg-muted', '--fg-subtle', '--accent', '--danger', '--warning', '--ok']

export default function DesignPage() {
  const [theme, setTheme] = useState(() => new URLSearchParams(location.search).get('theme') ?? 'dark')
  const [seg, setSeg] = useState<'1' | '2' | '4'>('2')
  const [sw, setSw] = useState(true)
  const [cb, setCb] = useState(false)
  const [sel, setSel] = useState<string | undefined>('hazard')
  const [op, setOp] = useState(0.6)
  const [drawer, setDrawer] = useState(false)
  const [dialog, setDialog] = useState(false)
  applyTheme(theme as 'dark' | 'light')

  return (
    <div className="min-h-full bg-bg p-6 text-fg">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl">Design system</h1>
          <p className="text-muted">Every primitive from DESIGN.md, in the {theme} theme.</p>
        </div>
        <SegmentedControl label="Theme" value={theme} onChange={setTheme} options={[{ value: 'dark', label: 'Dark' }, { value: 'light', label: 'Light' }]} />
      </div>

      <div className="grid grid-cols-1 items-start gap-4 xl:grid-cols-3">
        <Panel title="Colour tokens" bodyClassName="grid grid-cols-4 gap-3 p-4">
          {swatches.map((s) => (
            <div key={s} className="flex flex-col gap-1">
              <div className="h-10 rounded-sm border border-line" style={{ background: `var(${s})` }} />
              <code className="num text-xs text-muted">{s}</code>
            </div>
          ))}
        </Panel>

        <Panel title="Type" bodyClassName="flex flex-col gap-2 p-4">
          <p className="text-2xl font-semibold">Page title 26</p>
          <p className="text-xl">Section title 20</p>
          <p className="text-lg font-semibold">Panel title 16</p>
          <p className="text-md">Control text 14</p>
          <p className="text-sm">Body 13: Person #12 entered the loading bay without a helmet.</p>
          <p className="text-xs text-muted">Caption 12, secondary</p>
          <p className="num text-xl">1,284 · 07:42:13 · inc_8f2a91</p>
        </Panel>

        <Panel title="Metrics" bodyClassName="grid grid-cols-3 gap-4 p-4">
          <Metric label="People now" value={7} unit="people" />
          <Metric label="Unique today" value={142} unit="people" note="since 00:00" />
          <Metric label="Open, high" value={2} tone="danger" note="oldest 6 min" />
        </Panel>

        <Panel title="Buttons" bodyClassName="flex flex-wrap content-start items-center gap-2 p-4">
          <Button variant="primary" icon={<Plus className="size-4" />}>New zone</Button>
          <Button>Acknowledge</Button>
          <Button variant="ghost">Cancel</Button>
          <Button variant="danger" icon={<Trash2 className="size-4" />}>Delete</Button>
          <Button loading>Saving</Button>
          <Button disabled>Disabled</Button>
          <Button size="sm">Small</Button>
          <IconButton label="Pause stream" shortcut="Space"><Pause className="size-4" /></IconButton>
          <IconButton label="Play" active><Play className="size-4" /></IconButton>
          <Kbd>a</Kbd>
          <Kbd>⌘K</Kbd>
        </Panel>

        <Panel title="Form controls" bodyClassName="flex flex-col gap-4 p-4">
          <Field label="Zone name" hint="Shown on alerts and reports.">{(p) => <Input {...p} defaultValue="Loading bay" />}</Field>
          <Field label="Max occupancy" error="Enter a whole number of people, 0 or more.">{(p) => <Input {...p} defaultValue="-2" />}</Field>
          <Field label="Note">{(p) => <Textarea {...p} placeholder="What did you check?" />}</Field>
          <div className="flex items-center gap-4">
            <Select label="Zone kind" value={sel} onChange={setSel} options={[{ value: 'restricted', label: 'No entry' }, { value: 'ppe_required', label: 'PPE required' }, { value: 'hazard', label: 'Hazard area' }]} />
            <Switch label="Enabled" checked={sw} onChange={setSw} />
            <Checkbox label="Helmet" checked={cb} onChange={setCb} />
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-muted">Overlay</span>
            <Slider label="Overlay opacity" value={op} onChange={setOp} />
            <span className="num w-10 text-right text-xs">{Math.round(op * 100)}%</span>
          </div>
        </Panel>

        <Panel title="Selection and status" bodyClassName="flex flex-col gap-4 p-4">
          <SegmentedControl label="Layout" value={seg} onChange={setSeg} options={[{ value: '1', label: '1 camera' }, { value: '2', label: '2' }, { value: '4', label: '2 × 2' }]} />
          <Tabs defaultValue="evidence">
            <TabList tabs={[{ value: 'evidence', label: 'Evidence' }, { value: 'explain', label: 'Explanation' }, { value: 'timeline', label: 'Timeline' }]} />
            <TabPanel value="evidence" className="pt-3 text-muted">Tab content</TabPanel>
          </Tabs>
          <div className="flex flex-wrap gap-2">
            <StatusPill tone="danger">Open</StatusPill>
            <StatusPill tone="warning">Acknowledged</StatusPill>
            <StatusPill tone="ok">Compliant</StatusPill>
            <StatusPill tone="info">Running</StatusPill>
            <StatusPill tone="neutral">Resolved</StatusPill>
          </div>
        </Panel>

        <Panel title="Table" className="xl:col-span-2" bodyClassName="overflow-auto">
          <Table>
            <thead>
              <tr><Th>Rule</Th><Th>Zone</Th><Th>Status</Th><Th align="right">Duration</Th><Th align="right">Started</Th></tr>
            </thead>
            <tbody>
              <Tr selected><Td>Entered no-entry zone</Td><Td>Vehicle lane</Td><Td><StatusPill tone="danger">Open</StatusPill></Td><Td align="right">1m 12s</Td><Td align="right">07:42:13</Td></Tr>
              <Tr><Td>Missing helmet</Td><Td>Site floor</Td><Td><StatusPill tone="warning">Acknowledged</StatusPill></Td><Td align="right">24s</Td><Td align="right">07:39:02</Td></Tr>
              <Tr><Td>Zone over capacity</Td><Td>Square centre</Td><Td><StatusPill tone="neutral">Resolved</StatusPill></Td><Td align="right">3m 05s</Td><Td align="right">07:12:55</Td></Tr>
            </tbody>
          </Table>
        </Panel>

        <Panel title="Feedback" bodyClassName="flex flex-col gap-3 p-4">
          <div className="flex gap-2">
            <Button onClick={() => toast.error('Entered no-entry zone', { description: 'Vehicle lane · person #12', action: { label: 'Open', onClick: () => undefined } })}>Toast</Button>
            <Button onClick={() => setDrawer(true)}>Drawer</Button>
            <Button onClick={() => setDialog(true)}>Dialog</Button>
          </div>
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
          <EmptyState icon={<AlertTriangle className="size-5" />} title="No open incidents" action={<Button size="sm">Show resolved</Button>}>
            Cameras are running. New incidents appear here as they open.
          </EmptyState>
        </Panel>
      </div>

      <Drawer open={drawer} onOpenChange={setDrawer} title="Entered no-entry zone" description="inc_8f2a91 · Vehicle lane" footer={<><Button variant="primary">Acknowledge</Button><Button>Resolve</Button></>}>
        <div className="p-5 text-muted">Drawer body</div>
      </Drawer>
      <Dialog open={dialog} onOpenChange={setDialog} title="Delete zone?" description="Loading bay will stop raising incidents. Past incidents stay in the log." footer={<><Button variant="ghost" onClick={() => setDialog(false)}>Cancel</Button><Button variant="danger">Delete zone</Button></>}>
        <p className="text-sm text-muted">This cannot be undone.</p>
      </Dialog>
    </div>
  )
}
