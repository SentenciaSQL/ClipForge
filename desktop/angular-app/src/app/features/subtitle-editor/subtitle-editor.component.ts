import { NgFor, NgIf } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';

import { SubtitlePreset } from '../../core/models';
import { ApiService } from '../../core/services/api.service';

@Component({
  selector: 'app-subtitle-editor',
  standalone: true,
  imports: [NgFor, NgIf],
  template: `
    <div class="space-y-6">
      <header>
        <div class="avc-label">Typography</div>
        <h1 class="avc-title mt-1">Subtitle Editor</h1>
        <p class="mt-2 max-w-2xl text-sm text-muted">
          Live subtitle presets from the backend. Choose a style in Clips Studio / render settings —
          ASS burn-in uses these configs with word-level highlighting.
        </p>
      </header>

      <div *ngIf="error()" class="rounded-xl border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
        {{ error() }}
      </div>

      <section class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <article class="avc-panel p-4" *ngFor="let preset of presets()">
          <div class="avc-label">{{ preset.is_builtin ? 'Built-in' : 'Custom' }} · {{ preset.slug }}</div>
          <div class="font-display text-lg font-semibold mt-1">{{ preset.name }}</div>
          <dl class="mt-3 space-y-1 text-xs text-muted">
            <div>Font: {{ preset.config['font_family'] || '—' }}</div>
            <div>Size: {{ preset.config['font_size'] || '—' }}</div>
            <div>Highlight: {{ preset.config['highlight_color'] || '—' }}</div>
            <div>Animation: {{ preset.config['animation_preset'] || 'none' }}</div>
            <div>Word highlight: {{ preset.config['word_highlight'] ? 'yes' : 'no' }}</div>
          </dl>
          <div
            class="mt-4 rounded-lg px-3 py-4 text-center text-sm font-semibold"
            [style.background]="'#111827'"
            [style.color]="(preset.config['primary_color'] || '#fff') + ''"
          >
            <span [style.color]="(preset.config['highlight_color'] || '#FFE600') + ''">WORD</span>
            LEVEL PREVIEW
          </div>
        </article>
      </section>
    </div>
  `,
})
export class SubtitleEditorComponent implements OnInit {
  private readonly api = inject(ApiService);
  readonly presets = signal<SubtitlePreset[]>([]);
  readonly error = signal<string | null>(null);

  ngOnInit(): void {
    this.api.listSubtitlePresets().subscribe({
      next: (presets) => this.presets.set(presets),
      error: (err) => this.error.set(err?.error?.detail || err?.message || 'Failed to load presets'),
    });
  }
}
