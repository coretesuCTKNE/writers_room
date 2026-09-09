/**
 * AudioWorklet processor for PCM resampling + 100ms framing.
 *
 * Captures mic audio at native sample rate, resamples to 16kHz mono PCM,
 * accumulates 1,600 samples (100ms), then posts binary frames to the
 * main thread for WebSocket transmission to Gemini Live.
 *
 * Also computes per-frame RMS for VU meter display.
 */

const FRAME_SIZE = 1600; // 100ms at 16kHz
const INPUT_BUFFER_MAX = FRAME_SIZE * 4; // ring buffer for native-rate input

class AudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._inputBuffer = new Float32Array(INPUT_BUFFER_MAX);
    this._inputWritePos = 0;
    this._frameAccum = new Float32Array(FRAME_SIZE);
    this._framePos = 0;
    this._active = false;

    this.port.onmessage = (e) => {
      if (e.data.type === 'start') {
        this._active = true;
      } else if (e.data.type === 'stop') {
        this._active = false;
        this._flushRemaining();
      }
    };
  }

  process(inputs, outputs, parameters) {
    if (!this._active) return true;

    const input = inputs[0];
    if (!input || !input[0]) return true;

    const channelData = input[0]; // mono

    if (sampleRate === 16000) {
      // Native 16kHz — copy directly into frame accumulator
      this._accumulate(channelData);
    } else {
      // Resample to 16kHz
      const ratio = sampleRate / 16000;
      const resampledLength = Math.floor(channelData.length / ratio);
      const resampled = new Float32Array(resampledLength);
      for (let i = 0; i < resampledLength; i++) {
        const srcIdx = i * ratio;
        const idx = Math.floor(srcIdx);
        const frac = srcIdx - idx;
        resampled[i] =
          idx + 1 < channelData.length
            ? channelData[idx] * (1 - frac) + channelData[idx + 1] * frac
            : channelData[idx];
      }
      this._accumulate(resampled);
    }

    return true;
  }

  _accumulate(samples) {
    let offset = 0;
    while (offset < samples.length) {
      const space = FRAME_SIZE - this._framePos;
      const toCopy = Math.min(space, samples.length - offset);
      this._frameAccum.set(
        samples.subarray(offset, offset + toCopy),
        this._framePos,
      );
      this._framePos += toCopy;
      offset += toCopy;

      if (this._framePos >= FRAME_SIZE) {
        this._emitFrame();
        this._framePos = 0;
      }
    }
  }

  _emitFrame() {
    // Compute RMS for VU meter
    let sum = 0;
    for (let i = 0; i < FRAME_SIZE; i++) {
      sum += this._frameAccum[i] * this._frameAccum[i];
    }
    const rms = Math.sqrt(sum / FRAME_SIZE);

    // Convert Float32 → Int16 PCM
    const pcm = new Int16Array(FRAME_SIZE);
    for (let i = 0; i < FRAME_SIZE; i++) {
      const s = Math.max(-1, Math.min(1, this._frameAccum[i]));
      pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }

    this.port.postMessage(
      { type: 'frame', pcm: pcm.buffer, rms },
      [pcm.buffer],
    );
  }

  _flushRemaining() {
    if (this._framePos > 0) {
      // Zero-pad remaining samples
      this._frameAccum.fill(0, this._framePos, FRAME_SIZE);
      this._framePos = FRAME_SIZE;
      this._emitFrame();
      this._framePos = 0;
    }
  }
}

registerProcessor('audio-processor', AudioProcessor);
