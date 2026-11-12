import { DecimalPipe, NgFor, NgIf } from '@angular/common';
import {
  AfterViewChecked,
  Component,
  ElementRef,
  OnDestroy,
  OnInit,
  QueryList,
  ViewChild,
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
          Mute or remove the original track, upload the audio you want, then generate subtitles from that
          audio so captions match what viewers hear. Use the live preview below to play video + new audio
          together before rendering.
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
      <div *ngIf="message()" class="rounded-xl border border-accent/30 bg-accent/10 px-4 py-3 text-sm text-accent">
        {{ message() }}
      </div>
      <div *ngIf="job()" class="avc-panel p-4 text-sm">
        {{ job()?.status }} · {{ job()?.message }} · {{ job()?.progress | number: '1.0-0' }}%
      </div>

      <ng-container *ngIf="state() as studio">
        <section class="avc-panel p-5 space-y-4" *ngIf="selectedClip() as clip">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div class="avc-label">Live mix preview</div>
              <h2 class="font-display text-lg font-semibold mt-1">{{ clip.hook || clip.title || 'Clip' }}</h2>
              <p class="text-xs text-muted mt-1">
                Plays the clip picture with your current track mix (mute / volume / offset). No render needed.
              </p>
            </div>
            <div class="flex flex-wrap gap-2">
              <button class="avc-btn-primary" type="button" (click)="togglePreview()">
                {{ previewPlaying() ? 'Pause' : 'Play preview' }}
              </button>
              <button class="avc-btn-ghost" type="button" (click)="restartPreview()">Restart</button>
            </div>
          </div>

          <div class="grid gap-4 lg:grid-cols-[minmax(0,280px)_1fr] items-start">
            <div class="overflow-hidden rounded-xl border border-line bg-black/40">
              <video
                #previewVideo
                class="block w-full max-h-[420px] bg-black"
                playsinline
                preload="auto"
                [muted]="videoMuted()"
                [src]="previewVideoUrl(clip)"
                (timeupdate)="onPreviewTimeUpdate()"
                (play)="onPreviewPlay()"
                (pause)="onPreviewPause()"
                (ended)="onPreviewEnded()"
                (seeked)="syncAudiosToVideo()"
              ></video>
            </div>
            <div class="space-y-3 text-sm">
              <div class="text-xs text-muted">
                {{ previewClock() }} / {{ studio.duration_seconds | number: '1.1-1' }}s
                · {{ previewStatusLabel() }}
              </div>
              <input
                class="w-full accent-[var(--avc-accent,#38bdf8)]"
                type="range"
                min="0"
                [max]="studio.duration_seconds"
                step="0.05"
                [ngModel]="previewPosition()"
                (ngModelChange)="seekPreview($event)"
              />
              <ul class="space-y-1 text-xs text-muted">
                <li *ngFor="let track of audiblePreviewTracks()">
                  {{ track.label }} · vol {{ track.volume | number: '1.2-2' }}
                  <span *ngIf="track.offset_seconds"> · offset {{ track.offset_seconds | number: '1.1-1' }}s</span>
                </li>
                <li *ngIf="!audiblePreviewTracks().length && videoMuted()">
                  No audible tracks — unmute original or upload replacement/VO/music.
                </li>
                <li *ngIf="!videoMuted()">Original dialogue comes from the video soundtrack.</li>
              </ul>
              <p class="text-xs text-muted">
                Ducking / loudnorm still need Render. This preview is for timing and balance.
              </p>
            </div>
          </div>

          <audio
            *ngFor="let track of previewableTracks()"
            #previewAudio
            preload="auto"
            [attr.data-track-id]="track.id"
            [src]="audioUrl(track)"
          ></audio>
        </section>

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
            <div>
              <h2 class="font-display text-lg font-semibold">Tracks</h2>
              <p class="text-xs text-muted mt-1">
                Tip: set type to Replacement, upload your file (original mutes automatically), hit Play preview to
                hear it with the video, then Use for subtitles.
              </p>
            </div>
            <div class="flex flex-wrap gap-2 items-center">
              <select class="avc-input" [(ngModel)]="uploadType">
                <option value="replacement">Replacement</option>
                <option value="voiceover">Voice-over</option>
                <option value="music">Music</option>
              </select>
              <label class="avc-btn-ghost cursor-pointer">
                Upload audio
                <input type="file" class="hidden" accept="audio/*,.mp3,.wav,.m4a,.aac,.ogg,.flac" (change)="onUpload($event)" />
              </label>
            </div>
          </div>

          <article class="avc-panel p-4" *ngFor="let track of studio.tracks; let i = index">
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div class="avc-label">{{ track.track_type }}</div>
                <div class="font-medium">{{ track.label }}</div>
                <p class="text-xs text-accent mt-1" *ngIf="track.track_type === 'original' && track.muted">
                  Original muted — replacement/VO will be heard on render.
                </p>
              </div>
              <div class="flex flex-wrap gap-2" *ngIf="track.track_type !== 'original'">
                <button
                  class="avc-btn-primary text-xs"
                  type="button"
                  *ngIf="canTranscribe(track)"
                  (click)="useForSubtitles(track)"
                  [disabled]="busy()"
                >
                  Use for subtitles
                </button>
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
  private syncing = false;

  @ViewChild('previewVideo') private previewVideo?: ElementRef<HTMLVideoElement>;
  @ViewChildren('previewAudio') private previewAudios!: QueryList<ElementRef<HTMLAudioElement>>;
  @ViewChildren('waveCanvas') private waveCanvases!: QueryList<ElementRef<HTMLCanvasElement>>;

  readonly projects = signal<Project[]>([]);
  readonly clips = signal<Clip[]>([]);
  readonly state = signal<AudioStudioState | null>(null);
  readonly waveforms = signal<ClipWaveforms | null>(null);
  readonly job = signal<ProcessingJob | null>(null);
  readonly busy = signal(false);
  readonly error = signal<string | null>(null);
  readonly previewPlaying = signal(false);
  readonly previewPosition = signal(0);

  selectedProjectId = '';
  selectedClipId = '';
  presetSlug = '';
  uploadType = 'replacement';
  readonly message = signal<string | null>(null);

  ngOnInit(): void {
    this.api.listProjects().subscribe({
      next: (projects) => this.projects.set(projects),
      error: (err) => this.error.set(err?.message || 'Failed to load projects'),
    });
  }

  ngOnDestroy(): void {
    this.pollSub?.unsubscribe();
    this.pausePreviewMedia();
  }

  ngAfterViewChecked(): void {
    this.paintWaveforms();
    this.applyTrackVolumes();
  }

  selectedClip(): Clip | null {
    return this.clips().find((clip) => clip.id === this.selectedClipId) || null;
  }

  videoMuted(): boolean {
    const original = this.state()?.tracks.find((track) => track.track_type === 'original');
    if (!original) return true;
    return Boolean(original.muted) || Number(original.volume || 0) <= 0.001;
  }

  previewableTracks(): AudioTrack[] {
    return (this.state()?.tracks || []).filter(
      (track) => track.track_type !== 'original' && Boolean(track.source_path) && !track.muted
    );
  }

  audiblePreviewTracks(): AudioTrack[] {
    return this.previewableTracks().filter((track) => Number(track.volume || 0) > 0.001);
  }

  previewVideoUrl(clip: Clip): string {
    const start = Math.max(0, Number(clip.start_seconds || 0));
    const end = Math.max(start + 0.1, Number(clip.end_seconds || start + (clip.duration_seconds || 1)));
    return `${this.api.videoMediaUrl(clip.video_id)}#t=${start.toFixed(2)},${end.toFixed(2)}`;
  }

  audioUrl(track: AudioTrack): string {
    const stamp = `${track.created_at || ''}:${track.volume}:${track.offset_seconds}:${track.muted}`;
    return `${this.api.audioTrackMediaUrl(track.id)}?t=${encodeURIComponent(stamp)}`;
  }

  previewStatusLabel(): string {
    if (this.previewPlaying()) return 'Playing live mix';
    if (this.audiblePreviewTracks().length) return 'Ready — video + uploaded audio';
    if (!this.videoMuted()) return 'Ready — original video audio';
    return 'Ready — muted';
  }

  previewClock(): string {
    return `${this.previewPosition().toFixed(1)}s`;
  }

  togglePreview(): void {
    const video = this.previewVideo?.nativeElement;
    if (!video) return;
    if (video.paused) {
      void this.playPreview();
    } else {
      this.pausePreviewMedia();
    }
  }

  async playPreview(): Promise<void> {
    const video = this.previewVideo?.nativeElement;
    const clip = this.selectedClip();
    if (!video || !clip) return;
    this.ensureVideoInClipWindow(video, clip);
    this.syncAudiosToVideo(true);
    try {
      await video.play();
      await this.playAudios();
      this.previewPlaying.set(true);
    } catch (err) {
      this.error.set(err instanceof Error ? err.message : 'Could not start preview playback');
      this.previewPlaying.set(false);
    }
  }

  restartPreview(): void {
    const video = this.previewVideo?.nativeElement;
    const clip = this.selectedClip();
    if (!video || !clip) return;
    const start = Math.max(0, Number(clip.start_seconds || 0));
    video.currentTime = start;
    this.previewPosition.set(0);
    this.syncAudiosToVideo(true);
    void this.playPreview();
  }

  seekPreview(relativeSeconds: number | string): void {
    const video = this.previewVideo?.nativeElement;
    const clip = this.selectedClip();
    const studio = this.state();
    if (!video || !clip || !studio) return;
    const duration = Math.max(0.1, Number(studio.duration_seconds || clip.duration_seconds || 1));
    const rel = Math.max(0, Math.min(duration, Number(relativeSeconds) || 0));
    const start = Math.max(0, Number(clip.start_seconds || 0));
    video.currentTime = start + rel;
    this.previewPosition.set(rel);
    this.syncAudiosToVideo(true);
  }

  onPreviewTimeUpdate(): void {
    const video = this.previewVideo?.nativeElement;
    const clip = this.selectedClip();
    const studio = this.state();
    if (!video || !clip || !studio) return;
    const start = Math.max(0, Number(clip.start_seconds || 0));
    const end = Math.max(start + 0.1, Number(clip.end_seconds || start + studio.duration_seconds));
    if (video.currentTime >= end - 0.05) {
      video.pause();
      this.pauseAudios();
      this.previewPlaying.set(false);
      this.previewPosition.set(studio.duration_seconds);
      return;
    }
    this.previewPosition.set(Math.max(0, video.currentTime - start));
    this.syncAudiosToVideo();
  }

  onPreviewPlay(): void {
    this.previewPlaying.set(true);
    void this.playAudios();
  }

  onPreviewPause(): void {
    this.previewPlaying.set(false);
    this.pauseAudios();
  }

  onPreviewEnded(): void {
    this.previewPlaying.set(false);
    this.pauseAudios();
  }

  syncAudiosToVideo(forceSeek = false): void {
    const video = this.previewVideo?.nativeElement;
    const clip = this.selectedClip();
    if (!video || !clip || this.syncing) return;
    this.syncing = true;
    try {
      const start = Math.max(0, Number(clip.start_seconds || 0));
      const clipTime = Math.max(0, video.currentTime - start);
      const byId = new Map((this.state()?.tracks || []).map((track) => [track.id, track]));
      this.previewAudios?.forEach((ref) => {
        const audio = ref.nativeElement;
        const trackId = audio.getAttribute('data-track-id') || '';
        const track = byId.get(trackId);
        if (!track) return;
        audio.volume = Math.max(0, Math.min(1, Number(track.volume || 0)));
        audio.muted = Boolean(track.muted) || audio.volume <= 0.001;
        const offset = Number(track.offset_seconds || 0);
        const target = Math.max(0, clipTime - offset);
        if (clipTime < offset - 0.02) {
          if (!audio.paused) audio.pause();
          if (forceSeek || Math.abs(audio.currentTime) > 0.05) audio.currentTime = 0;
          return;
        }
        if (forceSeek || Math.abs(audio.currentTime - target) > 0.25) {
          try {
            audio.currentTime = target;
          } catch {
            /* ignore seek race while metadata loads */
          }
        }
        if (!video.paused && audio.paused && !audio.muted) {
          void audio.play().catch(() => undefined);
        }
        if ((video.paused || audio.muted) && !audio.paused) {
          audio.pause();
        }
      });
    } finally {
      this.syncing = false;
    }
  }

  loadClips(): void {
    this.selectedClipId = '';
    this.state.set(null);
    this.waveforms.set(null);
    this.pausePreviewMedia();
    this.previewPosition.set(0);
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
    this.pausePreviewMedia();
    this.previewPosition.set(0);
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
        this.applyTrackVolumes();
        this.syncAudiosToVideo(true);
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

  canTranscribe(track: AudioTrack): boolean {
    return Boolean(track.source_path) && (track.track_type === 'replacement' || track.track_type === 'voiceover');
  }

  onUpload(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file || !this.selectedClipId) return;
    this.error.set(null);
    this.message.set(null);
    this.api
      .uploadAudioTrack(this.selectedClipId, this.uploadType, file, {
        ducking_enabled: this.uploadType === 'music',
        volume: this.uploadType === 'music' ? 0.35 : 1,
      })
      .subscribe({
        next: (track) => {
          input.value = '';
          this.loadAudio();
          if (this.canTranscribe(track)) {
            this.message.set(
              `Uploaded ${track.track_type}. Original muted. Use Play preview above to hear it with the video, then “Use for subtitles” and Render when ready.`
            );
          } else {
            this.message.set(
              'Audio track updated. Use Play preview above to hear the mix; Render with mix bakes ducking/loudnorm.'
            );
          }
        },
        error: (err) => this.error.set(err?.error?.detail || 'Upload failed'),
      });
  }

  useForSubtitles(track: AudioTrack): void {
    if (!this.selectedClipId || !this.canTranscribe(track)) return;
    this.busy.set(true);
    this.error.set(null);
    this.message.set(null);
    this.api
      .transcribeTrackForSubtitles(this.selectedClipId, track.id, { mute_original: true })
      .subscribe({
        next: (job) => this.pollJob(job, 'Subtitles aligned to your uploaded audio. Render to burn them in.'),
        error: (err) => {
          this.busy.set(false);
          this.error.set(err?.error?.detail || 'Failed to queue subtitle transcription');
        },
      });
  }

  render(): void {
    if (!this.selectedClipId) return;
    this.busy.set(true);
    this.error.set(null);
    this.message.set(null);
    this.api.renderClip(this.selectedClipId, { burn_subtitles: true }).subscribe({
      next: (job) => this.pollJob(job, 'Render finished with the current audio mix and subtitles.'),
      error: (err) => {
        this.busy.set(false);
        this.error.set(err?.error?.detail || 'Failed to queue render');
      },
    });
  }

  private pollJob(job: ProcessingJob, successMessage: string): void {
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
              this.error.set(updated.error || 'Job failed');
            } else if (updated.status === 'completed') {
              this.message.set(updated.message || successMessage);
              this.loadAudio();
            }
          }
        },
      });
  }

  private ensureVideoInClipWindow(video: HTMLVideoElement, clip: Clip): void {
    const start = Math.max(0, Number(clip.start_seconds || 0));
    const end = Math.max(start + 0.1, Number(clip.end_seconds || start + (clip.duration_seconds || 1)));
    if (video.currentTime < start || video.currentTime >= end) {
      video.currentTime = start;
      this.previewPosition.set(0);
    }
  }

  private async playAudios(): Promise<void> {
    const tasks: Promise<void>[] = [];
    this.previewAudios?.forEach((ref) => {
      const audio = ref.nativeElement;
      if (audio.muted) return;
      tasks.push(audio.play().then(() => undefined).catch(() => undefined));
    });
    await Promise.all(tasks);
  }

  private pauseAudios(): void {
    this.previewAudios?.forEach((ref) => {
      const audio = ref.nativeElement;
      if (!audio.paused) audio.pause();
    });
  }

  private pausePreviewMedia(): void {
    const video = this.previewVideo?.nativeElement;
    if (video && !video.paused) video.pause();
    this.pauseAudios();
    this.previewPlaying.set(false);
  }

  private applyTrackVolumes(): void {
    const byId = new Map((this.state()?.tracks || []).map((track) => [track.id, track]));
    this.previewAudios?.forEach((ref) => {
      const audio = ref.nativeElement;
      const track = byId.get(audio.getAttribute('data-track-id') || '');
      if (!track) return;
      audio.volume = Math.max(0, Math.min(1, Number(track.volume || 0)));
      audio.muted = Boolean(track.muted) || audio.volume <= 0.001;
    });
    const video = this.previewVideo?.nativeElement;
    if (video) {
      video.muted = this.videoMuted();
      if (!video.muted) {
        const original = this.state()?.tracks.find((track) => track.track_type === 'original');
        video.volume = Math.max(0, Math.min(1, Number(original?.volume ?? 1)));
      }
    }
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
