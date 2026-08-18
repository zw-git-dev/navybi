import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { CircleMarker, MapContainer, Popup, TileLayer } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import { api } from '../api/client'
import type { MapData } from '../api/types'
import { Card, ErrorNote, PageHeader, Spinner } from '../components/ui'
import { MultiSelect } from '../components/MultiSelect'
import { colorForCategory } from '../lib/palette'

export function MapPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['map'],
    queryFn: () => api.get<MapData>('/api/dashboard/map'),
  })
  const [selectedStatuses, setSelectedStatuses] = useState<string[] | null>(null)

  const statuses = data?.statuses ?? []
  const activeStatuses = selectedStatuses ?? statuses

  const missions = useMemo(
    () => (data ? data.missions.filter((m) => activeStatuses.includes(m.status)) : []),
    [data, activeStatuses],
  )
  const missingDuration = missions.filter((m) => m.duration_hours === null).length

  if (isLoading) return <Spinner />
  if (error || !data) return <ErrorNote message="Could not load the map." />

  return (
    <div>
      <PageHeader title="Map" caption="Mission locations, colored by status." />

      <div className="mb-4 max-w-sm">
        <MultiSelect label="Status" options={statuses} selected={activeStatuses} onChange={setSelectedStatuses} />
      </div>

      <Card className="overflow-hidden p-0">
        <MapContainer center={[25, -60]} zoom={3} scrollWheelZoom style={{ height: 550, width: '100%' }}>
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {missions.map((m, i) => (
            <CircleMarker
              key={i}
              center={[m.mission_lat, m.mission_lon]}
              radius={m.duration_hours ? Math.min(4 + m.duration_hours / 2, 14) : 4}
              pathOptions={{ color: colorForCategory(m.status), fillColor: colorForCategory(m.status), fillOpacity: 0.7, weight: 1 }}
            >
              <Popup>
                <div className="text-xs">
                  <div className="font-semibold">{m.mission_type}</div>
                  <div>Unit: {m.unit_name}</div>
                  <div>Date: {m.mission_date}</div>
                  <div>Status: {m.status}</div>
                  <div>Duration: {m.duration_hours ?? 'unknown'} hrs</div>
                </div>
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      </Card>

      {missingDuration > 0 && (
        <p className="mt-3 text-xs text-ink-faint">
          {missingDuration} mission(s) shown have no recorded duration and are plotted at a small default marker
          size for visibility only.
        </p>
      )}
    </div>
  )
}
