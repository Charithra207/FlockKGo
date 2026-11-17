import { MessageCircle, Send } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import toast from 'react-hot-toast'
import api from '../../services/api'
import useAuthStore from '../../store/authStore'
import Avatar from '../profile/Avatar'

/** Simple trip chat, so decisions don't get buried in WhatsApp. Polls every 8 s. */
export default function TripNotes({ tripId }) {
  const { token, user } = useAuthStore()
  const [items, setItems] = useState([])
  const [text, setText] = useState('')
  const [name, setName] = useState(() => {
    try { return localStorage.getItem('flockgo-chat-name') || '' } catch { return '' }
  })
  const [busy, setBusy] = useState(false)
  const lastId = useRef(0)
  const box = useRef(null)

  useEffect(() => {
    let alive = true
    const poll = () => api.get(`/trips/${tripId}/comments`, { params: { after: lastId.current } }).then((r) => {
      if (!alive || !r.data.items.length) return
      lastId.current = r.data.items[r.data.items.length - 1].id
      setItems((xs) => [...xs, ...r.data.items])
      setTimeout(() => box.current?.scrollTo({ top: box.current.scrollHeight, behavior: 'smooth' }), 50)
    }).catch(() => {})
    poll()
    const t = setInterval(poll, 8000)
    return () => { alive = false; clearInterval(t) }
  }, [tripId])

  async function send(e) {
    e.preventDefault()
    if (!text.trim()) return
    if (!token && !name.trim()) return toast.error('Add your name first')
    setBusy(true)
    try {
      await api.post(`/trips/${tripId}/comments`, { text: text.trim(), author_name: token ? undefined : name.trim() })
      try { if (!token) localStorage.setItem('flockgo-chat-name', name.trim()) } catch { /* ignore */ }
      setText('')
      const r = await api.get(`/trips/${tripId}/comments`, { params: { after: lastId.current } })
      if (r.data.items.length) {
        lastId.current = r.data.items[r.data.items.length - 1].id
        setItems((xs) => [...xs, ...r.data.items])
        setTimeout(() => box.current?.scrollTo({ top: box.current.scrollHeight, behavior: 'smooth' }), 50)
      }
    } catch (err) {
      toast.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="rounded-2xl bg-white p-5 shadow-card">
      <h2 className="mb-3 flex items-center gap-2 text-lg font-bold text-primary"><MessageCircle className="h-5 w-5" /> Trip notes</h2>
      <div ref={box} className="max-h-80 space-y-3 overflow-y-auto pr-1">
        {items.length === 0 && <p className="text-sm text-slate-400">Who's driving? Where do we meet? Keep the plan here so it doesn't get lost in the group chat.</p>}
        {items.map((c) => {
          const mine = token && user && c.username && c.username === user.username
          return (
            <div key={c.id} className={`flex items-start gap-2 ${mine ? 'flex-row-reverse text-right' : ''}`}>
              <Avatar user={{ display_name: c.author_name, username: c.username || c.author_name, avatar_url: c.avatar_url }} size={28} />
              <div className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm ${mine ? 'bg-primary text-white' : 'bg-slate-100 text-slate-700'}`}>
                <p className={`text-[11px] font-bold ${mine ? 'text-white/70' : 'text-slate-500'}`}>{c.author_name}</p>
                <p className="whitespace-pre-line">{c.text}</p>
              </div>
            </div>
          )
        })}
      </div>
      <form onSubmit={send} className="mt-3 flex flex-wrap gap-2">
        {!token && (
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} placeholder="Your name"
            className="w-32 rounded-xl border border-slate-200 px-3 py-2 text-sm" />
        )}
        <input value={text} onChange={(e) => setText(e.target.value)} maxLength={1000} placeholder="Write a note…"
          className="min-w-0 flex-1 rounded-xl border border-slate-200 px-3 py-2 text-sm focus:border-primary focus:outline-none" />
        <button disabled={busy} className="rounded-xl bg-primary px-4 py-2 text-white disabled:opacity-50" aria-label="Send"><Send className="h-4 w-4" /></button>
      </form>
    </section>
  )
}
