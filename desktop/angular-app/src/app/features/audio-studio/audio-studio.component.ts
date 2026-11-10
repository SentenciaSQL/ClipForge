import { Component } from '@angular/core';

@Component({
  selector: 'app-audio-studio',
  standalone: true,
  template: `
    <div class="space-y-4">
      <div class="avc-label">Sound</div>
      <h1 class="avc-title">Audio Studio</h1>
      <p class="max-w-2xl text-sm text-muted">
        Independent original, music, replacement, and voice-over tracks with ducking and loudness
        normalization. Backend filter builders live under <code>backend/app/media/audio</code>; full
        timeline UI and clip APIs ship with the Audio Studio implementation pass after Phase 4 rendering.
      </p>
      <div class="avc-panel grid gap-3 p-5 sm:grid-cols-2 text-sm">
        <div class="rounded-xl border border-line bg-canvas/50 p-4">Original / mute / remove</div>
        <div class="rounded-xl border border-line bg-canvas/50 p-4">Background music + fades</div>
        <div class="rounded-xl border border-line bg-canvas/50 p-4">Voice-over sync</div>
        <div class="rounded-xl border border-line bg-canvas/50 p-4">Ducking + loudnorm mix</div>
      </div>
    </div>
  `,
})
export class AudioStudioComponent {}
