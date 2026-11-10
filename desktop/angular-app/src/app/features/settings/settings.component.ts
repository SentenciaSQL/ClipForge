import { JsonPipe, NgIf } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { AppSettings } from '../../core/models';
import { ApiService } from '../../core/services/api.service';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [NgIf, FormsModule, JsonPipe],
  template: `
    <div class="space-y-6">
      <header>
        <div class="avc-label">Configuration</div>
        <h1 class="avc-title mt-1">Settings</h1>
        <p class="mt-2 text-sm text-muted">Local paths, models, and rendering defaults. No cloud keys required.</p>
      </header>

      <div *ngIf="message()" class="rounded-xl border border-accent/30 bg-accent/10 px-4 py-3 text-sm text-accent">
        {{ message() }}
      </div>
      <div *ngIf="error()" class="rounded-xl border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
        {{ error() }}
      </div>

      <form class="avc-panel grid gap-4 p-5 md:grid-cols-2" *ngIf="settings() as s" (ngSubmit)="save()">
        <label class="text-sm">
          <span class="avc-label">Ollama URL</span>
          <input class="avc-input mt-2" [(ngModel)]="s.ollama_url" name="ollama_url" />
        </label>
        <label class="text-sm">
          <span class="avc-label">Ollama model</span>
          <input class="avc-input mt-2" [(ngModel)]="s.ollama_model" name="ollama_model" />
        </label>
        <label class="text-sm">
          <span class="avc-label">Whisper model</span>
          <select class="avc-input mt-2" [(ngModel)]="s.whisper_model" name="whisper_model">
            <option value="large-v3">large-v3</option>
            <option value="distil-large-v3">distil-large-v3</option>
            <option value="medium">medium</option>
            <option value="small">small</option>
          </select>
        </label>
        <label class="text-sm">
          <span class="avc-label">Whisper device</span>
          <select class="avc-input mt-2" [(ngModel)]="s.whisper_device" name="whisper_device">
            <option value="auto">auto</option>
            <option value="cuda">cuda</option>
            <option value="cpu">cpu</option>
          </select>
        </label>
        <label class="text-sm">
          <span class="avc-label">Workspace path</span>
          <input class="avc-input mt-2" [(ngModel)]="s.workspace_path" name="workspace_path" />
        </label>
        <label class="text-sm">
          <span class="avc-label">FFmpeg path</span>
          <input class="avc-input mt-2" [(ngModel)]="s.ffmpeg_path" name="ffmpeg_path" />
        </label>
        <label class="text-sm">
          <span class="avc-label">Max concurrent jobs</span>
          <input class="avc-input mt-2" type="number" min="1" max="4" [(ngModel)]="s.max_concurrent_jobs" name="max_jobs" />
        </label>
        <label class="text-sm">
          <span class="avc-label">CRF</span>
          <input class="avc-input mt-2" type="number" min="12" max="28" [(ngModel)]="s.crf" name="crf" />
        </label>
        <label class="flex items-center gap-3 text-sm md:col-span-2">
          <input type="checkbox" [(ngModel)]="s.prefer_gpu" name="prefer_gpu" />
          Prefer GPU when available
        </label>
        <div class="md:col-span-2">
          <button class="avc-btn-primary" type="submit">Save settings</button>
        </div>
      </form>

      <section class="avc-panel p-5" *ngIf="settings() as s">
        <div class="avc-label">Detected hardware</div>
        <pre class="mt-3 overflow-auto rounded-xl bg-canvas p-4 text-xs text-muted">{{ s.hardware | json }}</pre>
      </section>
    </div>
  `,
})
export class SettingsComponent implements OnInit {
  private readonly api = inject(ApiService);
  readonly settings = signal<AppSettings | null>(null);
  readonly message = signal<string | null>(null);
  readonly error = signal<string | null>(null);

  ngOnInit(): void {
    this.api.getSettings().subscribe({
      next: (settings) => this.settings.set(settings),
      error: (err) => this.error.set(err?.message || 'Failed to load settings'),
    });
  }

  save(): void {
    const current = this.settings();
    if (!current) {
      return;
    }
    this.api.updateSettings(current).subscribe({
      next: (updated) => {
        this.settings.set(updated);
        this.message.set('Settings saved.');
        this.error.set(null);
      },
      error: (err) => this.error.set(err?.error?.detail || 'Save failed'),
    });
  }
}
