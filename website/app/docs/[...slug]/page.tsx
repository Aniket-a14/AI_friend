import type { Metadata } from "next"
import Link from "next/link"
import { notFound } from "next/navigation"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { findDocPage, getAdjacentPages } from "@/lib/docs-nav"
import { getAllDocSlugs, getDocSource } from "@/lib/docs-content"
import { ComingSoonOverlay } from "@/components/coming-soon-overlay"

export function generateStaticParams() {
  return getAllDocSlugs().map((slug) => ({ slug: slug.split("/") }))
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string[] }> }): Promise<Metadata> {
  const { slug: slugParts } = await params
  const slug = slugParts.join("/")
  const page = findDocPage(slug)
  return {
    title: page ? `${page.title} — AI Friend Docs` : "AI Friend Docs",
  }
}

export default async function DocPage({ params }: { params: Promise<{ slug: string[] }> }) {
  const { slug: slugParts } = await params
  const slug = slugParts.join("/")
  const page = findDocPage(slug)
  if (!page) notFound()

  const { title, body } = getDocSource(slug)
  const { prev, next } = getAdjacentPages(slug)

  const content = (
    <div className="max-w-2xl">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h2: (props) => <h2 className="mt-10 mb-3 text-xl font-light border-t border-black/[0.06] pt-8" {...props} />,
          h3: (props) => <h3 className="mt-6 mb-2 text-base font-medium" {...props} />,
          p: (props) => <p className="mb-4 text-sm text-black/60 leading-relaxed" {...props} />,
          ul: (props) => <ul className="mb-4 space-y-1.5 list-disc pl-5 text-sm text-black/60" {...props} />,
          ol: (props) => <ol className="mb-4 space-y-1.5 list-decimal pl-5 text-sm text-black/60" {...props} />,
          li: (props) => <li className="leading-relaxed" {...props} />,
          a: (props) => <a className="text-black underline underline-offset-2 decoration-black/30 hover:decoration-black" {...props} />,
          strong: (props) => <strong className="font-medium text-black/80" {...props} />,
          code: (props) => <code className="rounded bg-black/[0.05] px-1.5 py-0.5 text-[13px] font-mono text-black/70" {...props} />,
          pre: (props) => (
            <pre className="mb-4 overflow-x-auto rounded-xl border border-black/[0.07] bg-black/[0.03] p-4 text-[13px] leading-relaxed [&_code]:bg-transparent [&_code]:p-0" {...props} />
          ),
          table: (props) => (
            <div className="mb-4 overflow-x-auto rounded-xl border border-black/[0.07]">
              <table className="w-full border-collapse text-sm" {...props} />
            </div>
          ),
          thead: (props) => <thead className="bg-black/[0.03] text-left text-xs uppercase tracking-wide text-black/40" {...props} />,
          th: (props) => <th className="px-4 py-2.5 font-medium" {...props} />,
          td: (props) => <td className="border-t border-black/[0.05] px-4 py-2.5 text-black/60" {...props} />,
        }}
      >
        {body}
      </ReactMarkdown>
    </div>
  )

  return (
    <article>
      <div className="flex items-center gap-3 mb-6">
        <h1 className="text-3xl md:text-4xl font-light tracking-tight" style={{ fontFamily: '"IBM Plex Sans", sans-serif' }}>
          {title}
        </h1>
        {page.comingSoon && (
          <span className="font-mono text-[9px] uppercase tracking-widest px-2.5 py-1 rounded-full bg-amber-100 text-amber-900 border border-amber-300 font-semibold">
            COMING SOON
          </span>
        )}
      </div>

      {page.comingSoon ? (
        <ComingSoonOverlay
          title="COMING SOON"
          description="This specification is currently in development on the roadmap. Full draft preview visible below."
          eta="Roadmap Target"
          blurAmount="md"
        >
          {content}
        </ComingSoonOverlay>
      ) : (
        content
      )}

      <div className="mt-16 flex items-center justify-between border-t border-black/[0.06] pt-8">
        {prev ? (
          <Link href={`/docs/${prev.slug}`} className="text-sm text-black/50 hover:text-black">
            ← {prev.title}
          </Link>
        ) : (
          <span />
        )}
        {next ? (
          <Link href={`/docs/${next.slug}`} className="text-sm text-black/50 hover:text-black">
            {next.title} →
          </Link>
        ) : (
          <span />
        )}
      </div>
    </article>
  )
}
