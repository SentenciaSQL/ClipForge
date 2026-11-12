import { DecimalPipe, NgFor, NgIf } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { Clip, Project, SourceVideo, SubtitlePreset } from '../../core/models';
import { ApiService } from '../../core/services/api.service';

@Component({
  selector: 'app-full-video-studio',
  standalone: true,
  imports: [NgIf, NgFor, FormsModule, DecimalPipe, RouterLink],
  template: `
    <div class="space-y-6">
      <header>
        <div class="avc-label">Dubbing</div>
        <h1 class="avc-title mt-1">Full video · Audio &amp; subtitles</h1>
        <p class="mt-2 max-w-2xl text-sm text-muted">
          Upload or pick a video and work on the whole file — replace audio and burn subtitles without
          generating short clips.
        </p>
      </header>

      <section class="avc-panel p-5 space-y-4">
        <div class="avc-label">1. Source video</div>
        <div class="grid gap-4 md:grid-cols-2">
          <label class="text-sm block">
            <span class="avc-label">Existing video</span>
            <select class="avc-input mt-2" [(ngModel)]="selectedVideoId" (ngModelChange)="onVideoPicked()">
              <option value="">Select imported video</option>
              <option *ngFor="let video of videos()" [value]="video.id">
                {{ video.original_filename || video.id }}
                <ng-container *ngIf="video.duration_seconds">
                  ({{ video.duration_seconds | number: '1.0-0' }}s)
                </ng-container>
              </option>
            </select>
          </label>
          <label class="text-sm block">
            <span class="avc-label">Or upload a new file</span>
            <input
              class="avc-input mt-2"
              type="file"
              accept="video/*,.mp4,.mov,.mkv,.webm"
              (change)="onUpload($event)"
              [disabled]="busy()"
            />
          </label>
        </div>
        <label class="text-sm block max-w-sm">
          <span class="avc-label">Subtitle preset</span>
          <select class="avc-input mt-2" [(ngModel)]="presetSlug">
            <option *ngFor="let preset of presets()" [value]="preset.slug">{{ preset.name }}</option>
          </select>
        </label>
      </section>

      <div *ngIf="error()" class="rounded-xl border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
        {{ error() }}
      </div>
      <div *ngIf="message()" class="rounded-xl border border-accent/30 bg-accent/10 px-4 py-3 text-sm text-accent">
        {{ message() }}
      </div>

      <section class="avc-panel p-5 space-y-4" *ngIf="selectedVideo() as video">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div class="avc-label">2. Create full-video job</div>
            <h2 class="font-display text-lg font-semibold mt-1">
              {{ video.original_filename || 'Video' }}
            </h2>
            <p class="text-xs text-muted mt-1">
              Duration {{ video.duration_seconds | number: '1.1-1' }}s ·
              {{ video.width }}×{{ video.height }}
            </p>
          </div>
          <button class="avc-btn-primary" type="button" (click)="createJob()" [disabled]="busy()">
            {{ busy() ? 'Working…' : fullClip() ? 'Refresh full-video job' : 'Prepare full video' }}
          </button>
        </div>

        <div class="overflow-hidden rounded-xl border border-line bg-black/40 max-w-md">
          <video
            class="block w-full max-h-[360px] bg-black"
            controls
            playsinline
            preload="metadata"
            [src]="api.videoMediaUrl(video.id)"
          ></video>
        </div>
      </section>

      <section class="avc-panel p-5 space-y-3" *ngIf="fullClip() as clip">
        <div class="avc-label">3. Edit audio &amp; subtitles</div>
        <p class="text-sm text-muted">
          Job ready: {{ clip.title || clip.id }} · {{ clip.duration_seconds | number: '1.1-1' }}s
          (category {{ clip.category }})
        </p>
        <div class="flex flex-wrap gap-2">
          <a
            class="avc-btn-primary"
            [routerLink]="['/audio']"
            [queryParams]="{ project: clip.project_id, clip: clip.id }"
          >
            Open Audio Studio
          </a>
          <a
            class="avc-btn-ghost"
            [routerLink]="['/clips']"
            [queryParams]="{ video: clip.video_id, clip: clip.id }"
          >
            Open Clips Studio (styles / offset / export)
          </a>
        </div>
        <ol class="list-decimal pl-5 text-sm text-muted space-y-1">
          <li>In Audio Studio: mute original, upload replacement, Play preview, Use for subtitles.</li>
          <li>In Clips Studio: tweak styles, sync offset, Preview render / Export MP4.</li>
        </ol>
      </section>
    </div>
  `,
})
export class FullVideoStudioComponent implements OnInit {
  readonly api = inject(ApiService);

  readonly videos = signal<SourceVideo[]>([]);
  readonly projects = signal<Project[]>([]);
  readonly presets = signal<SubtitlePreset[]>([]);
  readonly fullClip = signal<Clip | null>(null);
  readonly busy = signal(false);
  readonly error = signal<string | null>(null);
  readonly message = signal<string | null>(null);

  selectedVideoId = '';
  presetSlug = 'hormozi';

  ngOnInit(): void {
    this.refreshVideos();
    this.api.listProjects().subscribe({
      next: (projects) => this.projects.set(projects),
    });
    this.api.listSubtitlePresets().subscribe({
      next: (presets) => {
        this.presets.set(presets);
        if (presets.length && !presets.some((p) => p.slug === this.presetSlug)) {
          this.presetSlug = presets[0].slug;
        }
      },
    });
  }

  selectedVideo(): SourceVideo | null {
    return this.videos().find((video) => video.id === this.selectedVideoId) || null;
  }

  onVideoPicked(): void {
    this.fullClip.set(null);
    this.message.set(null);
    this.error.set(null);
  }

  onUpload(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    this.busy.set(true);
    this.error.set(null);
    this.message.set(null);
    this.api.importVideo(file, undefined, file.name.replace(/\.[^.]+$/, '') || 'Dubbing').subscribe({
      next: (res) => {
        input.value = '';
        this.message.set(`Imported ${res.video.original_filename || res.video.id}`);
        this.refreshVideos(() => {
          this.selectedVideoId = res.video.id;
          this.createJob();
        });
      },
      error: (err) => {
        this.busy.set(false);
        this.error.set(err?.error?.detail || 'Import failed');
      },
    });
  }

  createJob(): void {
    if (!this.selectedVideoId) {
      this.error.set('Select or upload a video first');
      return;
    }
    this.busy.set(true);
    this.error.set(null);
    this.api.createFullVideoClip(this.selectedVideoId, this.presetSlug).subscribe({
      next: (res) => {
        this.fullClip.set(res.clip);
        this.message.set(res.message);
        this.busy.set(false);
      },
      error: (err) => {
        this.busy.set(false);
        this.error.set(err?.error?.detail || 'Failed to create full-video job');
      },
    });
  }

  private refreshVideos(done?: () => void): void {
    this.api.listVideos().subscribe({
      next: (videos) => {
        this.videos.set(videos);
        this.busy.set(false);
        done?.();
      },
      error: (err) => {
        this.busy.set(false);
        this.error.set(err?.error?.detail || 'Failed to load videos');
      },
    });
  }
}
