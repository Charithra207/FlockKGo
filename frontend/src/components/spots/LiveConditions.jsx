import { CloudRain, Droplets, Sun, Thermometer } from 'lucide-react'
import { useEffect, useState } from 'react'

/**
 * Live weather + "is the waterfall flowing?" from Open-Meteo (free, no key).
 * Flow is a rough guess from the last 14 days of rain at that spot.
 */
const CODES = {
  0: 'Clear', 1: 'Mostly clear', 2: 'Partly cloudy', 3: 'Cloudy', 45: 'Fog', 48: 'Fog',
  51: 'Drizzle', 53: 'Drizzle', 55: 'Drizzle', 61: 'Light rain', 63: 'Rain', 65: 'Heavy rain',
  80: 'Showers', 81: 'Showers', 82: 'Heavy showers', 95: 'Thunderstorm', 96: 'Thunderstorm', 99: 'Thunderstorm',
}

function flowVerdict(rain14) {
  if (rain14 >= 150) return { text: 'Likely roaring', tone: 'text-sky-700', tip: 'Lots of recent rain. Spectacular, but stay far from the edge.' }
  if (rain14 >= 50) return { text: 'Likely flowing well', tone: 'text-sky-600', tip: 'Good recent rain: a great time to visit.' }
  if (rain14 >= 10) return { text: 'Probably a gentle flow', tone: 'text-emerald-600', tip: 'Some rain recently. It may be thinner than in photos.' }
  return { text: 'Probably a trickle or dry', tone: 'text-amber-600', tip: 'Very little rain lately. Best from June to October.' }
}

export default function LiveConditions({ lat, lng, category }) {
  const [w, setW] = useState(null)
  useEffect(() => {
    if (lat == null || lng == null) return
    const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lng}`
      + '&current=temperature_2m,weather_code,precipitation&daily=precipitation_sum,temperature_2m_max,temperature_2m_min'
      + '&past_days=14&forecast_days=3&timezone=Asia%2FKolkata'
    fetch(url).then((r) => (r.ok ? r.json() : null)).then(setW).catch(() => setW(null))
  }, [lat, lng])
  if (!w?.current || !w?.daily) return null

  const rain = w.daily.precipitation_sum || []
  const past14 = rain.slice(0, 14).reduce((a, b) => a + (b || 0), 0)
  const next3 = rain.slice(14).reduce((a, b) => a + (b || 0), 0)
  const flow = category === 'waterfall' ? flowVerdict(past14) : null
  const today = 14
  const heavySoon = next3 >= 40

  return (
    <div className="rounded-xl bg-sky-50 p-4">
      <p className="mb-2 text-xs font-bold uppercase tracking-wider text-sky-700">Right now there</p>
      <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm text-slate-700">
        <span className="inline-flex items-center gap-1"><Thermometer className="h-4 w-4 text-sky-600" /> {Math.round(w.current.temperature_2m)}°C, {CODES[w.current.weather_code] || 'Mixed'}</span>
        {w.daily.temperature_2m_max?.[today] != null && (
          <span className="inline-flex items-center gap-1"><Sun className="h-4 w-4 text-amber-500" /> {Math.round(w.daily.temperature_2m_min[today])}–{Math.round(w.daily.temperature_2m_max[today])}°C today</span>
        )}
        <span className="inline-flex items-center gap-1"><CloudRain className="h-4 w-4 text-sky-600" /> {Math.round(past14)} mm rain in 2 weeks</span>
      </div>
      {flow && (
        <p className="mt-2 text-sm">
          <Droplets className="mr-1 inline h-4 w-4 text-sky-600" />
          <b className={flow.tone}>{flow.text}.</b> <span className="text-slate-600">{flow.tip}</span>
        </p>
      )}
      {heavySoon && <p className="mt-2 text-sm font-semibold text-red-600">⚠️ Heavy rain forecast in the next 3 days ({Math.round(next3)} mm). Check before you go.</p>}
      <p className="mt-2 text-[10px] text-slate-400">Weather by Open-Meteo.com. Flow is a guess from recent rain.</p>
    </div>
  )
}
