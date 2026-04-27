import { useState } from 'react'

export default function ExclusionInput({ label, values, setValues }) {
  const [value, setValue] = useState('')
  return (
    <div>
      <label className="mb-2 block text-sm font-semibold">{label}</label>
      <input value={value} onChange={(e) => setValue(e.target.value)} onKeyDown={(e) => {
        if (e.key === 'Enter' && value.trim()) {
          e.preventDefault()
          setValues([...values, value.trim()])
          setValue('')
        }
      }} className="w-full rounded-xl border p-3" placeholder="Type destination and press Enter" />
      <div className="mt-2 flex flex-wrap gap-2">
        {values.map((item) => (
          <button key={item} onClick={() => setValues(values.filter((v) => v !== item))} className="rounded-full bg-slate-200 px-3 py-1 text-xs">{item} x</button>
        ))}
      </div>
    </div>
  )
}
