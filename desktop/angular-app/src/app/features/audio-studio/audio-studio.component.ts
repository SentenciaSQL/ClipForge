import { DecimalPipe, NgFor, NgIf } from '@angular/common';
import {
  AfterViewChecked,
  Component,
  ElementRef,
  OnDestroy,
  OnInit,
  QueryList,
  ViewChildren,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subscription, switchMap, timer } from 'rxjs';

import {
  AudioStudioState,
  AudioTrack,
  Clip,
  ClipWaveforms,
  ProcessingJob,
  Project,
  WaveformTrack,
} from '../../core/models';
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
          Mix tracks with real waveform timelines, ducking, and loudnorm. Changes apply on the next render.
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

          <article class="avc-panel p-4" *ngFor="let track of studio.tracks; let i = index">
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div class="avc-label">{{ track.track_type }}</div>
                <div class="font-medium">{{ track.label }}</div>
              </div>
              <div class="flex gap-2" *ngIf="track.track_type !== 'original'">
                <button class="avc-btn-ghost text-xs" type="button" (click)="removeTrack(track)">Remove</button>
              </div>
            </div>

            <div class="mt-3 rounded-xl border border-line bg-canvas/70 p-2">
              <canvas
                #waveCanvas
                class="h-16 w-full"
                height="64"
                [attr.data-track-id]="track.id"
              ></canvas>
              <div class="mt-1 flex justify-between text-[10px] uppercase tracking-wide text-muted">
                <span>0s</span>
                <span>{{ studio.duration_seconds | number: '1.1-1' }}s</span>
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
            </div>
          </article>
        </section>
      </ng-container>
    </div>
  `,
})
export class AudioStudioComponent implements OnInit, OnDestroy, AfterViewChecked {
  private readonly api = inject(ApiService);
  private pollSub: Subscription | null = null;
  private paintedKey = '';

  @ViewChildren('waveCanvas') private waveCanvases!: QueryList<ElementRef<HTMLCanvasElement>>;

  readonly projects = signal<Project[]>([]);
  readonly clips = signal<Clip[]>([]);
  readonly state = signal<AudioStudioState | null>(null);
  readonly waveforms = signal<ClipWaveforms | null>(null);
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

  ngAfterViewChecked(): void {
    this.paintWaveforms();
  }

  loadClips(): void {
    this.selectedClipId = '';
    this.state.set(null);
    this.waveforms.set(null);
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
      this.waveforms.set(null);
      return;
    }
    this.api.getAudioStudio(this.selectedClipId).subscribe({
      next: (state) => {
        this.state.set(state);
        this.presetSlug = state.mix_settings.preset_slug || '';
        this.loadWaveforms();
      },
      error: (err) => this.error.set(err?.error?.detail || 'Failed to load audio studio'),
    });
  }

  loadWaveforms(): void {
    if (!this.selectedClipId) return;
    this.paintedKey = '';
    this.api.getClipWaveforms(this.selectedClipId).subscribe({
      next: (waves) => this.waveforms.set(waves),
      error: (err) => this.error.set(err?.error?.detail || 'Failed to load waveforms'),
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
      next: (state) => {
        this.state.set(state);
        this.loadWaveforms();
      },
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
        this.paintedKey = '';
        this.paintWaveforms();
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

  private paintWaveforms(): void {
    const data = this.waveforms();
    const studio = this.state();
    if (!data || !studio || !this.waveCanvases?.length) return;
    const key = `${data.clip_id}:${data.waveforms.map((w) => w.track_id).join(',')}:${studio.tracks
      .map((t) => `${t.id}:${t.muted}:${t.volume}`)
      .join('|')}`;
    if (key === this.paintedKey) return;
    this.paintedKey = key;

    const byId = new Map<string, WaveformTrack>(data.waveforms.map((item) => [item.track_id, item]));
    this.waveCanvases.forEach((ref) => {
      const canvas = ref.nativeElement;
      const trackId = canvas.getAttribute('data-track-id') || '';
      const wave = byId.get(trackId);
      const track = studio.tracks.find((item) => item.id === trackId);
      this.drawWave(canvas, wave?.peaks || [], track);
    });
  }

  private drawWave(canvas: HTMLCanvasElement, peaks: number[], track?: AudioTrack): void {
    const width = canvas.clientWidth || 640;
    canvas.width = width;
    canvas.height = 64;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, width, 64);
    ctx.fillStyle = 'rgba(15, 23, 42, 0.35)';
    ctx.fillRect(0, 0, width, 64);
    ctx.strokeStyle = 'rgba(148, 163, 184, 0.25)';
    ctx.beginPath();
    ctx.moveTo(0, 32);
    ctx.lineTo(width, 32);
    ctx.stroke();

    const color = this.waveColor(track);
    const count = peaks.length || 1;
    const barWidth = Math.max(width / count, 1);
    const gain = track?.muted ? 0.15 : Math.min(Math.max(track?.volume ?? 1, 0.2), 1.6);
    for (let i = 0; i < peaks.length; i++) {
      const amplitude = Math.max(peaks[i] * gain, 0.02);
      const h = amplitude * 54;
      const x = i * barWidth;
      const y = 32 - h / 2;
      ctx.fillStyle = color;
      ctx.fillRect(x, y, Math.max(barWidth * 0.7, 1), h);
    }
  }

  private waveColor(track?: AudioTrack): string {
    if (!track || track.muted) return 'rgba(148,163,184,0.55)';
    if (track.track_type === 'music') return 'rgba(34,197,94,0.85)';
    if (track.track_type === 'voiceover') return 'rgba(56,189,248,0.85)';
    if (track.track_type === 'replacement') return 'rgba(251,146,60,0.85)';
    return 'rgba(250,204,21,0.9)';
  }
}
