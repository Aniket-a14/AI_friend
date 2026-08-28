'use client';

import { Heading, Card, PrimaryButton } from '@/components/ui';

export default function DoneStep({ name, voiceSaved }) {
    return (
        <div className="max-w-xl mx-auto text-center">
            <Heading>{name} is ready.</Heading>
            <Card className="mt-8 text-left">
                <ul className="space-y-2 text-sm text-black/60">
                    <li>✓ Persona saved — seeded on the agent&apos;s next first boot.</li>
                    <li>{voiceSaved ? '✓' : '—'} Voice {voiceSaved ? 'recorded and saved' : 'left as the bundled default'}.</li>
                </ul>
                <p className="mt-6 text-sm text-black/45 leading-relaxed">
                    Restart the mesh (<code className="text-black/70">./start.sh</code>) so the
                    voice agent picks up the new reference clip, then come back and talk.
                </p>
            </Card>
            <div className="mt-8">
                <PrimaryButton onClick={() => (window.location.href = '/')}>
                    Go talk to them
                </PrimaryButton>
            </div>
        </div>
    );
}
