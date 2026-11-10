import { DecimalPipe, NgFor, NgIf } from '@angular/common';
import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subscription, switchMap, timer } from 'rxjs';

import { Clip, ProcessingJob, SourceVideo, Speaker, Transcription } from '../../core/models';
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
          Runs local audio extraction, Faster-Whisper transcription, and Ollama semantic highlight
          detection with live job progress.
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
            Run full analysis
          </button>
          <button
            class="avc-btn-ghost"
            type="button"
            (click)="runDiarization()"
            [disabled]="!selectedVideoId || busy()"
          >
            Detect speakers (optional)
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

      <section class="avc-panel p-5" *ngIf="speakers().length">
        <div class="avc-label">Speakers</div>
        <div class="mt-3 flex flex-wrap gap-2">
          <div
            class="rounded-lg border border-line px-3 py-2 text-sm"
            *ngFor="let speaker of speakers()"
            [style.borderColor]="speakerColor(speaker.label)"
          >
            <span class="font-medium">{{ speaker.display_name || speaker.label }}</span>
            <span class="text-xs text-muted ml-2">{{ speaker.label }}</span>
          </div>
        </div>
      </section>

      <section class="avc-panel p-5" *ngIf="transcription() as tx">
        <div class="avc-label">Latest transcription</div>
        <p class="mt-2 text-sm text-muted">
          {{ tx.language }} · {{ tx.segment_count }} segments · {{ tx.word_count }} words
        </p>
        <div class="mt-3 space-y-2" *ngIf="tx.segments?.length; else plainText">
          <p class="text-sm" *ngFor="let seg of tx.segments">
            <span
              class="mr-2 inline-block rounded px-1.5 py-0.5 text-[10px] uppercase tracking-wide"
              [style.background]="speakerColor(seg.speaker_label || '')"
              *ngIf="seg.speaker_label"
              >{{ speakerName(seg.speaker_label) }}</span
            >
            {{ seg.text }}
          </p>
        </div>
        <ng-template #plainText>
          <p class="mt-3 whitespace-pre-wrap text-sm">{{ tx.full_text }}</p>
        </ng-template>
      </section>

      <section class="avc-panel p-5" *ngIf="clips().length">
        <div class="avc-label">Selected clips</div>
        <div class="mt-4 space-y-3">
          <article class="rounded-xl border border-line bg-canvas/50 p-3" *ngFor="let clip of clips()">
            <div class="flex justify-between gap-3">
              <strong>{{ clip.hook }}</strong>
              <span class="text-accent">{{ clip.score | number: '1.0-0' }}</span>
            </div>
            <div class="text-xs text-muted mt-1">
              {{ clip.start_seconds | number: '1.1-1' }}s–{{ clip.end_seconds | number: '1.1-1' }}s
            </div>
            <p class="text-sm mt-2">{{ clip.transcript }}</p>
          </article>
        </div>
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
  readonly clips = signal<Clip[]>([]);
  readonly speakers = signal<Speaker[]>([]);
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
    this.clips.set([]);
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
                    this.api.getVideoClips(this.selectedVideoId).subscribe({
                      next: (clips) => this.clips.set(clips),
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

  runDiarization(): void {
    if (!this.selectedVideoId) return;
    this.busy.set(true);
    this.error.set(null);
    this.api.diarizeVideo(this.selectedVideoId, { engine: 'local', max_speakers: 2 }).subscribe({
      next: (job) => {
        this.job.set(job);
        this.pollSub?.unsubscribe();
        this.pollSub = timer(0, 1200)
          .pipe(switchMap(() => this.api.getJob(job.id)))
          .subscribe({
            next: (updated) => {
              this.job.set(updated);
              if (['completed', 'failed', 'cancelled'].includes(updated.status)) {
                this.busy.set(false);
                this.pollSub?.unsubscribe();
                this.pollSub = null;
                if (updated.status === 'completed') {
                  this.api.listSpeakers(this.selectedVideoId).subscribe({
                    next: (speakers) => this.speakers.set(speakers),
                  });
                  this.api.getVideoTranscription(this.selectedVideoId).subscribe({
                    next: (tx) => this.transcription.set(tx),
                  });
                }
                if (updated.status === 'failed') {
                  this.error.set(updated.error || 'Diarization failed');
                }
              }
            },
          });
      },
      error: (err) => {
        this.busy.set(false);
        this.error.set(err?.error?.detail || 'Failed to start diarization');
      },
    });
  }

  speakerColor(label: string): string {
    if (!label) return 'rgba(148,163,184,0.35)';
    const palette = [
      'rgba(250,204,21,0.35)',
      'rgba(56,189,248,0.35)',
      'rgba(34,197,94,0.35)',
      'rgba(251,146,60,0.35)',
      'rgba(244,114,182,0.35)',
    ];
    let hash = 0;
    for (let i = 0; i < label.length; i++) hash = (hash + label.charCodeAt(i) * (i + 1)) % palette.length;
    return palette[hash];
  }

  speakerName(label: string): string {
    const match = this.speakers().find((item) => item.label === label);
    return match?.display_name || label;
  }
}
