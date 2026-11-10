import { Component } from '@angular/core';

@Component({
  selector: 'app-clips-studio',
  standalone: true,
  template: `
    <div class="space-y-4">
      <div class="avc-label">Edit</div>
      <h1 class="avc-title">Clips Studio</h1>
      <p class="max-w-2xl text-sm text-muted">
        Preview, trim, reframe, and restyle generated clips. This screen will populate once Phase 3–4
        produce scored clip candidates.
      </p>
      <div class="avc-panel p-8 text-sm text-muted">No clips yet.</div>
    </div>
  `,
})
export class ClipsStudioComponent {}
