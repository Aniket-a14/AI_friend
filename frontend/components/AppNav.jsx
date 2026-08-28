'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const LINKS = [
    { href: '/', label: 'Talk' },
    { href: '/chat', label: 'Chat' },
    { href: '/memories', label: 'Memories' },
    { href: '/settings', label: 'Settings' },
];

export default function AppNav() {
    const pathname = usePathname();
    return (
        <nav className="border-b border-black/[0.07] bg-white/70 backdrop-blur sticky top-0 z-10">
            <div className="max-w-4xl mx-auto px-4 md:px-8 h-14 flex items-center gap-1">
                {LINKS.map(({ href, label }) => {
                    const active = href === '/' ? pathname === '/' : pathname?.startsWith(href);
                    return (
                        <Link
                            key={href}
                            href={href}
                            className={`px-3 py-1.5 rounded-lg text-sm tracking-wide transition-colors ${
                                active
                                    ? 'bg-[#111] text-white'
                                    : 'text-black/50 hover:text-black hover:bg-black/[0.04]'
                            }`}
                        >
                            {label}
                        </Link>
                    );
                })}
            </div>
        </nav>
    );
}
