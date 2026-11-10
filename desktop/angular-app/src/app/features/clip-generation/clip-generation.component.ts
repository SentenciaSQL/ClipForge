import { DecimalPipe, NgFor, NgIf } from '@angular/common';
import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subscription, switchMap, timer } from 'rxjs';

import { ProcessingJob, SourceVideo, Transcription } from '../../core/models';
import { ApiService } from '../../core/services/api.service';

@Component({
  selector: 'app-clip-generation',
  standalone: true,
  imports: [FormsModule, NgIf, NgFor, DecimalPipe],
  template: `
    <div class="space-y-6">
      <header>
        <div class="avc-label">Pipeline</div>
        <h1 class="avc-title mt-1">Clip Generation</h1>
        <p class="mt-2 max-w-2xl text-sm text-muted">
          Phase 2 runs local audio extraction and Faster-Whisper transcription with live job progress.
          Highlight detection starts in Phase 3.
        </p>
      </header>

      <form class="avc-panel grid gap-4 p-5 md:grid-cols-2" (ngSubmit)="start()">
        <label class="text-sm md:col-span-2">
          <span class="avc-label">Source video</span>
          <select class="avc-input mt-2" [(ngModel)]="selectedVideoId" name="video" required>
            <option value="">Select imported video</option>
            <option *ngFor="let video of videos()" [value]="video.id">
              {{ video.original_filename }} ({{ video.duration_seconds | number: '1.0-1' }}s)
            </option>
          </select>
        </label>
        <label class="text-sm">
          <span class="avc-label">Min duration (s)</span>
          <input class="avc-input mt-2" type="number" [(ngModel)]="minDuration" name="min" min="12" max="30" />
        </label>
        <label class="text-sm">
          <span class="avc-label">Max duration (s)</span>
          <input class="avc-input mt-2" type="number" [(ngModel)]="maxDuration" name="max" min="12" max="30" />
        </label>
        <label class="text-sm">
          <span class="avc-label">Number of clips</span>
          <input class="avc-input mt-2" type="number" [(ngModel)]="clipCount" name="count" min="1" max="50" />
        </label>
        <label class="text-sm">
          <span class="avc-label">Language</span>
          <select class="avc-input mt-2" [(ngModel)]="language" name="language">
            <option value="auto">Automatic</option>
            <option value="en">English</option>
            <option value="es">Spanish</option>
            <option value="fr">French</option>
            <option value="de">German</option>
            <option value="pt">Portuguese</option>
          </select>
        </label>
        <label class="text-sm">
          <span class="avc-label">Whisper model</span>
          <select class="avc-input mt-2" [(ngModel)]="whisperModel" name="whisper">
            <option value="large-v3">large-v3</option>
            <option value="distil-large-v3">distil-large-v3</option>
            <option value="medium">medium</option>
            <option value="small">small</option>
            <option value="base">base</option>
            <option value="tiny">tiny</option>
          </select>
        </label>
        <label class="text-sm">
          <span class="avc-label">Subtitle preset</span>
          <select class="avc-input mt-2" [(ngModel)]="subtitlePreset" name="preset">
            <option value="hormozi">Hormozi</option>
            <option value="karaoke">Karaoke</option>
            <option value="tiktok">TikTok</option>
            <option value="minimal">Minimal</option>
            <option value="professional">Professional</option>
            <option value="custom">Custom</option>
          </select>
        </label>
        <label class="text-sm">
          <span class="avc-label">Reframing</span>
          <select class="avc-input mt-2" [(ngModel)]="reframe" name="reframe">
            <option value="auto">Automatic</option>
            <option value="smart_crop">Smart crop</option>
            <option value="center_crop">Center crop</option>
            <option value="blurred_bg">Blurred background</option>
          </select>
        </label>
        <div class="md:col-span-2 flex flex-wrap gap-3">
          <button class="avc-btn-primary" type="submit" [disabled]="!selectedVideoId || busy()">
            Run transcription
          </button>
          <button class="avc-btn-ghost" type="button" *ngIf="job()" (click)="cancel()" [disabled]="!busy()">
            Cancel
          </button>
        </div>
      </form>

      <div *ngIf="error()" class="rounded-xl border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
        {{ error() }}
      </div>

      <section class="avc-panel p-5" *ngIf="job() as j">
        <div class="avc-label">Live progress</div>
        <div class="mt-2 flex items-center justify-between gap-3">
          <div class="text-sm">{{ j.status }} · {{ j.current_stage }} — {{ j.message }}</div>
          <div class="font-display text-2xl font-semibold">{{ j.progress | number: '1.0-0' }}%</div>
        </div>
        <div class="mt-4 h-2 overflow-hidden rounded-full bg-canvas">
          <div class="h-full bg-accent" [style.width.%]="j.progress"></div>
        </div>
      </section>

      <section class="avc-panel p-5" *ngIf="transcription() as tx">
        <div class="avc-label">Latest transcription</div>
        <p class="mt-2 text-sm text-muted">
          {{ tx.language }} · {{ tx.segment_count }} segments · {{ tx.word_count }} words
        </p>
        <p class="mt-3 whitespace-pre-wrap text-sm">{{ tx.full_text }}</p>
      </section>
    </div>
  `,
})
export class ClipGenerationComponent implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);
  private pollSub: Subscription | null = null;

  readonly videos = signal<SourceVideo[]>([]);
  readonly job = signal<ProcessingJob | null>(null);
  readonly transcription = signal<Transcription | null>(null);
  readonly busy = signal(false);
  readonly error = signal<string | null>(null);

  selectedVideoId = '';
  minDuration = 12;
  maxDuration = 30;
  clipCount = 5;
  language = 'auto';
  whisperModel = 'small';
  subtitlePreset = 'hormozi';
  reframe = 'auto';

  ngOnInit(): void {
    this.api.listVideos().subscribe({
      next: (videos) => this.videos.set(videos),
      error: (err) => this.error.set(err?.message || 'Failed to load videos'),
    });
  }

  ngOnDestroy(): void {
    this.pollSub?.unsubscribe();
  }

  start(): void {
    if (!this.selectedVideoId) {
      return;
    }
    this.busy.set(true);
    this.error.set(null);
    this.transcription.set(null);
    this.api
      .analyzeVideo(this.selectedVideoId, {
        language: this.language === 'auto' ? null : this.language,
        whisper_model: this.whisperModel,
        clip_count: this.clipCount,
        min_duration: this.minDuration,
        max_duration: this.maxDuration,
        subtitle_preset: this.subtitlePreset,
        reframing_mode: this.reframe,
      })
      .subscribe({
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
                  if (updated.status === 'completed') {
                    this.api.getVideoTranscription(this.selectedVideoId).subscribe({
                      next: (tx) => this.transcription.set(tx),
                    });
                  }
                  if (updated.status === 'failed') {
                    this.error.set(updated.error || 'Job failed');
                  }
                }
              },
            });
        },
        error: (err) => {
          this.busy.set(false);
          this.error.set(err?.error?.detail || err?.message || 'Failed to start');
        },
      });
  }

  cancel(): void {
    const current = this.job();
    if (!current) {
      return;
    }
    this.api.cancelJob(current.id).subscribe();
  }
}
