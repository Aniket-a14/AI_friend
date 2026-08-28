import React from "react"
import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'AI Friend — A friend of your own making',
  description: 'An AI friend you describe in your own words, that speaks in a voice you gave it, runs entirely on your own machine, and remembers who you are. Local-first, open source, MIT licensed.',
  keywords: ['AI companion', 'local AI', 'self-hosted AI', 'voice cloning', 'open source'],
  authors: [{ name: 'AI Friend contributors' }],
  openGraph: {
    title: 'AI Friend — A friend of your own making',
    description: 'Describe them in your own words. They speak in a voice you gave them, remember who you are, and run entirely on your own hardware.',
    type: 'website',
    url: 'https://github.com/Aniket-a14/AI_friend',
    siteName: 'AI Friend',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'AI Friend — A friend of your own making',
    description: 'Describe them in your own words. They speak in a voice you gave them, remember who you are, and run entirely on your own hardware.',
  },
  icons: {
    icon: [
      {
        url: '/icon-light-32x32.png',
        media: '(prefers-color-scheme: light)',
      },
      {
        url: '/icon-dark-32x32.png',
        media: '(prefers-color-scheme: dark)',
      },
      {
        url: '/icon.svg',
        type: 'image/svg+xml',
      },
    ],
    apple: '/apple-icon.png',
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body className={`font-sans antialiased`}>
        {children}
      </body>
    </html>
  )
}
