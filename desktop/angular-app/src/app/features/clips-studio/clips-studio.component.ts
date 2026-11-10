import { DecimalPipe, NgFor, NgIf } from '@angular/common';
import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subscription, switchMap, timer } from 'rxjs';

import { Clip, ProcessingJob, SourceVideo } from '../../core/models';
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
          Review scored candidates, adjust reframing/subtitles, and render vertical shorts locally with FFmpeg.
        </p>
      </header>

      <section class="avc-panel grid gap-4 p-5 md:grid-cols-3">
        <label class="text-sm md:col-span-2 block">
          <span class="avc-label">Source video</span>
          <select class="avc-input mt-2" [(ngModel)]="selectedVideoId" (ngModelChange)="loadClips()">
            <option value="">Select a video</option>
            <option *ngFor="let video of videos()" [value]="video.id">
              {{ video.original_filename }}
            </option>
          </select>
        </label>
        <label class="text-sm block">
          <span class="avc-label">Default reframe</span>
          <select class="avc-input mt-2" [(ngModel)]="reframeMode">
            <option value="auto">Automatic</option>
            <option value="smart_crop">Smart crop</option>
            <option value="center_crop">Center crop</option>
            <option value="blurred_bg">Blurred background</option>
            <option value="podcast">Podcast</option>
            <option value="gaming">Gaming</option>
            <option value="tutorial">Tutorial</option>
          </select>
        </label>
      </section>

      <div *ngIf="error()" class="rounded-xl border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
        {{ error() }}
      </div>
      <div *ngIf="job()" class="avc-panel p-4 text-sm">
        Render job: {{ job()?.status }} · {{ job()?.current_stage }} · {{ job()?.progress | number: '1.0-0' }}%
        <div class="text-muted mt-1">{{ job()?.message }}</div>
      </div>

      <section class="grid gap-4 lg:grid-cols-2" *ngIf="clips().length; else empty">
        <article class="avc-panel p-5" *ngFor="let clip of clips()">
          <div class="flex items-start justify-between gap-3">
            <div>
              <div class="avc-label">{{ clip.category || 'general' }} · {{ clip.status }}</div>
              <h2 class="mt-1 font-display text-lg font-semibold">{{ clip.hook || clip.title }}</h2>
            </div>
            <div class="font-display text-2xl font-semibold text-accent">{{ clip.score | number: '1.0-0' }}</div>
          </div>
          <p class="mt-3 text-xs text-muted">
            {{ clip.start_seconds | number: '1.1-1' }}s → {{ clip.end_seconds | number: '1.1-1' }}s
            ({{ clip.duration_seconds | number: '1.1-1' }}s)
          </p>
          <p class="mt-3 text-sm leading-relaxed">{{ clip.transcript }}</p>
          <div class="mt-4 flex flex-wrap gap-2">
            <button class="avc-btn-primary" type="button" (click)="render(clip)" [disabled]="busy()">
              Render 9:16
            </button>
            <button class="avc-btn-ghost" type="button" *ngIf="clip.output_path" (click)="copyPath(clip)">
              Copy output path
            </button>
          </div>
          <p class="mt-2 text-xs text-muted" *ngIf="clip.output_path">{{ clip.output_path }}</p>
        </article>
      </section>
      <ng-template #empty>
        <div class="avc-panel p-8 text-sm text-muted">
          No clips yet. Run analysis from Import or Generate first.
        </div>
      </ng-template>
    </div>
  `,
})
export class ClipsStudioComponent implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);
  private pollSub: Subscription | null = null;

  readonly videos = signal<SourceVideo[]>([]);
  readonly clips = signal<Clip[]>([]);
  readonly job = signal<ProcessingJob | null>(null);
  readonly busy = signal(false);
  readonly error = signal<string | null>(null);
  selectedVideoId = '';
  reframeMode = 'auto';

  ngOnInit(): void {
    this.api.listVideos().subscribe({
      next: (videos) => this.videos.set(videos),
      error: (err) => this.error.set(err?.message || 'Failed to load videos'),
    });
  }

  ngOnDestroy(): void {
    this.pollSub?.unsubscribe();
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

  render(clip: Clip): void {
    this.busy.set(true);
    this.error.set(null);
    this.api.renderClip(clip.id, { reframing_mode: this.reframeMode, burn_subtitles: true }).subscribe({
      next: (job) => {
        this.job.set(job);
        this.pollSub?.unsubscribe();
        this.pollSub = timer(0, 1500)
          .pipe(switchMap(() => this.api.getJob(job.id)))
          .subscribe({
            next: (updated) => {
              this.job.set(updated);
              if (['completed', 'failed', 'cancelled'].includes(updated.status)) {
                this.busy.set(false);
                this.pollSub?.unsubscribe();
                this.pollSub = null;
                this.loadClips();
                if (updated.status === 'failed') {
                  this.error.set(updated.error || 'Render failed');
                }
              }
            },
          });
      },
      error: (err) => {
        this.busy.set(false);
        this.error.set(err?.error?.detail || err?.message || 'Failed to queue render');
      },
    });
  }

  copyPath(clip: Clip): void {
    if (clip.output_path && navigator.clipboard) {
      navigator.clipboard.writeText(clip.output_path);
    }
  }
}
