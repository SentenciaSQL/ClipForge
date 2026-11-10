import { NgFor, NgIf } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { Project, SourceVideo, VideoImportResponse } from '../../core/models';
import { ApiService } from '../../core/services/api.service';

@Component({
  selector: 'app-video-import',
  standalone: true,
  imports: [NgIf, NgFor, FormsModule],
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
      </section>

      <div *ngIf="busy()" class="rounded-xl border border-accent/30 bg-accent/10 px-4 py-3 text-sm text-accent">
        Importing and extracting metadata…
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
            Queue analysis job
          </button>
          <span class="text-xs text-muted self-center" *ngIf="jobMessage()">{{ jobMessage() }}</span>
        </div>
      </section>
    </div>
  `,
})
export class VideoImportComponent {
  private readonly api = inject(ApiService);

  readonly projects = signal<Project[]>([]);
  readonly result = signal<VideoImportResponse | null>(null);
  readonly busy = signal(false);
  readonly dragging = signal(false);
  readonly error = signal<string | null>(null);
  readonly jobMessage = signal<string | null>(null);

  projectName = '';
  selectedProjectId = '';

  constructor() {
    this.api.listProjects().subscribe({
      next: (projects) => this.projects.set(projects),
      error: () => undefined,
    });
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
    this.error.set(null);
    this.jobMessage.set(null);
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
    this.api.analyzeVideo(videoId, { clip_count: 5 }).subscribe({
      next: (job) => {
        this.busy.set(false);
        this.jobMessage.set(`Job ${job.id} queued (${job.status}). Full pipeline starts in Phase 2+.`);
      },
      error: (err) => {
        this.busy.set(false);
        this.error.set(err?.error?.detail || err?.message || 'Failed to queue analysis');
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
