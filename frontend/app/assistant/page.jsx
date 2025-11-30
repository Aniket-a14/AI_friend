'use client';

import AI FriendCircle from '../../components/AI FriendCircle';
import { useBackendState } from '../../hooks/useBackendState';

export default function AssistantPage() {
    const state = useBackendState();

    return (
        <main className="flex min-h-screen flex-col items-center justify-center bg-black overflow-hidden">
            <div className="relative flex items-center justify-center w-full h-full">
                <AI FriendCircle state={state} />
            </div>
        </main>
    );
}
