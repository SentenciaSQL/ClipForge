import { DecimalPipe, NgFor, NgIf } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { Clip, SourceVideo } from '../../core/models';
import { ApiService } from '../../core/services/api.service';

@Component({
  selector: 'app-clips-studio',
  standalone: true,
  imports: [NgIf, NgFor, FormsModule, DecimalPipe],
  template: `
    <div class="space-y-6">
      <header>
        <div class="avc-label">Edit</div>
        <h1 class="avc-title mt-1">Clips Studio</h1>
        <p class="mt-2 max-w-2xl text-sm text-muted">
          Scored candidates from local semantic analysis. Rendering and subtitle burn-in arrive in Phase 4.
        </p>
      </header>

      <section class="avc-panel p-5">
        <label class="text-sm block">
          <span class="avc-label">Source video</span>
          <select class="avc-input mt-2" [(ngModel)]="selectedVideoId" (ngModelChange)="loadClips()">
            <option value="">Select a video</option>
            <option *ngFor="let video of videos()" [value]="video.id">
              {{ video.original_filename }}
            </option>
          </select>
        </label>
      </section>

      <div *ngIf="error()" class="rounded-xl border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
        {{ error() }}
      </div>

      <section class="grid gap-4 lg:grid-cols-2" *ngIf="clips().length; else empty">
        <article class="avc-panel p-5" *ngFor="let clip of clips()">
          <div class="flex items-start justify-between gap-3">
            <div>
              <div class="avc-label">{{ clip.category || 'general' }}</div>
              <h2 class="mt-1 font-display text-lg font-semibold">{{ clip.hook || clip.title }}</h2>
            </div>
            <div class="font-display text-2xl font-semibold text-accent">{{ clip.score | number: '1.0-0' }}</div>
          </div>
          <p class="mt-3 text-xs text-muted">
            {{ clip.start_seconds | number: '1.1-1' }}s → {{ clip.end_seconds | number: '1.1-1' }}s
            ({{ clip.duration_seconds | number: '1.1-1' }}s) · {{ clip.status }}
          </p>
          <p class="mt-3 text-sm leading-relaxed">{{ clip.transcript }}</p>
        </article>
      </section>
      <ng-template #empty>
        <div class="avc-panel p-8 text-sm text-muted">
          No clips yet. Run analysis from Import or Generate after transcription.
        </div>
      </ng-template>
    </div>
  `,
})
export class ClipsStudioComponent implements OnInit {
  private readonly api = inject(ApiService);
  readonly videos = signal<SourceVideo[]>([]);
  readonly clips = signal<Clip[]>([]);
  readonly error = signal<string | null>(null);
  selectedVideoId = '';

  ngOnInit(): void {
    this.api.listVideos().subscribe({
      next: (videos) => this.videos.set(videos),
      error: (err) => this.error.set(err?.message || 'Failed to load videos'),
    });
  }

  loadClips(): void {
    if (!this.selectedVideoId) {
      this.clips.set([]);
      return;
    }
    this.api.getVideoClips(this.selectedVideoId).subscribe({
      next: (clips) => this.clips.set(clips),
      error: (err) => this.error.set(err?.error?.detail || err?.message || 'Failed to load clips'),
    });
  }
}
