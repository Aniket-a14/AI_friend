import "./globals.css";

export const metadata = {
  title: "AI Friend",
  description: "Sovereign AI Voice Mesh",
  openGraph: {
    title: "AI Friend",
    description: "Sovereign AI Voice Mesh",
    siteName: "AI Friend",
    type: "website",
  },
  twitter: {
    card: "summary",
    title: "AI Friend",
    description: "Sovereign AI Voice Mesh",
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="font-sans">{children}</body>
    </html>
  );
}
