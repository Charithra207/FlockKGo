export const formatCurrency = (v) => `$${Number(v || 0).toLocaleString()}`
export const formatBudgetRange = (min, max) => `${formatCurrency(min)} - ${formatCurrency(max)} per person`
