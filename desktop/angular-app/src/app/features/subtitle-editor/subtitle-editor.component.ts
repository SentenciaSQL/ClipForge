import { NgFor } from '@angular/common';
import { Component } from '@angular/core';

@Component({
  selector: 'app-subtitle-editor',
  standalone: true,
  imports: [NgFor],
  template: `
    <div class="space-y-4">
      <div class="avc-label">Typography</div>
      <h1 class="avc-title">Subtitle Editor</h1>
      <p class="max-w-2xl text-sm text-muted">
        Built-in presets are already stored as JSON under <code>resources/subtitle-presets</code>.
        Word-level ASS rendering lands in Phase 4.
      </p>
      <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <article class="avc-panel p-4" *ngFor="let preset of presets">
          <div class="font-display text-lg font-semibold">{{ preset }}</div>
          <p class="mt-2 text-xs text-muted">Preset available for burn-in once rendering is enabled.</p>
        </article>
      </div>
    </div>
  `,
})
export class SubtitleEditorComponent {
  readonly presets = ['Hormozi', 'Karaoke', 'TikTok', 'Minimal', 'Professional', 'Custom'];
}
