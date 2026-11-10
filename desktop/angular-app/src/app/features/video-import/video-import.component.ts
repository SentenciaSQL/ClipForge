import { DecimalPipe, NgFor, NgIf } from '@angular/common';
import { Component, OnDestroy, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subscription, switchMap, timer } from 'rxjs';

import { Clip, ProcessingJob, Project, SourceVideo, Transcription, VideoImportResponse } from '../../core/models';
import { ApiService } from '../../core/services/api.service';

@Component({
  selector: 'app-video-import',
  standalone: true,
  imports: [NgIf, NgFor, FormsModule, DecimalPipe],
  template: `
    <div class="space-y-6">
      <header>
        <div class="avc-label">Ingest</div>
        <h1 class="avc-title mt-1">Video Import</h1>
        <p class="mt-2 max-w-2xl text-sm text-muted">
          Drop long-form footage locally. Metadata is extracted with FFprobe — originals are never overwritten.
        </p>
      </header>

      <section
        class="avc-panel relative flex min-h-56 cursor-pointer flex-col items-center justify-center gap-3 border-dashed p-8 text-center transition"
        [class.border-accent]="dragging()"
        (dragover)="onDragOver($event)"
        (dragleave)="dragging.set(false)"
        (drop)="onDrop($event)"
        (click)="fileInput.click()"
      >
        <div class="font-display text-xl font-semibold">Drag & drop a video</div>
        <p class="max-w-md text-sm text-muted">
          MP4, MOV, MKV, AVI, WEBM and other FFmpeg-supported formats.
        </p>
        <button type="button" class="avc-btn-primary" (click)="$event.stopPropagation(); fileInput.click()">
          Choose file
        </button>
        <input
          #fileInput
          type="file"
          class="hidden"
          accept="video/*,.mp4,.mov,.mkv,.avi,.webm,.m4v"
          (change)="onFileSelected($event)"
        />
      </section>

      <section class="avc-panel grid gap-4 p-5 md:grid-cols-2">
        <label class="block text-sm">
          <span class="avc-label">Project name (new)</span>
          <input class="avc-input mt-2" [(ngModel)]="projectName" placeholder="My Podcast Episode" />
        </label>
        <label class="block text-sm">
          <span class="avc-label">Existing project (optional)</span>
          <select class="avc-input mt-2" [(ngModel)]="selectedProjectId">
            <option value="">Create new project</option>
            <option *ngFor="let project of projects()" [value]="project.id">{{ project.name }}</option>
          </select>
        </label>
        <label class="block text-sm">
          <span class="avc-label">Whisper model</span>
          <select class="avc-input mt-2" [(ngModel)]="whisperModel">
            <option value="large-v3">large-v3</option>
            <option value="distil-large-v3">distil-large-v3</option>
            <option value="medium">medium</option>
            <option value="small">small</option>
            <option value="base">base</option>
            <option value="tiny">tiny</option>
          </select>
        </label>
        <label class="block text-sm">
          <span class="avc-label">Language</span>
          <select class="avc-input mt-2" [(ngModel)]="language">
            <option value="auto">Automatic</option>
            <option value="en">English</option>
            <option value="es">Spanish</option>
            <option value="fr">French</option>
            <option value="de">German</option>
            <option value="pt">Portuguese</option>
          </select>
        </label>
      </section>

      <div *ngIf="busy()" class="rounded-xl border border-accent/30 bg-accent/10 px-4 py-3 text-sm text-accent">
        {{ busyMessage() }}
      </div>
      <div *ngIf="error()" class="rounded-xl border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
        {{ error() }}
      </div>

      <section class="avc-panel p-5" *ngIf="result() as r">
        <div class="avc-label">Imported</div>
        <h2 class="mt-2 font-display text-xl font-semibold">{{ r.video.original_filename }}</h2>
        <p class="mt-1 text-sm text-muted">
          Project: {{ r.project.name }} · Status: {{ r.video.status }}
        </p>
        <dl class="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 text-sm">
          <div *ngFor="let row of metaRows(r.video)">
            <dt class="text-muted">{{ row.label }}</dt>
            <dd class="mt-1 font-medium">{{ row.value }}</dd>
          </div>
        </dl>
        <div class="mt-5 flex flex-wrap gap-3">
          <button type="button" class="avc-btn-primary" (click)="queueAnalyze(r.video.id)" [disabled]="busy()">
            Analyze & find clips
          </button>
          <button
            type="button"
            class="avc-btn-ghost"
            *ngIf="activeJob() as job"
            (click)="cancelActive()"
            [disabled]="job.status === 'completed' || job.status === 'failed' || job.status === 'cancelled'"
          >
            Cancel job
          </button>
        </div>
      </section>

      <section class="avc-panel p-5" *ngIf="activeJob() as job">
        <div class="avc-label">Processing job</div>
        <div class="mt-2 flex flex-wrap items-center justify-between gap-3">
          <div>
            <div class="font-medium">{{ job.status }} · {{ job.current_stage || '—' }}</div>
            <div class="text-sm text-muted">{{ job.message }}</div>
          </div>
          <div class="font-display text-2xl font-semibold">{{ job.progress | number: '1.0-0' }}%</div>
        </div>
        <div class="mt-4 h-2 overflow-hidden rounded-full bg-canvas">
          <div class="h-full bg-accent transition-all" [style.width.%]="job.progress"></div>
        </div>
        <ul class="mt-4 grid gap-2 sm:grid-cols-2 text-xs text-muted">
          <li *ngFor="let stage of job.stages_json || []">
            {{ stage['stage'] }} — {{ stage['status'] }}
          </li>
        </ul>
      </section>

      <section class="avc-panel p-5" *ngIf="transcription() as tx">
        <div class="avc-label">Transcription</div>
        <h2 class="mt-2 font-display text-xl font-semibold">
          {{ tx.language || 'unknown' }} · {{ tx.word_count }} words · {{ tx.model_name }}
        </h2>
        <p class="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-ink">{{ tx.full_text }}</p>
        <div class="mt-4 max-h-64 overflow-auto rounded-xl border border-line bg-canvas/60 p-3 text-xs text-muted">
          <div *ngFor="let segment of tx.segments || []" class="mb-2">
            [{{ segment.start | number: '1.1-1' }}s–{{ segment.end | number: '1.1-1' }}s] {{ segment.text }}
          </div>
        </div>
      </section>

      <section class="avc-panel p-5" *ngIf="clips().length">
        <div class="avc-label">Selected clips</div>
        <div class="mt-4 space-y-3">
          <article class="rounded-xl border border-line bg-canvas/40 p-3" *ngFor="let clip of clips()">
            <div class="flex items-center justify-between gap-3">
              <div class="font-medium">{{ clip.hook }}</div>
              <div class="text-accent font-display text-lg">{{ clip.score | number: '1.0-0' }}</div>
            </div>
            <div class="mt-1 text-xs text-muted">
              {{ clip.start_seconds | number: '1.1-1' }}s–{{ clip.end_seconds | number: '1.1-1' }}s ·
              {{ clip.category }}
            </div>
            <p class="mt-2 text-sm">{{ clip.transcript }}</p>
          </article>
        </div>
      </section>
    </div>
  `,
})
export class VideoImportComponent implements OnDestroy {
  private readonly api = inject(ApiService);
  private pollSub: Subscription | null = null;

  readonly projects = signal<Project[]>([]);
  readonly result = signal<VideoImportResponse | null>(null);
  readonly busy = signal(false);
  readonly busyMessage = signal('Working…');
  readonly dragging = signal(false);
  readonly error = signal<string | null>(null);
  readonly activeJob = signal<ProcessingJob | null>(null);
  readonly transcription = signal<Transcription | null>(null);
  readonly clips = signal<Clip[]>([]);

  projectName = '';
  selectedProjectId = '';
  whisperModel = 'small';
  language = 'auto';

  constructor() {
    this.api.listProjects().subscribe({
      next: (projects) => this.projects.set(projects),
      error: () => undefined,
    });
  }

  ngOnDestroy(): void {
    this.pollSub?.unsubscribe();
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.dragging.set(true);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragging.set(false);
    const file = event.dataTransfer?.files?.[0];
    if (file) {
      this.importFile(file);
    }
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (file) {
      this.importFile(file);
    }
  }

  importFile(file: File): void {
    this.busy.set(true);
    this.busyMessage.set('Importing and extracting metadata…');
    this.error.set(null);
    this.transcription.set(null);
    this.clips.set([]);
    this.activeJob.set(null);
    this.api
      .importVideo(
        file,
        this.selectedProjectId || undefined,
        this.projectName || file.name.replace(/\.[^.]+$/, '')
      )
      .subscribe({
        next: (response) => {
          this.result.set(response);
          this.busy.set(false);
          this.api.listProjects().subscribe((projects) => this.projects.set(projects));
        },
        error: (err) => {
          this.busy.set(false);
          this.error.set(err?.error?.detail || err?.message || 'Import failed');
        },
      });
  }

  queueAnalyze(videoId: string): void {
    this.busy.set(true);
    this.busyMessage.set('Queueing analysis job…');
    this.error.set(null);
    this.transcription.set(null);
    this.clips.set([]);
    this.api
      .analyzeVideo(videoId, {
        whisper_model: this.whisperModel,
        language: this.language === 'auto' ? null : this.language,
        force: false,
      })
      .subscribe({
        next: (job) => {
          this.activeJob.set(job);
          this.busyMessage.set('Running local transcription + Ollama highlight detection…');
          this.startPolling(job.id, videoId);
        },
        error: (err) => {
          this.busy.set(false);
          this.error.set(err?.error?.detail || err?.message || 'Failed to queue analysis');
        },
      });
  }

  cancelActive(): void {
    const job = this.activeJob();
    if (!job) {
      return;
    }
    this.api.cancelJob(job.id).subscribe({
      next: () => this.busyMessage.set('Cancellation requested…'),
      error: (err) => this.error.set(err?.error?.detail || 'Cancel failed'),
    });
  }

  private startPolling(jobId: string, videoId: string): void {
    this.pollSub?.unsubscribe();
    this.pollSub = timer(0, 1500)
      .pipe(switchMap(() => this.api.getJob(jobId)))
      .subscribe({
        next: (job) => {
          this.activeJob.set(job);
          if (['completed', 'failed', 'cancelled'].includes(job.status)) {
            this.busy.set(false);
            this.pollSub?.unsubscribe();
            this.pollSub = null;
            if (job.status === 'completed') {
              this.api.getVideoTranscription(videoId).subscribe({
                next: (tx) => this.transcription.set(tx),
                error: () => undefined,
              });
              this.api.getVideoClips(videoId).subscribe({
                next: (clips) => this.clips.set(clips),
                error: () => undefined,
              });
            }
            if (job.status === 'failed') {
              this.error.set(job.error || job.message || 'Job failed');
            }
          }
        },
        error: (err) => {
          this.busy.set(false);
          this.error.set(err?.message || 'Failed to poll job');
          this.pollSub?.unsubscribe();
          this.pollSub = null;
        },
      });
  }

  metaRows(video: SourceVideo): Array<{ label: string; value: string }> {
    return [
      { label: 'Duration', value: video.duration_seconds != null ? `${video.duration_seconds.toFixed(2)} s` : '—' },
      {
        label: 'Resolution',
        value: video.width && video.height ? `${video.width}×${video.height}` : '—',
      },
      { label: 'FPS', value: video.fps != null ? video.fps.toFixed(3) : '—' },
      { label: 'Video codec', value: video.video_codec || '—' },
      { label: 'Audio codec', value: video.audio_codec || '—' },
      { label: 'Aspect ratio', value: video.aspect_ratio || '—' },
      {
        label: 'File size',
        value: `${(video.file_size_bytes / (1024 * 1024)).toFixed(2)} MB`,
      },
      {
        label: 'Bitrate',
        value: video.bitrate != null ? `${Math.round(video.bitrate / 1000)} kbps` : '—',
      },
    ];
  }
}
