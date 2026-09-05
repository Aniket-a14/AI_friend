// Exact 1:1 port of backend/app/cognitive/tom.py's pure/regex-based functions.
// Does NOT port inferred_valence/inferred_arousal -- those come from the
// LLM-backed appraisal engine elsewhere, not from tom.py itself.

export const MAX_KNOWN_CONCEPTS = 200

const STOP_WORDS = new Set([
  "them", "they", "their", "there", "these", "those", "this", "that",
  "with", "from", "your", "what", "when", "where", "which", "who", "whom",
  "have", "has", "had", "been", "being", "were", "was", "will", "would",
  "should", "could", "about", "above", "after", "again", "against", "some",
  "more", "most", "other", "such", "than", "then", "very", "just", "here",
  "also", "even", "still", "well", "really", "actually", "maybe", "kind",
  "sort", "much", "many", "does", "doing", "because", "before", "during",
  "while", "same", "only", "over", "into", "under", "until",
])

// Zero-overhead vocabulary tracker: extracts significant words from the
// user's transcript without LLM latency.
export function updateKnownConcepts(currentConcepts: string[], userInput: string): string[] {
  if (!userInput) return currentConcepts

  // Clean alphabetical words between 4 and 15 characters in length.
  const words = userInput.match(/\b[a-zA-Z]{4,15}\b/g) ?? []

  const updated = [...currentConcepts]
  const seenLower = new Set(updated.map((c) => c.toLowerCase()))

  for (const word of words) {
    const lower = word.toLowerCase()
    if (!STOP_WORDS.has(lower) && !seenLower.has(lower)) {
      updated.push(word)
      seenLower.add(lower)
    }
  }

  // Sliding window: drop the oldest concepts once the cap is exceeded.
  if (updated.length > MAX_KNOWN_CONCEPTS) {
    return updated.slice(updated.length - MAX_KNOWN_CONCEPTS)
  }
  return updated
}

export interface BeliefDiscrepancy {
  userBelief: string
  groundTruth: string
}

// Compares user beliefs with ground truth facts to identify discrepancies.
export function extractBeliefDiscrepancies(
  userBeliefs: Record<string, string>,
  groundTruth: Record<string, string>,
): Record<string, BeliefDiscrepancy> {
  const discrepancies: Record<string, BeliefDiscrepancy> = {}
  for (const [concept, belief] of Object.entries(userBeliefs)) {
    const truth = groundTruth[concept]
    if (truth && truth.toLowerCase() !== belief.toLowerCase()) {
      discrepancies[concept] = { userBelief: belief, groundTruth: truth }
    }
  }
  return discrepancies
}
