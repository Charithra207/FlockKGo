export const MOCK_TRIP = {
  id: 'trip-demo-001',
  name: 'Europe Summer 2025',
  organizer_name: 'Aryan',
  organizer_email: 'aryan@example.com',
  status: 'voting',
  trip_month: 'June',
  duration_days: 7,
}

export const MOCK_PARTICIPANTS = [
  { id: 'p1', name: 'Aryan', survey_submitted: true, survey_link: '/survey/token-1' },
  { id: 'p2', name: 'Maya', survey_submitted: true, survey_link: '/survey/token-2' },
  { id: 'p3', name: 'Rhea', survey_submitted: true, survey_link: '/survey/token-3' },
  { id: 'p4', name: 'Kabir', survey_submitted: false, survey_link: '/survey/token-4' },
  { id: 'p5', name: 'Noah', survey_submitted: false, survey_link: '/survey/token-5' },
]

export const MOCK_RECOMMENDATIONS = [
  { id: 'd1', name: 'Bali', country_flag: '🇮🇩', why: 'Balanced relaxation and adventure for mixed preferences.', budget_min: 1200, budget_max: 2200, activities: ['Beaches', 'Temples', 'Surf'], ml_score: 86, concern: 'Long travel time for some members' },
  { id: 'd2', name: 'Tokyo', country_flag: '🇯🇵', why: 'High city, food, and culture overlap with the group.', budget_min: 1800, budget_max: 3000, activities: ['Food tours', 'Museums', 'Nightlife'], ml_score: 82, concern: '' },
  { id: 'd3', name: 'Barcelona', country_flag: '🇪🇸', why: 'Great blend of beach, culture, and nightlife.', budget_min: 1300, budget_max: 2400, activities: ['Architecture', 'Tapas', 'Beach'], ml_score: 91, concern: '' },
  { id: 'd4', name: 'Lisbon', country_flag: '🇵🇹', why: 'Budget-friendly city with strong food and vibe fit.', budget_min: 1100, budget_max: 2100, activities: ['Tram rides', 'Food', 'Day trips'], ml_score: 84, concern: 'Can get windy in shoulder months' },
  { id: 'd5', name: 'Prague', country_flag: '🇨🇿', why: 'Excellent value and cultural depth for the group.', budget_min: 900, budget_max: 1700, activities: ['Old town', 'Cafes', 'Nightlife'], ml_score: 79, concern: 'Cooler weather depending on dates' },
]

export const MOCK_RESULTS = {
  winner: 'Barcelona',
  total_voters: 5,
  rounds_taken: 2,
  ai_agreement: true,
  rounds: [
    { round: 1, eliminated: 'Prague', votes: { Barcelona: 2, Bali: 1, Tokyo: 1, Lisbon: 1, Prague: 0 } },
    { round: 2, eliminated: 'Lisbon', votes: { Barcelona: 3, Bali: 1, Tokyo: 1, Lisbon: 0 } },
  ],
  final_ranking: ['Barcelona', 'Bali', 'Tokyo', 'Lisbon', 'Prague'],
}
