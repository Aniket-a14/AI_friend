import fs from "node:fs"
import path from "node:path"
import { ALL_DOC_PAGES } from "@/lib/docs-nav"

const CONTENT_DIR = path.join(process.cwd(), "content", "docs")

export interface DocSource {
  title: string
  body: string
}

export function getAllDocSlugs(): string[] {
  return ALL_DOC_PAGES.map((p) => p.slug)
}

export function getDocSource(slug: string): DocSource {
  const filePath = path.join(CONTENT_DIR, `${slug}.md`)
  const raw = fs.readFileSync(filePath, "utf8")
  const titleMatch = raw.match(/^#\s+(.+)$/m)
  const title = titleMatch ? titleMatch[1].trim() : slug
  // Strip the leading H1 -- the page shell renders its own title, so a
  // duplicate would show the same heading twice at different sizes.
  const body = raw.replace(/^#\s+.+\n/, "")
  return { title, body }
}
