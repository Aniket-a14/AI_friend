// Single source of truth for the sidebar and prev/next links. Every slug
// here must have a matching file at content/docs/<slug>.md.

export interface DocPage {
  title: string
  slug: string
}

export interface DocSection {
  title: string
  pages: DocPage[]
}

export const DOCS_NAV: DocSection[] = [
  {
    title: "Getting Started",
    pages: [
      { title: "Installation", slug: "getting-started/installation" },
      { title: "Quickstart", slug: "getting-started/quickstart" },
    ],
  },
  {
    title: "Concepts",
    pages: [
      { title: "Architecture", slug: "concepts/architecture" },
      { title: "Privacy & data", slug: "concepts/privacy" },
    ],
  },
  {
    title: "Guides",
    pages: [{ title: "Voice training & other GPU work", slug: "guides/voice-training" }],
  },
  {
    title: "Troubleshooting",
    pages: [{ title: "Common issues", slug: "troubleshooting/common-issues" }],
  },
]

export const ALL_DOC_PAGES: DocPage[] = DOCS_NAV.flatMap((section) => section.pages)

export function findDocPage(slug: string): DocPage | undefined {
  return ALL_DOC_PAGES.find((p) => p.slug === slug)
}

export function findSectionForSlug(slug: string): DocSection | undefined {
  return DOCS_NAV.find((section) => section.pages.some((p) => p.slug === slug))
}

export function getAdjacentPages(slug: string): { prev?: DocPage; next?: DocPage } {
  const index = ALL_DOC_PAGES.findIndex((p) => p.slug === slug)
  if (index === -1) return {}
  return {
    prev: index > 0 ? ALL_DOC_PAGES[index - 1] : undefined,
    next: index < ALL_DOC_PAGES.length - 1 ? ALL_DOC_PAGES[index + 1] : undefined,
  }
}
