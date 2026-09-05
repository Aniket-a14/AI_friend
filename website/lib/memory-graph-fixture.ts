// Hand-authored fixture dataset for the Memory Activation & Decay visualizer.
// Illustrative only -- not derived from any real conversation. Clustered into
// a few "topics" so the graph has plausible neighbor structure to spread
// activation across.

export interface MemoryNode {
  id: string
  label: string
  topic: string
  recallCount: number
  hoursSince: number
  importanceScore: number
  distEmo: number
  neighbors: string[]
}

const TOPICS: Record<string, string[]> = {
  work: [
    "the deadline for the launch", "the argument with a coworker", "the promotion",
    "quitting the old job", "the new manager", "the failed demo", "the raise",
    "the late-night deploy", "the conference talk", "the layoffs scare",
  ],
  family: [
    "mom's birthday", "the trip home", "dad's surgery", "the sibling's wedding",
    "the family dinner argument", "grandma's stories", "moving out",
    "the holiday visit", "the phone call about the diagnosis", "the reunion",
  ],
  hobbies: [
    "learning guitar", "the marathon training", "the failed sourdough starter",
    "the camping trip", "picking up painting again", "the chess club",
    "finishing the novel draft", "the hiking injury", "the pottery class",
    "the garden's first tomatoes",
  ],
  friendship: [
    "the falling out with a close friend", "the surprise visit", "the shared apartment",
    "the road trip", "the friend who moved away", "the group chat drama",
    "the birthday party", "the late-night phone call", "the reconciliation",
    "meeting through a mutual friend",
  ],
  self: [
    "starting therapy", "the anxiety about the future", "the confidence breakthrough",
    "the identity questions", "the burnout", "learning to say no",
    "the sleep schedule struggle", "the small win worth celebrating",
    "the fear of failure", "the moment of real pride",
  ],
}

function seededRandom(seed: number) {
  let s = seed
  return () => {
    s = (s * 1103515245 + 12345) & 0x7fffffff
    return s / 0x7fffffff
  }
}

export const MEMORY_GRAPH_FIXTURE: MemoryNode[] = (() => {
  const rand = seededRandom(42)
  const nodes: MemoryNode[] = []

  for (const [topic, labels] of Object.entries(TOPICS)) {
    labels.forEach((label, i) => {
      nodes.push({
        id: `${topic}-${i}`,
        label,
        topic,
        recallCount: 1 + Math.floor(rand() * 12),
        hoursSince: Math.floor(rand() * 24 * 90), // up to ~90 days
        importanceScore: rand(),
        distEmo: rand(),
        neighbors: [], // filled below
      })
    })
  }

  // Connect each node to 2-4 same-topic neighbors (a topic cluster) plus
  // occasionally one cross-topic neighbor, so the graph has some bridging.
  for (const node of nodes) {
    const sameTopic = nodes.filter((n) => n.topic === node.topic && n.id !== node.id)
    const shuffled = [...sameTopic].sort(() => rand() - 0.5)
    const neighborCount = 2 + Math.floor(rand() * 3)
    node.neighbors = shuffled.slice(0, neighborCount).map((n) => n.id)

    if (rand() > 0.7) {
      const otherTopic = nodes.filter((n) => n.topic !== node.topic)
      const bridge = otherTopic[Math.floor(rand() * otherTopic.length)]
      if (bridge) node.neighbors.push(bridge.id)
    }
  }

  return nodes
})()
