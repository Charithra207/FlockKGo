import { useEffect } from 'react'
import { Circle, CircleMarker, MapContainer, TileLayer, Tooltip, useMap, useMapEvents } from 'react-leaflet'
import { useNavigate } from 'react-router-dom'
import { CATEGORY_META, spotTitle } from '../../services/spotsService'

export const KARNATAKA_CENTER = [14.6, 76.1]

const CATEGORY_COLORS = {
  cafe: '#b45309', viewpoint: '#7c3aed', waterfall: '#0284c7', trek: '#15803d',
  beach: '#0891b2', lake: '#2563eb', temple: '#c2410c', heritage: '#a16207',
  food: '#dc2626', stay: '#db2777', wildlife: '#4d7c0f', other: '#475569',
}

export function categoryColor(c) {
  return CATEGORY_COLORS[c] || CATEGORY_COLORS.other
}

function FlyTo({ center, zoom }) {
  const map = useMap()
  useEffect(() => {
    if (center) map.flyTo(center, zoom ?? map.getZoom(), { duration: 0.8 })
  }, [center?.[0], center?.[1], zoom]) // eslint-disable-line react-hooks/exhaustive-deps
  return null
}

function ClickToPick({ onPick }) {
  useMapEvents({
    click(e) {
      onPick?.([Number(e.latlng.lat.toFixed(6)), Number(e.latlng.lng.toFixed(6))])
    },
  })
  return null
}

/**
 * Map of Karnataka.
 *  spots   — items from /v1/spots (locked ones have approx_latitude/longitude only)
 *  hubs    — destinations from /v1/spots/meta (drawn as small grey dots)
 *  pick    — [lat, lng] currently picked (location-picker mode)
 *  onPick  — enables click-to-pick
 */
export default function SpotMap({
  spots = [], hubs = [], center, zoom = 7, height = 460, pick, onPick, focus,
}) {
  const navigate = useNavigate()

  return (
    <div className="relative z-0 overflow-hidden rounded-2xl shadow-card" style={{ height }}>
      <MapContainer
        center={center || KARNATAKA_CENTER}
        zoom={zoom}
        scrollWheelZoom
        style={{ height: '100%', width: '100%' }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {focus && <FlyTo center={focus.center} zoom={focus.zoom} />}
        {onPick && <ClickToPick onPick={onPick} />}

        {hubs.map((h) => (
          <CircleMarker
            key={`hub-${h.id}`}
            center={[h.latitude, h.longitude]}
            radius={4}
            pathOptions={{ color: '#1E3A5F', weight: 1, fillOpacity: 0.5 }}
          >
            <Tooltip>{h.name}</Tooltip>
          </CircleMarker>
        ))}

        {spots.map((s) => {
          const color = categoryColor(s.category)
          const meta = CATEGORY_META[s.category] || CATEGORY_META.other
          if (s.locked) {
            return (
              <Circle
                key={s.id}
                center={[s.approx_latitude, s.approx_longitude]}
                radius={5000}
                pathOptions={{ color, dashArray: '6 6', weight: 2, fillOpacity: 0.12 }}
                eventHandlers={{ click: () => navigate(`/spots/${s.id}`) }}
              >
                <Tooltip>🔒 {spotTitle(s)}</Tooltip>
              </Circle>
            )
          }
          return (
            <CircleMarker
              key={s.id}
              center={[s.latitude, s.longitude]}
              radius={s.featured ? 9 : 7}
              pathOptions={{ color: '#fff', weight: 2, fillColor: color, fillOpacity: 0.95 }}
              eventHandlers={{ click: () => navigate(`/spots/${s.id}`) }}
            >
              <Tooltip>{meta.emoji} {s.name}</Tooltip>
            </CircleMarker>
          )
        })}

        {pick && (
          <CircleMarker
            center={pick}
            radius={10}
            pathOptions={{ color: '#fff', weight: 3, fillColor: '#FF6B6B', fillOpacity: 1 }}
          >
            <Tooltip permanent direction="top">Your spot</Tooltip>
          </CircleMarker>
        )}
      </MapContainer>
    </div>
  )
}
