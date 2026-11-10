import { DecimalPipe, NgFor, NgIf } from '@angular/common';
import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subscription, switchMap, timer } from 'rxjs';

import { AudioStudioState, AudioTrack, Clip, ProcessingJob, Project } from '../../core/models';
import { ApiService } from '../../core/services/api.service';

@Component({
  selector: 'app-audio-studio',
  standalone: true,
  imports: [NgIf, NgFor, FormsModule, DecimalPipe],
  template: `
    <div class="space-y-6">
      <header>
        <div class="avc-label">Sound</div>
        <h1 class="avc-title mt-1">Audio Studio</h1>
        <p class="mt-2 max-w-2xl text-sm text-muted">
          Mix original, music, and voice-over tracks with sidechain ducking and EBU R128 loudness
          normalization. Settings apply on the next FFmpeg render.
        </p>
      </header>

      <section class="avc-panel grid gap-4 p-5 md:grid-cols-3">
        <label class="text-sm block">
          <span class="avc-label">Project</span>
          <select class="avc-input mt-2" [(ngModel)]="selectedProjectId" (ngModelChange)="loadClips()">
            <option value="">Select project</option>
            <option *ngFor="let project of projects()" [value]="project.id">{{ project.name }}</option>
          </select>
        </label>
        <label class="text-sm block md:col-span-2">
          <span class="avc-label">Clip</span>
          <select class="avc-input mt-2" [(ngModel)]="selectedClipId" (ngModelChange)="loadAudio()">
            <option value="">Select clip</option>
            <option *ngFor="let clip of clips()" [value]="clip.id">
              {{ clip.hook || clip.title || clip.id }} ({{ clip.duration_seconds | number: '1.1-1' }}s)
            </option>
          </select>
        </label>
      </section>

      <div *ngIf="error()" class="rounded-xl border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
        {{ error() }}
      </div>
      <div *ngIf="job()" class="avc-panel p-4 text-sm">
        {{ job()?.status }} · {{ job()?.message }} · {{ job()?.progress | number: '1.0-0' }}%
      </div>

      <ng-container *ngIf="state() as studio">
        <section class="avc-panel p-5 space-y-4">
          <div class="flex flex-wrap items-end justify-between gap-3">
            <div>
              <div class="avc-label">Mix preset</div>
              <div class="mt-1 text-sm text-muted">Duration {{ studio.duration_seconds | number: '1.1-1' }}s</div>
            </div>
            <div class="flex flex-wrap gap-2">
              <select class="avc-input" [(ngModel)]="presetSlug">
                <option value="">Custom</option>
                <option *ngFor="let preset of studio.audio_presets" [value]="preset.slug || preset.name">
                  {{ preset.name }}
                </option>
              </select>
              <button class="avc-btn-ghost" type="button" (click)="applyPreset()" [disabled]="!presetSlug">
                Apply preset
              </button>
              <button class="avc-btn-primary" type="button" (click)="render()" [disabled]="busy()">
                Render with mix
              </button>
            </div>
          </div>

          <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 text-sm">
            <label class="block">
              <span class="avc-label">Loudnorm</span>
              <select class="avc-input mt-2" [(ngModel)]="studio.mix_settings.enable_loudnorm" (ngModelChange)="saveMix()">
                <option [ngValue]="true">On (-14 LUFS)</option>
                <option [ngValue]="false">Off</option>
              </select>
            </label>
            <label class="block">
              <span class="avc-label">Limiter</span>
              <select class="avc-input mt-2" [(ngModel)]="studio.mix_settings.enable_limiter" (ngModelChange)="saveMix()">
                <option [ngValue]="true">On</option>
                <option [ngValue]="false">Off</option>
              </select>
            </label>
            <label class="block">
              <span class="avc-label">Duck threshold</span>
              <input
                class="avc-input mt-2"
                type="number"
                step="0.01"
                [(ngModel)]="studio.mix_settings.ducking_threshold"
                (change)="saveMix()"
              />
            </label>
            <label class="block">
              <span class="avc-label">Duck ratio</span>
              <input
                class="avc-input mt-2"
                type="number"
                step="0.5"
                [(ngModel)]="studio.mix_settings.ducking_ratio"
                (change)="saveMix()"
              />
            </label>
          </div>
        </section>

        <section class="space-y-3">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <h2 class="font-display text-lg font-semibold">Tracks</h2>
            <div class="flex flex-wrap gap-2 items-center">
              <select class="avc-input" [(ngModel)]="uploadType">
                <option value="music">Music</option>
                <option value="voiceover">Voice-over</option>
                <option value="replacement">Replacement</option>
              </select>
              <label class="avc-btn-ghost cursor-pointer">
                Upload
                <input type="file" class="hidden" accept="audio/*,.mp3,.wav,.m4a,.aac,.ogg,.flac" (change)="onUpload($event)" />
              </label>
            </div>
          </div>

          <article class="avc-panel p-4" *ngFor="let track of studio.tracks">
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div class="avc-label">{{ track.track_type }}</div>
                <div class="font-medium">{{ track.label }}</div>
                <div class="text-xs text-muted mt-1 break-all" *ngIf="track.source_path">{{ track.source_path }}</div>
              </div>
              <div class="flex gap-2" *ngIf="track.track_type !== 'original'">
                <button class="avc-btn-ghost text-xs" type="button" (click)="removeTrack(track)">Remove</button>
              </div>
            </div>

            <div class="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 text-sm">
              <label class="block">
                <span class="avc-label">Volume</span>
                <input
                  class="avc-input mt-2"
                  type="range"
                  min="0"
                  max="2"
                  step="0.05"
                  [(ngModel)]="track.volume"
                  (change)="patchTrack(track, { volume: track.volume })"
                />
                <div class="text-xs text-muted mt-1">{{ track.volume | number: '1.2-2' }}</div>
              </label>
              <label class="block">
                <span class="avc-label">Mute</span>
                <select
                  class="avc-input mt-2"
                  [(ngModel)]="track.muted"
                  (ngModelChange)="patchTrack(track, { muted: track.muted })"
                >
                  <option [ngValue]="false">Audible</option>
                  <option [ngValue]="true">Muted</option>
                </select>
              </label>
              <label class="block">
                <span class="avc-label">Offset (s)</span>
                <input
                  class="avc-input mt-2"
                  type="number"
                  step="0.1"
                  [(ngModel)]="track.offset_seconds"
                  (change)="patchTrack(track, { offset_seconds: track.offset_seconds })"
                />
              </label>
              <label class="block" *ngIf="track.track_type === 'music'">
                <span class="avc-label">Ducking</span>
                <select
                  class="avc-input mt-2"
                  [(ngModel)]="track.ducking_enabled"
                  (ngModelChange)="patchTrack(track, { ducking_enabled: track.ducking_enabled })"
                >
                  <option [ngValue]="true">Under speech</option>
                  <option [ngValue]="false">Off</option>
                </select>
              </label>
              <label class="block" *ngIf="track.track_type !== 'music'">
                <span class="avc-label">Fade in (s)</span>
                <input
                  class="avc-input mt-2"
                  type="number"
                  step="0.1"
                  [(ngModel)]="track.fade_in_seconds"
                  (change)="patchTrack(track, { fade_in_seconds: track.fade_in_seconds })"
                />
              </label>
            </div>

            <div class="mt-4">
              <div class="h-8 rounded-lg bg-canvas border border-line overflow-hidden relative">
                <div
                  class="absolute inset-y-0 left-0 rounded-lg"
                  [style.width.%]="laneWidth(track)"
                  [style.background]="laneColor(track)"
                ></div>
                <div class="absolute inset-0 flex items-center px-3 text-xs font-medium">
                  {{ track.label }} · {{ track.muted ? 'muted' : 'live' }}
                </div>
              </div>
            </div>
          </article>
        </section>
      </ng-container>
    </div>
  `,
})
export class AudioStudioComponent implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);
  private pollSub: Subscription | null = null;

  readonly projects = signal<Project[]>([]);
  readonly clips = signal<Clip[]>([]);
  readonly state = signal<AudioStudioState | null>(null);
  readonly job = signal<ProcessingJob | null>(null);
  readonly busy = signal(false);
  readonly error = signal<string | null>(null);

  selectedProjectId = '';
  selectedClipId = '';
  presetSlug = '';
  uploadType = 'music';

  ngOnInit(): void {
    this.api.listProjects().subscribe({
      next: (projects) => this.projects.set(projects),
      error: (err) => this.error.set(err?.message || 'Failed to load projects'),
    });
  }

  ngOnDestroy(): void {
    this.pollSub?.unsubscribe();
  }

  loadClips(): void {
    this.selectedClipId = '';
    this.state.set(null);
    if (!this.selectedProjectId) {
      this.clips.set([]);
      return;
    }
    this.api.getProjectClips(this.selectedProjectId).subscribe({
      next: (clips) => this.clips.set(clips),
      error: (err) => this.error.set(err?.error?.detail || 'Failed to load clips'),
    });
  }

  loadAudio(): void {
    if (!this.selectedClipId) {
      this.state.set(null);
      return;
    }
    this.api.getAudioStudio(this.selectedClipId).subscribe({
      next: (state) => {
        this.state.set(state);
        this.presetSlug = state.mix_settings.preset_slug || '';
      },
      error: (err) => this.error.set(err?.error?.detail || 'Failed to load audio studio'),
    });
  }

  saveMix(): void {
    const studio = this.state();
    if (!studio) return;
    this.api.updateMixSettings(studio.clip_id, studio.mix_settings).subscribe({
      next: (settings) => this.state.update((s) => (s ? { ...s, mix_settings: settings } : s)),
      error: (err) => this.error.set(err?.error?.detail || 'Failed to save mix settings'),
    });
  }

  applyPreset(): void {
    if (!this.selectedClipId || !this.presetSlug) return;
    this.api.applyAudioPreset(this.selectedClipId, this.presetSlug).subscribe({
      next: (state) => this.state.set(state),
      error: (err) => this.error.set(err?.error?.detail || 'Failed to apply preset'),
    });
  }

  patchTrack(track: AudioTrack, patch: Partial<AudioTrack>): void {
    this.api.updateAudioTrack(track.id, patch).subscribe({
      next: (updated) => {
        this.state.update((studio) => {
          if (!studio) return studio;
          return {
            ...studio,
            tracks: studio.tracks.map((item) => (item.id === updated.id ? updated : item)),
          };
        });
      },
      error: (err) => this.error.set(err?.error?.detail || 'Failed to update track'),
    });
  }

  removeTrack(track: AudioTrack): void {
    this.api.deleteAudioTrack(track.id).subscribe({
      next: () => this.loadAudio(),
      error: (err) => this.error.set(err?.error?.detail || 'Failed to delete track'),
    });
  }

  onUpload(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file || !this.selectedClipId) return;
    this.api
      .uploadAudioTrack(this.selectedClipId, this.uploadType, file, {
        ducking_enabled: this.uploadType === 'music',
        volume: this.uploadType === 'music' ? 0.35 : 1,
      })
      .subscribe({
        next: () => {
          input.value = '';
          this.loadAudio();
        },
        error: (err) => this.error.set(err?.error?.detail || 'Upload failed'),
      });
  }

  render(): void {
    if (!this.selectedClipId) return;
    this.busy.set(true);
    this.error.set(null);
    this.api.renderClip(this.selectedClipId, { burn_subtitles: true }).subscribe({
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
                if (updated.status === 'failed') {
                  this.error.set(updated.error || 'Render failed');
                }
              }
            },
          });
      },
      error: (err) => {
        this.busy.set(false);
        this.error.set(err?.error?.detail || 'Failed to queue render');
      },
    });
  }

  laneWidth(track: AudioTrack): number {
    return Math.max(8, Math.min(100, (track.muted ? 0.15 : track.volume) * 50));
  }

  laneColor(track: AudioTrack): string {
    if (track.muted) return 'rgba(148,163,184,0.35)';
    if (track.track_type === 'music') return 'rgba(34,197,94,0.45)';
    if (track.track_type === 'voiceover') return 'rgba(56,189,248,0.45)';
    if (track.track_type === 'replacement') return 'rgba(251,146,60,0.45)';
    return 'rgba(250,204,21,0.4)';
  }
}
