import api from './api'

export const profileApi = {
  get: (username) => api.get(`/users/${encodeURIComponent(username)}`).then((r) => r.data),
  update: (body) => api.patch('/auth/me', body).then((r) => r.data),
  /** status: 'been' | 'want' | null (remove). Pass spot_id or destination_id. */
  mark: (body) => api.put('/marks', body).then((r) => r.data),
  myMarks: () => api.get('/marks/mine').then((r) => r.data),
  destinations: () => api.get('/places/destinations').then((r) => r.data),
  wrapped: (username, year, month) =>
    api.get(`/users/${encodeURIComponent(username)}/wrapped`, { params: month ? { year, month } : { year } }).then((r) => r.data),
}

export const KARNATAKA_DISTRICTS = [
  'Bagalkot', 'Ballari', 'Belagavi', 'Bengaluru Rural', 'Bengaluru Urban', 'Bengaluru South',
  'Bidar', 'Chamarajanagar', 'Chikkaballapura', 'Chikkamagaluru', 'Chitradurga',
  'Dakshina Kannada', 'Davanagere', 'Dharwad', 'Gadag', 'Hassan', 'Haveri', 'Kalaburagi',
  'Kodagu', 'Kolar', 'Koppal', 'Mandya', 'Mysuru', 'Raichur', 'Shivamogga', 'Tumakuru',
  'Udupi', 'Uttara Kannada', 'Vijayanagara', 'Vijayapura', 'Yadgir',
]

export function profilePath(user) {
  return user?.username ? `/u/${user.username}` : '/me'
}
