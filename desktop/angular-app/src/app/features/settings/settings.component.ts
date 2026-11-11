import { DecimalPipe, JsonPipe, NgIf } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { AppSettings } from '../../core/models';
import { ApiService } from '../../core/services/api.service';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [NgIf, FormsModule, JsonPipe, DecimalPipe],
  template: `
    <div class="space-y-6">
      <header>
        <div class="avc-label">Configuration</div>
        <h1 class="avc-title mt-1">Settings</h1>
        <p class="mt-2 text-sm text-muted">Local paths, models, rendering defaults, and system maintenance.</p>
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
            <option value="auto">auto (CPU if CUDA libs missing)</option>
            <option value="cuda">cuda</option>
            <option value="cpu">cpu</option>
          </select>
          <p class="mt-1 text-xs text-muted">
            If transcription fails with cublas64_12.dll, choose CPU or install CUDA Toolkit 12.x.
          </p>
        </label>
        <label class="text-sm">
          <span class="avc-label">Default clip min (seconds)</span>
          <input
            class="avc-input mt-2"
            type="number"
            min="12"
            max="30"
            step="1"
            [(ngModel)]="s.clip_min_seconds"
            name="clip_min_seconds"
          />
        </label>
        <label class="text-sm">
          <span class="avc-label">Default clip max (seconds)</span>
          <input
            class="avc-input mt-2"
            type="number"
            min="12"
            max="60"
            step="1"
            [(ngModel)]="s.clip_max_seconds"
            name="clip_max_seconds"
          />
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

      <section class="avc-panel p-5 space-y-4">
        <div>
          <div class="avc-label">System maintenance</div>
          <p class="mt-1 text-sm text-muted">
            Unload Whisper to free VRAM, inspect cache, or clear temporary artifacts.
          </p>
        </div>
        <div class="text-sm" *ngIf="system() as sys">
          <div>GPU holder: {{ $any(sys['gpu'])?.holder || 'none' }} · Whisper loaded:
            {{ $any(sys['gpu'])?.whisper_loaded ? 'yes' : 'no' }}</div>
          <div class="mt-1 text-muted">
            Cache: {{ ($any(sys['cache'])?.total_bytes || 0) / 1048576 | number: '1.1-1' }} MB across
            {{ $any(sys['cache'])?.entry_count || 0 }} entries
          </div>
        </div>
        <div class="flex flex-wrap gap-2">
          <button class="avc-btn-ghost" type="button" (click)="refreshSystem()">Refresh status</button>
          <button class="avc-btn-ghost" type="button" (click)="unloadGpu()">Unload Whisper</button>
          <button class="avc-btn-ghost" type="button" (click)="clearAllCache()">Clear all cache</button>
        </div>
      </section>

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
  readonly system = signal<Record<string, unknown> | null>(null);
  readonly message = signal<string | null>(null);
  readonly error = signal<string | null>(null);

  ngOnInit(): void {
    this.api.getSettings().subscribe({
      next: (settings) => this.settings.set(settings),
      error: (err) => this.error.set(err?.message || 'Failed to load settings'),
    });
    this.refreshSystem();
  }

  refreshSystem(): void {
    this.api.getSystemStatus().subscribe({
      next: (status) => this.system.set(status),
      error: (err) => this.error.set(err?.error?.detail || 'Failed to load system status'),
    });
  }

  unloadGpu(): void {
    this.api.unloadWhisper().subscribe({
      next: (result) => {
        this.message.set(`Whisper unload: was_loaded=${result['was_loaded']}`);
        this.refreshSystem();
      },
      error: (err) => this.error.set(err?.error?.detail || 'Unload failed'),
    });
  }

  clearAllCache(): void {
    this.api.clearCache({ kind: 'all' }).subscribe({
      next: (result) => {
        this.message.set(`Cleared ${result['removed_paths']} paths · freed ${result['freed_bytes']} bytes`);
        this.refreshSystem();
      },
      error: (err) => this.error.set(err?.error?.detail || 'Cache clear failed'),
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
