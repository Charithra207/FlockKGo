import { ArrowLeft, Camera, Eye, EyeOff, Save, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import Avatar from '../components/profile/Avatar'
import { KARNATAKA_DISTRICTS, profileApi, profilePath } from '../services/profileService'
import { authApi, resizeImage, spotsApi } from '../services/spotsService'
import useAuthStore from '../store/authStore'

const input = 'w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-slate-800 outline-none focus:border-primary focus:ring-2 focus:ring-primary/20'

export default function EditProfile() {
  const { token, user, setUser } = useAuthStore()
  const navigate = useNavigate()
  const [form, setForm] = useState(null)
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)

  useEffect(() => {
    if (!token) return
    authApi.me().then((u) => {
      setUser(u)
      setForm({
        display_name: u.display_name || '',
        username: u.username || '',
        bio: u.bio || '',
        home_district: u.home_district || '',
        avatar_url: u.avatar_url || '',
        profile_public: u.profile_public !== false,
      })
    }).catch((e) => toast.error(e.message))
  }, [token, setUser])

  if (!token) return <Navigate to="/login?next=/settings/profile" replace />
  if (!form) return null

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  async function pickAvatar(e) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setUploading(true)
    try {
      const blob = await resizeImage(file, 512, 0.85)
      const r = await spotsApi.uploadPhoto(blob)
      setForm((f) => ({ ...f, avatar_url: r.url }))
    } catch (err) {
      toast.error(err.message)
    } finally {
      setUploading(false)
    }
  }

  async function save(e) {
    e.preventDefault()
    setSaving(true)
    try {
      const u = await profileApi.update({ ...form, username: form.username.trim().toLowerCase() })
      setUser(u)
      toast.success('Profile saved')
      navigate(profilePath(u))
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={save} className="mx-auto max-w-xl space-y-5">
      <Link to={profilePath(user)} className="inline-flex items-center gap-1 text-sm font-medium text-slate-500 hover:text-primary">
        <ArrowLeft className="h-4 w-4" /> Back to my profile
      </Link>
      <div className="space-y-5 rounded-2xl bg-white p-6 shadow-card">
        <h1 className="text-2xl font-extrabold text-primary">Edit profile</h1>

        <div className="flex items-center gap-4">
          <Avatar user={{ ...user, ...form, avatar_url: form.avatar_url || null }} size={80} />
          <div className="flex flex-wrap gap-2">
            <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-xl bg-slate-100 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-200">
              <Camera className="h-4 w-4" /> {uploading ? 'Uploading…' : 'Change photo'}
              <input type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={pickAvatar} disabled={uploading} />
            </label>
            {form.avatar_url && (
              <button type="button" onClick={() => setForm((f) => ({ ...f, avatar_url: '' }))} className="inline-flex items-center gap-1.5 rounded-xl px-3 py-2 text-sm font-semibold text-slate-500 hover:text-red-600">
                <Trash2 className="h-4 w-4" /> Remove
              </button>
            )}
          </div>
        </div>

        <label className="block space-y-1">
          <span className="text-sm font-semibold text-slate-600">Name</span>
          <input className={input} value={form.display_name} onChange={set('display_name')} maxLength={80} required />
        </label>

        <label className="block space-y-1">
          <span className="text-sm font-semibold text-slate-600">Username</span>
          <div className="flex items-center rounded-xl border border-slate-200 focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20">
            <span className="pl-3 text-slate-400">flockgo/u/</span>
            <input
              className="w-full rounded-xl bg-transparent px-1 py-2.5 font-mono text-slate-800 outline-none"
              value={form.username} onChange={set('username')} maxLength={30} pattern="[a-zA-Z0-9_]{3,30}"
              title="3–30 letters, numbers or _" required
            />
          </div>
          <span className="text-xs text-slate-400">3–30 characters: letters, numbers and _</span>
        </label>

        <label className="block space-y-1">
          <span className="text-sm font-semibold text-slate-600">Bio</span>
          <textarea className={input} rows={3} value={form.bio} onChange={set('bio')} maxLength={200} placeholder="Monsoon chaser. Filter coffee snob. Always up for a sunrise trek." />
          <span className="block text-right text-xs text-slate-400">{form.bio.length}/200</span>
        </label>

        <label className="block space-y-1">
          <span className="text-sm font-semibold text-slate-600">Home district</span>
          <select className={input} value={form.home_district} onChange={set('home_district')}>
            <option value="">Not set</option>
            {KARNATAKA_DISTRICTS.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </label>

        <button
          type="button"
          onClick={() => setForm((f) => ({ ...f, profile_public: !f.profile_public }))}
          className="flex w-full items-center justify-between rounded-xl border border-slate-200 px-4 py-3 text-left hover:bg-slate-50"
        >
          <span>
            <span className="flex items-center gap-2 font-semibold text-slate-700">
              {form.profile_public ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
              {form.profile_public ? 'Public profile' : 'Private profile'}
            </span>
            <span className="text-xs text-slate-500">
              {form.profile_public ? 'Anyone with the link can see your stamps and bucket list.' : 'Only you can see your stamps and bucket list.'}
            </span>
          </span>
          <span className={`relative h-6 w-11 rounded-full transition ${form.profile_public ? 'bg-success' : 'bg-slate-300'}`}>
            <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${form.profile_public ? 'left-[22px]' : 'left-0.5'}`} />
          </span>
        </button>

        <button disabled={saving || uploading} className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-primary py-3 font-bold text-white hover:opacity-90 disabled:opacity-50">
          <Save className="h-4 w-4" /> {saving ? 'Saving…' : 'Save profile'}
        </button>
      </div>
    </form>
  )
}
