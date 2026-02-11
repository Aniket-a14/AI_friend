class AudioProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
    }

    process(inputs, outputs, parameters) {
        const input = inputs[0];
        if (input.length > 0) {
            const channelData = input[0];

            // Convert Float32 to Int16 PCM
            const pcmData = new Int16Array(channelData.length);
            for (let i = 0; i < channelData.length; i++) {
                // Clamp values between -1 and 1
                const s = Math.max(-1, Math.min(1, channelData[i]));
                // Scale to 16-bit range
                pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
            }

            // Send buffer to the main thread
            this.port.postMessage(pcmData.buffer);
        }
        return true;
    }
}

registerProcessor('audio-processor', AudioProcessor);
