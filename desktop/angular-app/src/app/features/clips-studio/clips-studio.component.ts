import { DecimalPipe, NgFor, NgIf } from '@angular/common';
import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subscription, switchMap, timer } from 'rxjs';

import {
  AspectPreset,
  Clip,
  ClipConfiguration,
  ClipConfigurationOut,
  ExportProfile,
  ProcessingJob,
  SourceVideo,
  SubtitlePreset,
} from '../../core/models';
import { ApiService } from '../../core/services/api.service';

@Component({
  selector: 'app-clips-studio',
  standalone: true,
  imports: [NgIf, NgFor, FormsModule, DecimalPipe],
  templateUrl: './clips-studio.component.html',
  styleUrl: './clips-studio.component.scss',
})
export class ClipsStudioComponent implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);
  private pollSub: Subscription | null = null;

  readonly Math = Math;
  readonly videos = signal<SourceVideo[]>([]);
  readonly clips = signal<Clip[]>([]);
  readonly activeClip = signal<Clip | null>(null);
  readonly config = signal<ClipConfiguration | null>(null);
  readonly configOut = signal<ClipConfigurationOut | null>(null);
  readonly subtitlePresets = signal<SubtitlePreset[]>([]);
  readonly profiles = signal<ExportProfile[]>([]);
  readonly aspects = signal<AspectPreset[]>([]);
  readonly job = signal<ProcessingJob | null>(null);
  readonly busy = signal(false);
  readonly error = signal<string | null>(null);
  readonly message = signal<string | null>(null);

  selectedVideoId = '';
  selectedIds = new Set<string>();
  tab: 'subtitles' | 'video' | 'reframe' | 'export' | 'profiles' = 'subtitles';
  editStart = 0;
  editEnd = 0;
  dirty = false;
  subtitleOverrideText = '';
  selectedProfileId = '';
  newProfileName = '';
  readonly manualCropKeys = ['x', 'y', 'width', 'height'] as const;

  ngOnInit(): void {
    this.api.listVideos().subscribe({
      next: (videos) => this.videos.set(videos),
      error: (err) => this.error.set(err?.message || 'Failed to load videos'),
    });
    this.api.listSubtitlePresets().subscribe({
      next: (presets) => this.subtitlePresets.set(presets),
    });
    this.api.listExportProfiles().subscribe({
      next: (profiles) => this.profiles.set(profiles),
    });
    this.api.listAspectPresets().subscribe({
      next: (aspects) => this.aspects.set(aspects),
    });
  }

  ngOnDestroy(): void {
    this.pollSub?.unsubscribe();
  }

  loadClips(): void {
    this.activeClip.set(null);
    this.config.set(null);
    this.selectedIds = new Set();
    if (!this.selectedVideoId) {
      this.clips.set([]);
      return;
    }
    this.api.getVideoClips(this.selectedVideoId).subscribe({
      next: (clips) => {
        this.clips.set(clips);
        if (clips.length) {
          this.selectClip(clips[0]);
        }
      },
      error: (err) => this.error.set(err?.error?.detail || err?.message || 'Failed to load clips'),
    });
  }

  selectClip(clip: Clip): void {
    this.activeClip.set(clip);
    this.editStart = clip.start_seconds;
    this.editEnd = clip.end_seconds;
    this.subtitleOverrideText = clip.transcript || '';
    this.dirty = false;
    this.api.getClipConfiguration(clip.id).subscribe({
      next: (out) => {
        this.configOut.set(out);
        this.config.set(structuredClone(out.configuration));
        if (!this.subtitleOverrideText && out.configuration.subtitles.segments?.length) {
          this.subtitleOverrideText = out.configuration.subtitles.segments.map((s) => s.text).join(' ');
        }
      },
      error: (err) => this.error.set(err?.error?.detail || 'Failed to load clip configuration'),
    });
  }

  markDirty(): void {
    this.dirty = true;
  }

  previewAspect(): string {
    const cfg = this.config();
    if (!cfg) return '9 / 16';
    return `${cfg.video.width} / ${cfg.video.height}`;
  }

  subtitlePreviewText(): string {
    const text = this.subtitleOverrideText.trim() || this.activeClip()?.hook || 'Subtitle preview';
    return text.slice(0, 80);
  }

  hasRenderedMedia(clip: Clip): boolean {
    return Boolean(clip.preview_path || clip.output_path);
  }

  clipPlayerUrl(clip: Clip): string {
    // Bust cache after each render so the <video> reloads the new file.
    const stamp = encodeURIComponent(clip.updated_at || clip.preview_path || clip.output_path || clip.id);
    return `${this.api.clipMediaUrl(clip.id, 'auto')}&t=${stamp}`;
  }

  sourceSegmentUrl(clip: Clip): string {
    const start = Math.max(0, Number(this.editStart || clip.start_seconds || 0));
    const end = Math.max(start + 0.1, Number(this.editEnd || clip.end_seconds || start + 1));
    // Media fragment seeks to the clip window in browsers that support #t=.
    return `${this.api.videoMediaUrl(clip.video_id)}#t=${start.toFixed(2)},${end.toFixed(2)}`;
  }

  activePlayerUrl(clip: Clip): string {
    return this.hasRenderedMedia(clip) ? this.clipPlayerUrl(clip) : this.sourceSegmentUrl(clip);
  }

  playerLabel(clip: Clip): string {
    if (clip.output_path) return 'Playing exported clip';
    if (clip.preview_path) return 'Playing preview render';
    return 'Playing source segment (render a preview for final look)';
  }

  ensureManualCrop(): { x: number; y: number; width: number; height: number } {
    const cfg = this.config();
    if (!cfg) {
      return { x: 0, y: 0, width: 1, height: 1 };
    }
    if (!cfg.reframe.manual_crop) {
      cfg.reframe.manual_crop = { x: 0.1, y: 0.05, width: 0.8, height: 0.9 };
    }
    return cfg.reframe.manual_crop;
  }

  onAspectChange(): void {
    this.markDirty();
    // Backend syncs width/height on save; optimistic local defaults for preview chrome.
    const cfg = this.config();
    const aspects = this.aspects();
    if (!cfg) return;
    const match = aspects.find((a) => a.key === cfg.video.aspect_ratio);
    if (match && cfg.video.resolution_label !== 'custom' && cfg.video.aspect_ratio !== 'custom') {
      const scale =
        cfg.video.resolution_label === '480p'
          ? 480 / 1080
          : cfg.video.resolution_label === '720p'
            ? 720 / 1080
            : cfg.video.resolution_label === '1440p'
              ? 1440 / 1080
              : cfg.video.resolution_label === '2160p'
                ? 2160 / 1080
                : 1;
      cfg.video.width = Math.round(match.default_width * scale);
      cfg.video.height = Math.round(match.default_height * scale);
      this.config.set({ ...cfg });
    }
  }

  applySubtitlePreset(slug: string): void {
    const preset = this.subtitlePresets().find((p) => p.slug === slug);
    const cfg = this.config();
    if (!preset || !cfg) return;
    const style = (preset.config || {}) as Record<string, unknown>;
    cfg.subtitles.preset_slug = slug;
    cfg.subtitles.style.font_family = String(style['font_family'] || cfg.subtitles.style.font_family);
    cfg.subtitles.style.font_size = Number(style['font_size'] || cfg.subtitles.style.font_size);
    cfg.subtitles.style.text_color = String(style['primary_color'] || cfg.subtitles.style.text_color);
    cfg.subtitles.style.highlight_color = String(
      style['highlight_color'] || cfg.subtitles.style.highlight_color
    );
    cfg.subtitles.style.outline_color = String(style['outline_color'] || cfg.subtitles.style.outline_color);
    cfg.subtitles.style.outline_width = Number(style['outline_width'] || cfg.subtitles.style.outline_width);
    cfg.subtitles.style.shadow = Number(style['shadow'] || cfg.subtitles.style.shadow);
    cfg.subtitles.style.position = (style['position'] as typeof cfg.subtitles.style.position) || 'bottom';
    cfg.subtitles.style.max_lines = Number(style['max_lines'] || cfg.subtitles.style.max_lines);
    cfg.subtitles.style.alignment =
      (style['alignment'] as typeof cfg.subtitles.style.alignment) || cfg.subtitles.style.alignment;
    cfg.subtitles.style.uppercase = Boolean(style['uppercase']);
    cfg.subtitles.style.font_weight = style['bold'] ? 'bold' : 'normal';
    cfg.subtitles.style.animation = String(style['animation_preset'] || cfg.subtitles.style.animation);
    this.config.set({ ...cfg });
    this.markDirty();
  }

  private buildPatch(): Record<string, unknown> {
    const cfg = this.config();
    if (!cfg) return {};
    if (this.subtitleOverrideText.trim()) {
      const duration = Math.max(0.5, this.editEnd - this.editStart);
      cfg.subtitles.segments = [
        {
          text: this.subtitleOverrideText.trim(),
          start: 0,
          end: duration,
        },
      ];
    }
    return {
      subtitles: cfg.subtitles,
      video: cfg.video,
      reframe: cfg.reframe,
      audio: cfg.audio,
      export: cfg.export,
      profile_id: cfg.profile_id ?? null,
    };
  }

  saveConfig(): void {
    const clip = this.activeClip();
    if (!clip) return;
    this.busy.set(true);
    this.error.set(null);
    this.api.patchClipConfiguration(clip.id, this.buildPatch()).subscribe({
      next: (out) => {
        this.configOut.set(out);
        this.config.set(structuredClone(out.configuration));
        this.dirty = false;
        this.message.set('Clip configuration saved (no re-transcription).');
        this.busy.set(false);
        this.refreshClip(clip.id);
      },
      error: (err) => {
        this.busy.set(false);
        this.error.set(err?.error?.detail || 'Failed to save configuration');
      },
    });
  }

  saveTiming(): void {
    const clip = this.activeClip();
    if (!clip) return;
    if (this.editEnd <= this.editStart) {
      this.error.set('End must be greater than start');
      return;
    }
    this.api
      .patchClip(clip.id, {
        start_seconds: this.editStart,
        end_seconds: this.editEnd,
      })
      .subscribe({
        next: (updated) => {
          this.activeClip.set(updated);
          this.clips.update((list) => list.map((c) => (c.id === updated.id ? updated : c)));
          this.message.set('Clip timing updated.');
        },
        error: (err) => this.error.set(err?.error?.detail || 'Failed to update timing'),
      });
  }

  runPreview(): void {
    const clip = this.activeClip();
    if (!clip) return;
    this.queueJob(() =>
      this.api.previewClip(clip.id, {
        configuration: this.buildPatch(),
        save_configuration: true,
      })
    );
  }

  runRender(): void {
    const clip = this.activeClip();
    if (!clip) return;
    this.queueJob(() =>
      this.api.renderClip(clip.id, {
        configuration: this.buildPatch(),
        burn_subtitles: this.config()?.subtitles.enabled ?? true,
      })
    );
  }

  applyToSelected(): void {
    if (!this.selectedIds.size) return;
    const confirmed = window.confirm(
      `Apply this clip's configuration to ${this.selectedIds.size} selected clips? Individual settings will be overwritten.`
    );
    if (!confirmed) return;
    this.busy.set(true);
    this.api
      .applyConfigurationToClips([...this.selectedIds], this.buildPatch(), true)
      .subscribe({
        next: (res) => {
          this.message.set(res.message);
          this.busy.set(false);
        },
        error: (err) => {
          this.busy.set(false);
          this.error.set(err?.error?.detail || 'Failed to apply configuration');
        },
      });
  }

  batchRender(): void {
    if (!this.selectedIds.size) return;
    this.queueJob(() =>
      this.api.batchRenderClips({
        clip_ids: [...this.selectedIds],
        configuration: this.buildPatch(),
        apply_to_all: true,
        confirm_overwrite: true,
      })
    );
  }

  applyProfile(profileId: string): void {
    const clip = this.activeClip();
    if (!clip || !profileId) return;
    this.busy.set(true);
    this.api
      .patchClipConfiguration(clip.id, {
        profile_id: profileId,
        apply_profile: true,
      })
      .subscribe({
        next: (out) => {
          this.configOut.set(out);
          this.config.set(structuredClone(out.configuration));
          this.message.set('Profile applied to this clip only.');
          this.busy.set(false);
        },
        error: (err) => {
          this.busy.set(false);
          this.error.set(err?.error?.detail || 'Failed to apply profile');
        },
      });
  }

  saveAsProfile(): void {
    const cfg = this.config();
    if (!cfg || !this.newProfileName.trim()) return;
    this.api
      .createExportProfile({
        name: this.newProfileName.trim(),
        config_json: cfg,
        description: 'Custom profile from Clips Studio',
      })
      .subscribe({
        next: (profile) => {
          this.profiles.update((list) => [...list, profile]);
          this.newProfileName = '';
          this.message.set(`Saved profile “${profile.name}”.`);
        },
        error: (err) => this.error.set(err?.error?.detail || 'Failed to save profile'),
      });
  }

  toggleSelected(id: string, event: Event): void {
    const checked = (event.target as HTMLInputElement).checked;
    const next = new Set(this.selectedIds);
    if (checked) next.add(id);
    else next.delete(id);
    this.selectedIds = next;
  }

  allSelected(): boolean {
    const clips = this.clips();
    return clips.length > 0 && clips.every((c) => this.selectedIds.has(c.id));
  }

  toggleSelectAll(event: Event): void {
    const checked = (event.target as HTMLInputElement).checked;
    this.selectedIds = checked ? new Set(this.clips().map((c) => c.id)) : new Set();
  }

  private refreshClip(id: string): void {
    this.api.getVideoClips(this.selectedVideoId).subscribe({
      next: (clips) => {
        this.clips.set(clips);
        const found = clips.find((c) => c.id === id) || null;
        if (found) this.activeClip.set(found);
      },
    });
  }

  private queueJob(factory: () => import('rxjs').Observable<ProcessingJob>): void {
    this.busy.set(true);
    this.error.set(null);
    factory().subscribe({
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
                const clip = this.activeClip();
                if (clip) this.refreshClip(clip.id);
                if (updated.status === 'failed') {
                  this.error.set(updated.error || 'Job failed');
                } else if (updated.status === 'completed') {
                  this.message.set(updated.message || 'Done');
                }
              }
            },
          });
      },
      error: (err) => {
        this.busy.set(false);
        this.error.set(err?.error?.detail || err?.message || 'Failed to queue job');
      },
    });
  }
}
