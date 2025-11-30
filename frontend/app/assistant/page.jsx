'use client';

import AssistantCircle from '../../components/AssistantCircle';
import { useBackendState } from '../../hooks/useBackendState';

export default function AssistantPage() {
    const state = useBackendState();

    return (
        <main className="flex min-h-screen flex-col items-center justify-center bg-black overflow-hidden">
            <div className="relative flex items-center justify-center w-full h-full">
                <AssistantCircle state={state} />
            </div>
        </main>
    );
}
