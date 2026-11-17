# FlockGo — frontend

React 18 + Vite + Tailwind + react-leaflet. See the [main README](../README.md) for the full project and [DEPLOY.md](../DEPLOY.md) for hosting.

```bash
npm install
npm run dev      # http://localhost:5173 — /v1 is proxied to the API on :8000
npm run build    # production build into dist/
```

| Path | Page |
|---|---|
| `/` | Home |
| `/explore` | Karnataka spot map + filters |
| `/spots/share`, `/spots/:id/edit` | Share or edit a spot |
| `/spots/:id` | Spot detail (locked / unlocked) |
| `/login`, `/me` | Account, my spots and credits |
| `/admin/spots` | Review queue (admins) |
| `/create`, `/trip/:id`, `/survey/:token` | Group trip planning |
| `/trip/:id/recs`, `/vote`, `/results` | Recommendations, voting, results |
| `/trip/:id/plan` | Trip companion: packing, expenses, itinerary, travel, SOS |

Environment variables (Vercel): `VITE_API_URL`, `VITE_API_KEY`. See `.env.example`.

Code map:
- `src/services/api.js`: axios client (API key, login token, friendly errors, wake-up ping)
- `src/services/spotsService.js`: spots, auth, photo upload helpers
- `src/i18n.js`: English + Kannada strings
