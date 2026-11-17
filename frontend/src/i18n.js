/**
 * i18n.js — English / Kannada strings for the Karnataka-facing screens.
 *
 * Usage:  const t = useT();  t('nav.explore')   t('explore.count', { n: 5 })
 * Missing Kannada keys fall back to English. Please have a native speaker
 * review the Kannada before launch: it's all in this one file.
 */
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

const en = {
  'nav.explore': 'Explore',
  'nav.share': 'Share a spot',
  'nav.login': 'Log in',
  'nav.plan': 'Plan a trip',
  'mark.stamp': 'Stamp my passport',
  'mark.stamped': 'Been here',
  'mark.unstamp': 'Remove stamp',
  'mark.want': 'Bucket list',
  'mark.onList': 'On my list',
  'mark.unwant': 'Remove from bucket list',

  'cat.cafe': 'Cafe', 'cat.viewpoint': 'Viewpoint', 'cat.waterfall': 'Waterfall', 'cat.trek': 'Trek',
  'cat.beach': 'Beach', 'cat.lake': 'Lake', 'cat.temple': 'Temple', 'cat.heritage': 'Heritage',
  'cat.food': 'Local food', 'cat.stay': 'Stay', 'cat.wildlife': 'Wildlife', 'cat.other': 'Other',

  'home.kicker': 'Karnataka, by locals',
  'home.title': 'Give a hidden spot, get a hidden spot',
  'home.body': 'Secret viewpoints, monsoon falls, the cafe only the town knows. Share one place you love and unlock three that other locals shared.',
  'home.explore': 'Explore the map',
  'home.share': 'Share a spot',
  'home.step1': 'Sign up and get 1 free unlock',
  'home.step2': 'Share a place you have been to: +3 unlocks when approved',
  'home.step3': 'Spend 1 unlock to see a hidden spot’s exact location and directions',
  'home.step4': 'Vouch for spots you visit so others know they are real',

  'explore.kicker': 'Explore Karnataka',
  'explore.title': 'Spots only locals know',
  'explore.body': '{hidden} shared by people who have been there, plus cafes, falls and viewpoints across all 31 districts.',
  'explore.hiddenN': '{n} hidden gems',
  'explore.hidden': 'Hidden gems',
  'explore.shareCta': 'Share a spot, unlock 3',
  'explore.credits': '{n} unlock credits',
  'explore.signup': 'Sign up free: your first unlock is on us',
  'explore.all': 'All',
  'explore.search': 'Search cafes, districts…',
  'explore.allDistricts': 'All districts',
  'explore.vis.all': 'Everything',
  'explore.vis.hidden': '🔒 Hidden gems',
  'explore.vis.public': 'Open to all',
  'explore.near': 'Near me',
  'explore.count': '{n} spots',
  'explore.within': 'within 60 km',
  'explore.loading': 'Finding spots…',
  'explore.emptyTitle': 'Nothing here yet',
  'explore.emptyBody': 'Know a place that should be on this map? Be the first to share it.',

  'card.famous': 'Famous',
  'card.unlockHint': 'Unlock with 1 credit to see where it is',
  'card.hiddenName': 'Hidden {cat} near {place}',

  'spot.back': 'Back',
  'spot.edit': 'Edit',
  'spot.lockedTitle': 'A local shared this hidden {cat}.',
  'spot.lockedBody': 'Unlock it to see the name, exact location, photos and how to get there.',
  'spot.confirmed': '{n} people confirmed it is real.',
  'spot.unlock': 'Unlock for 1 credit ({n} left)',
  'spot.earn': 'Share a spot to earn 3 unlocks',
  'spot.signup': 'Sign up: first unlock is free',
  'spot.howTo': 'How to get there',
  'spot.hours': 'Hours',
  'spot.directions': 'Directions',
  'spot.vouch': "I've been here",
  'spot.vouched': 'You vouched',
  'spot.permit': 'Needs a forest / entry permit. Book before you go.',
  'spot.confirmedBy': '{n} people confirmed this spot',
  'spot.respect': "🌱 This is a hidden spot. Please don't post the exact location publicly, carry your trash back, and respect the locals.",
  'spot.cafesNearby': '☕ Cafes nearby',
  'spot.moreHidden': '🔒 More hidden gems around here',

  'share.title': 'Share a spot',
  'share.editTitle': 'Edit spot',
  'share.intro': "Only places you've personally been to, please. Once it's approved you earn {n} unlocks.",
  'share.pin': 'Tap the map to drop the exact pin',
  'share.here': "I'm here now",
  'share.name': 'Name',
  'share.type': 'Type',
  'share.district': 'District',
  'share.choose': 'Choose…',
  'share.special': 'What makes it special?',
  'share.access': 'How to get there',
  'share.months': 'Best months',
  'share.photo': 'Photo (your own)',
  'share.addPhoto': 'Add a photo',
  'share.tags': 'Tags',
  'share.hidden': 'Hidden gem: only people who unlock it see where it is',
  'share.permit': 'Needs a forest / entry permit',
  'share.rules': "Don't share private property without permission or places that are unsafe or closed to visitors.",
  'share.submit': 'Submit for review',
  'share.save': 'Save changes',
  'share.gateTitle': 'Give a spot, get a spot',
  'share.gateBody': "Share a hidden place you've been to. When it's approved you earn 3 unlocks to discover other people's secret spots.",
  'share.gateCta': 'Log in or sign up',

  'login.signup': 'Sign up',
  'login.login': 'Log in',
  'login.name': 'Your name',
  'login.email': 'Email',
  'login.password': 'Password',
  'login.min': 'At least 8 characters',
  'login.create': 'Create account',
  'login.free': 'Your first hidden-spot unlock is free.',

  'footer.tag': 'Group travel, decided by AI. Made for Karnataka.',
}

const kn = {
  'nav.explore': 'ಅನ್ವೇಷಿಸಿ',
  'nav.share': 'ಸ್ಥಳ ಹಂಚಿಕೊಳ್ಳಿ',
  'nav.login': 'ಲಾಗಿನ್',
  'nav.plan': 'ಪ್ರವಾಸ ಯೋಜಿಸಿ',
  'mark.stamp': 'ಪಾಸ್‌ಪೋರ್ಟ್‌ಗೆ ಮುದ್ರೆ',
  'mark.stamped': 'ಇಲ್ಲಿಗೆ ಹೋಗಿದ್ದೇನೆ',
  'mark.want': 'ಹೋಗಬೇಕಾದ ಪಟ್ಟಿ',
  'mark.onList': 'ಪಟ್ಟಿಯಲ್ಲಿದೆ',

  'cat.cafe': 'ಕೆಫೆ', 'cat.viewpoint': 'ವೀಕ್ಷಣಾ ಸ್ಥಳ', 'cat.waterfall': 'ಜಲಪಾತ', 'cat.trek': 'ಚಾರಣ',
  'cat.beach': 'ಕಡಲತೀರ', 'cat.lake': 'ಕೆರೆ', 'cat.temple': 'ದೇವಸ್ಥಾನ', 'cat.heritage': 'ಪಾರಂಪರಿಕ ತಾಣ',
  'cat.food': 'ಸ್ಥಳೀಯ ಊಟ', 'cat.stay': 'ವಸತಿ', 'cat.wildlife': 'ವನ್ಯಜೀವಿ', 'cat.other': 'ಇತರೆ',

  'home.kicker': 'ಕರ್ನಾಟಕ, ಸ್ಥಳೀಯರ ಕಣ್ಣಲ್ಲಿ',
  'home.title': 'ಒಂದು ರಹಸ್ಯ ತಾಣ ಕೊಡಿ, ಇನ್ನೊಂದು ಪಡೆಯಿರಿ',
  'home.body': 'ರಹಸ್ಯ ವೀಕ್ಷಣಾ ಸ್ಥಳಗಳು, ಮಳೆಗಾಲದ ಜಲಪಾತಗಳು, ಊರಿನವರಿಗೆ ಮಾತ್ರ ಗೊತ್ತಿರುವ ಕೆಫೆ. ನಿಮಗೆ ಇಷ್ಟವಾದ ಒಂದು ಸ್ಥಳ ಹಂಚಿಕೊಳ್ಳಿ, ಬೇರೆಯವರು ಹಂಚಿಕೊಂಡ ಮೂರು ಸ್ಥಳಗಳನ್ನು ತೆರೆಯಿರಿ.',
  'home.explore': 'ನಕ್ಷೆ ನೋಡಿ',
  'home.share': 'ಸ್ಥಳ ಹಂಚಿಕೊಳ್ಳಿ',
  'home.step1': 'ಸೈನ್ ಅಪ್ ಮಾಡಿ, 1 ಉಚಿತ ಅನ್‌ಲಾಕ್ ಪಡೆಯಿರಿ',
  'home.step2': 'ನೀವು ಹೋಗಿರುವ ಸ್ಥಳ ಹಂಚಿಕೊಳ್ಳಿ: ಅನುಮೋದನೆಯಾದರೆ +3 ಅನ್‌ಲಾಕ್',
  'home.step3': '1 ಅನ್‌ಲಾಕ್ ಬಳಸಿ ರಹಸ್ಯ ತಾಣದ ನಿಖರ ಸ್ಥಳ ಮತ್ತು ದಾರಿ ನೋಡಿ',
  'home.step4': 'ನೀವು ಭೇಟಿ ನೀಡಿದ ಸ್ಥಳಗಳನ್ನು ದೃಢೀಕರಿಸಿ, ಇತರರಿಗೆ ನಂಬಿಕೆ ಬರಲಿ',

  'explore.kicker': 'ಕರ್ನಾಟಕ ಅನ್ವೇಷಿಸಿ',
  'explore.title': 'ಸ್ಥಳೀಯರಿಗೆ ಮಾತ್ರ ಗೊತ್ತಿರುವ ತಾಣಗಳು',
  'explore.body': 'ಅಲ್ಲಿಗೆ ಹೋಗಿ ಬಂದವರು ಹಂಚಿಕೊಂಡ {hidden}, ಜೊತೆಗೆ 31 ಜಿಲ್ಲೆಗಳ ಕೆಫೆಗಳು, ಜಲಪಾತಗಳು ಮತ್ತು ವೀಕ್ಷಣಾ ಸ್ಥಳಗಳು.',
  'explore.hiddenN': '{n} ರಹಸ್ಯ ತಾಣಗಳು',
  'explore.hidden': 'ರಹಸ್ಯ ತಾಣಗಳು',
  'explore.shareCta': 'ಒಂದು ಹಂಚಿಕೊಳ್ಳಿ, 3 ತೆರೆಯಿರಿ',
  'explore.credits': '{n} ಅನ್‌ಲಾಕ್ ಕ್ರೆಡಿಟ್',
  'explore.signup': 'ಉಚಿತ ಸೈನ್ ಅಪ್: ಮೊದಲ ಅನ್‌ಲಾಕ್ ನಮ್ಮಿಂದ',
  'explore.all': 'ಎಲ್ಲಾ',
  'explore.search': 'ಕೆಫೆ, ಜಿಲ್ಲೆ ಹುಡುಕಿ…',
  'explore.allDistricts': 'ಎಲ್ಲಾ ಜಿಲ್ಲೆಗಳು',
  'explore.vis.all': 'ಎಲ್ಲವೂ',
  'explore.vis.hidden': '🔒 ರಹಸ್ಯ ತಾಣಗಳು',
  'explore.vis.public': 'ಎಲ್ಲರಿಗೂ ತೆರೆದಿರುವವು',
  'explore.near': 'ನನ್ನ ಹತ್ತಿರ',
  'explore.count': '{n} ತಾಣಗಳು',
  'explore.within': '60 ಕಿ.ಮೀ. ಒಳಗೆ',
  'explore.loading': 'ತಾಣಗಳನ್ನು ಹುಡುಕುತ್ತಿದೆ…',
  'explore.emptyTitle': 'ಇಲ್ಲಿ ಇನ್ನೂ ಏನೂ ಇಲ್ಲ',
  'explore.emptyBody': 'ಈ ನಕ್ಷೆಯಲ್ಲಿ ಇರಬೇಕಾದ ಸ್ಥಳ ಗೊತ್ತೇ? ಮೊದಲು ನೀವೇ ಹಂಚಿಕೊಳ್ಳಿ.',

  'card.famous': 'ಪ್ರಸಿದ್ಧ',
  'card.unlockHint': 'ಎಲ್ಲಿದೆ ಎಂದು ನೋಡಲು 1 ಕ್ರೆಡಿಟ್ ಬಳಸಿ',
  'card.hiddenName': '{place} ಬಳಿಯ ರಹಸ್ಯ {cat}',

  'spot.back': 'ಹಿಂದೆ',
  'spot.edit': 'ತಿದ್ದಿ',
  'spot.lockedTitle': 'ಒಬ್ಬ ಸ್ಥಳೀಯರು ಈ ರಹಸ್ಯ {cat} ಹಂಚಿಕೊಂಡಿದ್ದಾರೆ.',
  'spot.lockedBody': 'ಹೆಸರು, ನಿಖರ ಸ್ಥಳ, ಫೋಟೋ ಮತ್ತು ಹೋಗುವ ದಾರಿ ನೋಡಲು ಅನ್‌ಲಾಕ್ ಮಾಡಿ.',
  'spot.confirmed': '{n} ಜನ ಇದು ನಿಜವೆಂದು ದೃಢೀಕರಿಸಿದ್ದಾರೆ.',
  'spot.unlock': '1 ಕ್ರೆಡಿಟ್‌ಗೆ ಅನ್‌ಲಾಕ್ ಮಾಡಿ ({n} ಉಳಿದಿವೆ)',
  'spot.earn': 'ಸ್ಥಳ ಹಂಚಿಕೊಂಡು 3 ಅನ್‌ಲಾಕ್ ಪಡೆಯಿರಿ',
  'spot.signup': 'ಸೈನ್ ಅಪ್: ಮೊದಲ ಅನ್‌ಲಾಕ್ ಉಚಿತ',
  'spot.howTo': 'ಹೋಗುವುದು ಹೇಗೆ',
  'spot.hours': 'ಸಮಯ',
  'spot.directions': 'ದಾರಿ',
  'spot.vouch': 'ನಾನು ಇಲ್ಲಿಗೆ ಹೋಗಿದ್ದೇನೆ',
  'spot.vouched': 'ನೀವು ದೃಢೀಕರಿಸಿದ್ದೀರಿ',
  'spot.permit': 'ಅರಣ್ಯ / ಪ್ರವೇಶ ಅನುಮತಿ ಬೇಕು. ಹೋಗುವ ಮೊದಲು ಬುಕ್ ಮಾಡಿ.',
  'spot.confirmedBy': '{n} ಜನ ಈ ಸ್ಥಳವನ್ನು ದೃಢೀಕರಿಸಿದ್ದಾರೆ',
  'spot.respect': '🌱 ಇದು ರಹಸ್ಯ ತಾಣ. ನಿಖರ ಸ್ಥಳವನ್ನು ಸಾರ್ವಜನಿಕವಾಗಿ ಹಾಕಬೇಡಿ, ಕಸವನ್ನು ವಾಪಸ್ ತನ್ನಿ, ಸ್ಥಳೀಯರನ್ನು ಗೌರವಿಸಿ.',
  'spot.cafesNearby': '☕ ಹತ್ತಿರದ ಕೆಫೆಗಳು',
  'spot.moreHidden': '🔒 ಇಲ್ಲಿನ ಇನ್ನಷ್ಟು ರಹಸ್ಯ ತಾಣಗಳು',

  'share.title': 'ಸ್ಥಳ ಹಂಚಿಕೊಳ್ಳಿ',
  'share.editTitle': 'ಸ್ಥಳ ತಿದ್ದಿ',
  'share.intro': 'ನೀವೇ ಹೋಗಿರುವ ಸ್ಥಳಗಳನ್ನು ಮಾತ್ರ ಹಂಚಿಕೊಳ್ಳಿ. ಅನುಮೋದನೆಯಾದರೆ ನಿಮಗೆ {n} ಅನ್‌ಲಾಕ್ ಸಿಗುತ್ತವೆ.',
  'share.pin': 'ನಿಖರ ಸ್ಥಳ ಗುರುತಿಸಲು ನಕ್ಷೆಯ ಮೇಲೆ ಒತ್ತಿ',
  'share.here': 'ನಾನು ಈಗ ಇಲ್ಲಿದ್ದೇನೆ',
  'share.name': 'ಹೆಸರು',
  'share.type': 'ಬಗೆ',
  'share.district': 'ಜಿಲ್ಲೆ',
  'share.choose': 'ಆಯ್ಕೆ ಮಾಡಿ…',
  'share.special': 'ಇದರ ವಿಶೇಷತೆ ಏನು?',
  'share.access': 'ಹೋಗುವುದು ಹೇಗೆ',
  'share.months': 'ಉತ್ತಮ ತಿಂಗಳುಗಳು',
  'share.photo': 'ಫೋಟೋ (ನಿಮ್ಮದೇ)',
  'share.addPhoto': 'ಫೋಟೋ ಸೇರಿಸಿ',
  'share.tags': 'ಟ್ಯಾಗ್‌ಗಳು',
  'share.hidden': 'ರಹಸ್ಯ ತಾಣ: ಅನ್‌ಲಾಕ್ ಮಾಡಿದವರಿಗೆ ಮಾತ್ರ ಸ್ಥಳ ಕಾಣುತ್ತದೆ',
  'share.permit': 'ಅರಣ್ಯ / ಪ್ರವೇಶ ಅನುಮತಿ ಬೇಕು',
  'share.rules': 'ಅನುಮತಿ ಇಲ್ಲದ ಖಾಸಗಿ ಜಾಗ, ಅಪಾಯಕಾರಿ ಅಥವಾ ಮುಚ್ಚಿರುವ ಸ್ಥಳಗಳನ್ನು ಹಂಚಿಕೊಳ್ಳಬೇಡಿ.',
  'share.submit': 'ಪರಿಶೀಲನೆಗೆ ಕಳುಹಿಸಿ',
  'share.save': 'ಬದಲಾವಣೆ ಉಳಿಸಿ',
  'share.gateTitle': 'ಒಂದು ತಾಣ ಕೊಡಿ, ಇನ್ನೊಂದು ಪಡೆಯಿರಿ',
  'share.gateBody': 'ನೀವು ಹೋಗಿರುವ ಒಂದು ರಹಸ್ಯ ಸ್ಥಳ ಹಂಚಿಕೊಳ್ಳಿ. ಅನುಮೋದನೆಯಾದರೆ ಬೇರೆಯವರ ರಹಸ್ಯ ತಾಣಗಳನ್ನು ನೋಡಲು 3 ಅನ್‌ಲಾಕ್ ಸಿಗುತ್ತವೆ.',
  'share.gateCta': 'ಲಾಗಿನ್ ಅಥವಾ ಸೈನ್ ಅಪ್',

  'login.signup': 'ಸೈನ್ ಅಪ್',
  'login.login': 'ಲಾಗಿನ್',
  'login.name': 'ನಿಮ್ಮ ಹೆಸರು',
  'login.email': 'ಇಮೇಲ್',
  'login.password': 'ಪಾಸ್‌ವರ್ಡ್',
  'login.min': 'ಕನಿಷ್ಠ 8 ಅಕ್ಷರಗಳು',
  'login.create': 'ಖಾತೆ ರಚಿಸಿ',
  'login.free': 'ನಿಮ್ಮ ಮೊದಲ ರಹಸ್ಯ ತಾಣದ ಅನ್‌ಲಾಕ್ ಉಚಿತ.',

  'footer.tag': 'ಗುಂಪು ಪ್ರವಾಸ, AI ನಿರ್ಧಾರ. ಕರ್ನಾಟಕಕ್ಕಾಗಿ.',
}

export const MONTHS_KN = ['ಜನ', 'ಫೆಬ್ರ', 'ಮಾರ್ಚ್', 'ಏಪ್ರಿ', 'ಮೇ', 'ಜೂನ್', 'ಜುಲೈ', 'ಆಗ', 'ಸೆಪ್ಟೆಂ', 'ಅಕ್ಟೋ', 'ನವೆಂ', 'ಡಿಸೆಂ']

const DICTS = { en, kn }

export const useLang = create(
  persist(
    (set) => ({
      lang: 'en',
      setLang: (lang) => {
        set({ lang })
        try { document.documentElement.lang = lang } catch { /* ignore */ }
      },
    }),
    { name: 'flockgo-lang' },
  ),
)

export function translate(lang, key, vars) {
  let s = DICTS[lang]?.[key] ?? en[key] ?? key
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, v)
  return s
}

export function useT() {
  const lang = useLang((s) => s.lang)
  return (key, vars) => translate(lang, key, vars)
}
