"use client"

import { Prism as SyntaxHighlighter } from "react-syntax-highlighter"
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism"

const LANGUAGE_LABELS: Record<string, string> = {
  bash: "bash",
  sh: "shell",
  shell: "shell",
  zsh: "zsh",
  powershell: "powershell",
  ps1: "powershell",
  python: "python",
  py: "python",
  rust: "rust",
  rs: "rust",
  javascript: "javascript",
  js: "javascript",
  typescript: "typescript",
  ts: "typescript",
  tsx: "tsx",
  jsx: "jsx",
  json: "json",
  yaml: "yaml",
  yml: "yaml",
  toml: "toml",
  sql: "sql",
  dockerfile: "dockerfile",
  docker: "dockerfile",
  cypher: "cypher",
  text: "text",
  plaintext: "text",
}

export function CodeBlock({ language, code }: { language: string; code: string }) {
  const label = LANGUAGE_LABELS[language.toLowerCase()] ?? language

  return (
    <div className="mb-4 overflow-hidden rounded-xl border border-black/[0.07] bg-[#fbfaf8]">
      <div className="flex items-center justify-between border-b border-black/[0.06] bg-black/[0.02] px-4 py-1.5">
        <span className="font-mono text-[10px] uppercase tracking-widest text-black/35">{label}</span>
      </div>
      <SyntaxHighlighter
        language={language}
        style={oneLight}
        customStyle={{
          margin: 0,
          padding: "1rem",
          background: "transparent",
          fontSize: "13px",
          lineHeight: 1.6,
        }}
        codeTagProps={{ style: { fontFamily: "var(--font-mono, ui-monospace, monospace)" } }}
        wrapLongLines
      >
        {code}
      </SyntaxHighlighter>
    </div>
  )
}
