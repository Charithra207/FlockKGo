/**
 * Minimal EXIF reader for JPEG photos: when it was taken and where.
 * Runs in the browser on the original file (resizing strips EXIF).
 * Returns { takenOn: 'YYYY-MM-DD' | null, lat: number | null, lng: number | null }.
 * The GPS is only sent once to decide "verified"; it is never stored.
 */
export async function readExif(file) {
  const empty = { takenOn: null, lat: null, lng: null }
  try {
    const buf = await file.slice(0, 256 * 1024).arrayBuffer()
    const v = new DataView(buf)
    if (v.getUint16(0) !== 0xffd8) return empty // not a JPEG
    let off = 2
    while (off + 4 < v.byteLength) {
      const marker = v.getUint16(off)
      const size = v.getUint16(off + 2)
      if (marker === 0xffe1 && v.getUint32(off + 4) === 0x45786966) return parseTiff(v, off + 10) // "Exif"
      if ((marker & 0xff00) !== 0xff00) break
      off += 2 + size
    }
  } catch {
    /* unreadable: no EXIF */
  }
  return empty
}

function parseTiff(v, start) {
  const out = { takenOn: null, lat: null, lng: null }
  const le = v.getUint16(start) === 0x4949
  const u16 = (o) => v.getUint16(start + o, le)
  const u32 = (o) => v.getUint32(start + o, le)

  function entries(dirOff) {
    const n = u16(dirOff)
    const list = []
    for (let i = 0; i < n; i++) {
      const e = dirOff + 2 + i * 12
      list.push({ tag: u16(e), type: u16(e + 2), count: u32(e + 4), valOff: e + 8 })
    }
    return list
  }
  const ascii = (e) => {
    const o = e.count > 4 ? u32(e.valOff) : e.valOff
    let s = ''
    for (let i = 0; i < e.count - 1; i++) s += String.fromCharCode(v.getUint8(start + o + i))
    return s
  }
  const rationals = (e) => {
    const o = u32(e.valOff)
    return Array.from({ length: e.count }, (_, i) => u32(o + i * 8) / (u32(o + i * 8 + 4) || 1))
  }

  const ifd0 = entries(u32(4))
  let dateStr = null
  const exifPtr = ifd0.find((e) => e.tag === 0x8769)
  if (exifPtr) {
    const d = entries(u32(exifPtr.valOff)).find((e) => e.tag === 0x9003) // DateTimeOriginal
    if (d) dateStr = ascii(d)
  }
  if (!dateStr) {
    const d = ifd0.find((e) => e.tag === 0x0132) // DateTime
    if (d) dateStr = ascii(d)
  }
  const m = dateStr && /^(\d{4}):(\d{2}):(\d{2})/.exec(dateStr)
  if (m && m[1] !== '0000') out.takenOn = `${m[1]}-${m[2]}-${m[3]}`

  const gpsPtr = ifd0.find((e) => e.tag === 0x8825)
  if (gpsPtr) {
    const g = Object.fromEntries(entries(u32(gpsPtr.valOff)).map((e) => [e.tag, e]))
    if (g[2] && g[4]) {
      const dms = (e) => { const [d, mi, s] = rationals(e); return d + mi / 60 + s / 3600 }
      let lat = dms(g[2])
      let lng = dms(g[4])
      if (g[1] && ascii({ ...g[1], count: 2 }) === 'S') lat = -lat
      if (g[3] && ascii({ ...g[3], count: 2 }) === 'W') lng = -lng
      if (Number.isFinite(lat) && Number.isFinite(lng) && (lat || lng)) {
        out.lat = Math.round(lat * 1e5) / 1e5
        out.lng = Math.round(lng * 1e5) / 1e5
      }
    }
  }
  return out
}
