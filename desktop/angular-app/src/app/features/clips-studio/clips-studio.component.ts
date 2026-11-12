import { DecimalPipe, NgFor, NgIf } from '@angular/common';
import {
  Component,
  ElementRef,
  OnDestroy,
  OnInit,
  ViewChild,
  inject,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
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
import {
  SubtitleCue,
  clipDurationSeconds,
  cueAtTime,
  cuesFromPlainText,
  cuesFromTranscriptionSegments,
  mergeCues,
  normalizeCue,
  nudgeAllCues,
  nudgeCue,
  sortCues,
  splitCueAt,
} from './subtitle-cues.util';

@Component({
  selector: 'app-clips-studio',
  standalone: true,
  imports: [NgIf, NgFor, FormsModule, DecimalPipe, RouterLink],
  templateUrl: './clips-studio.component.html',
  styleUrl: './clips-studio.component.scss',
})
export class ClipsStudioComponent implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);
  private pollSub: Subscription | null = null;
  private pendingClipId: string | null = null;

  @ViewChild('previewPlayer') private previewPlayer?: ElementRef<HTMLVideoElement>;

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
  readonly playheadSeconds = signal(0);
  readonly activeCueIndex = signal(-1);
  readonly fontChoices = [
    'Montserrat',
    'Inter',
    'Arial',
    'Helvetica',
    'Impact',
    'Georgia',
    'Roboto',
    'Oswald',
    'Poppins',
    'Bebas Neue',
    'Comic Sans MS',
    'DejaVu Sans',
  ];

  selectedVideoId = '';
  selectedIds = new Set<string>();
  tab: 'subtitles' | 'video' | 'reframe' | 'export' | 'profiles' = 'subtitles';
  editStart = 0;
  editEnd = 0;
  dirty = false;
  selectedProfileId = '';
  newProfileName = '';
  readonly manualCropKeys = ['x', 'y', 'width', 'height'] as const;

  ngOnInit(): void {
    this.pendingClipId = this.route.snapshot.queryParamMap.get('clip');
    const videoId = this.route.snapshot.queryParamMap.get('video');
    this.api.listVideos().subscribe({
      next: (videos) => {
        this.videos.set(videos);
        if (videoId) {
          this.selectedVideoId = videoId;
          this.loadClips();
        }
      },
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
        if (!clips.length) return;
        const pending = this.pendingClipId
          ? clips.find((clip) => clip.id === this.pendingClipId)
          : null;
        this.pendingClipId = null;
        this.selectClip(pending || clips[0]);
      },
      error: (err) => this.error.set(err?.error?.detail || err?.message || 'Failed to load clips'),
    });
  }

  selectClip(clip: Clip): void {
    this.activeClip.set(clip);
    this.editStart = clip.start_seconds;
    this.editEnd = clip.end_seconds;
    this.dirty = false;
    this.playheadSeconds.set(0);
    this.activeCueIndex.set(-1);
    this.api.getClipConfiguration(clip.id).subscribe({
      next: (out) => {
        this.configOut.set(out);
        const cfg = structuredClone(out.configuration);
        if (cfg.video.opacity == null || Number.isNaN(Number(cfg.video.opacity))) {
          cfg.video.opacity = 1;
        }
        if (cfg.subtitles.timing_offset_seconds == null) {
          cfg.subtitles.timing_offset_seconds = 0;
        }
        // Keep multi-cue timing from Audio Studio / prior edits — never collapse on load.
        if (cfg.subtitles.segments?.length) {
          cfg.subtitles.segments = sortCues(
            cfg.subtitles.segments.map((seg) =>
              normalizeCue(seg, { duration: this.clipDuration() })
            )
          );
          this.config.set(cfg);
        } else {
          this.config.set(cfg);
          this.seedCuesFromTranscription(clip, cfg);
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

  clipDuration(): number {
    const clip = this.activeClip();
    return clipDurationSeconds(this.editStart, this.editEnd, Number(clip?.duration_seconds) || 1);
  }

  cues(): SubtitleCue[] {
    return this.config()?.subtitles?.segments || [];
  }

  subtitlePreviewText(): string {
    const cfg = this.config();
    const offset = Number(cfg?.subtitles?.timing_offset_seconds || 0);
    const live = cueAtTime(this.cues(), this.playheadSeconds(), offset);
    if (live?.text) return live.text.slice(0, 120);
    const selected = this.cues()[this.activeCueIndex()];
    if (selected?.text) return selected.text.slice(0, 120);
    return this.activeClip()?.hook || 'Subtitle preview';
  }

  onPreviewTimeUpdate(): void {
    const video = this.previewPlayer?.nativeElement;
    const clip = this.activeClip();
    if (!video || !clip) return;
    const relative = this.hasRenderedMedia(clip)
      ? video.currentTime
      : Math.max(0, video.currentTime - Number(clip.start_seconds || 0));
    this.playheadSeconds.set(relative);
  }

  seekToCue(index: number): void {
    const cue = this.cues()[index];
    const video = this.previewPlayer?.nativeElement;
    const clip = this.activeClip();
    if (!cue || !video || !clip) return;
    this.activeCueIndex.set(index);
    const offset = Number(this.config()?.subtitles?.timing_offset_seconds || 0);
    const target = Math.max(0, cue.start + offset);
    if (this.hasRenderedMedia(clip)) {
      video.currentTime = target;
    } else {
      video.currentTime = Number(clip.start_seconds || 0) + target;
    }
    this.playheadSeconds.set(target);
  }

  updateCue(index: number, patch: Partial<SubtitleCue>): void {
    const cfg = this.config();
    if (!cfg?.subtitles.segments) return;
    const duration = this.clipDuration();
    const next = [...cfg.subtitles.segments];
    next[index] = normalizeCue({ ...next[index], ...patch }, { duration });
    cfg.subtitles.segments = sortCues(next);
    this.config.set({ ...cfg });
    this.markDirty();
  }

  nudgeSelected(delta: number): void {
    const index = this.activeCueIndex();
    if (index < 0) {
      this.nudgeAll(delta);
      return;
    }
    const cfg = this.config();
    if (!cfg?.subtitles.segments?.[index]) return;
    const moved = nudgeCue(cfg.subtitles.segments[index], delta, { duration: this.clipDuration() });
    const next = [...cfg.subtitles.segments];
    next[index] = moved;
    cfg.subtitles.segments = sortCues(next);
    this.config.set({ ...cfg });
    this.activeCueIndex.set(
      cfg.subtitles.segments.findIndex((c) => c.start === moved.start && c.end === moved.end && c.text === moved.text)
    );
    this.markDirty();
  }

  nudgeAll(delta: number): void {
    const cfg = this.config();
    if (!cfg?.subtitles.segments?.length) return;
    cfg.subtitles.segments = nudgeAllCues(cfg.subtitles.segments, delta, this.clipDuration());
    this.config.set({ ...cfg });
    this.markDirty();
  }

  nudgeCueRow(index: number, delta: number): void {
    this.activeCueIndex.set(index);
    const cfg = this.config();
    if (!cfg?.subtitles.segments?.[index]) return;
    const moved = nudgeCue(cfg.subtitles.segments[index], delta, { duration: this.clipDuration() });
    const next = [...cfg.subtitles.segments];
    next[index] = moved;
    cfg.subtitles.segments = sortCues(next);
    this.config.set({ ...cfg });
    this.activeCueIndex.set(
      cfg.subtitles.segments.findIndex((c) => c.start === moved.start && c.end === moved.end && c.text === moved.text)
    );
    this.markDirty();
  }

  addCue(): void {
    const cfg = this.config();
    if (!cfg) return;
    const duration = this.clipDuration();
    const last = this.cues()[this.cues().length - 1];
    const start = last ? Math.min(duration - 0.4, last.end) : Math.max(0, this.playheadSeconds());
    const cue = normalizeCue(
      { text: 'New caption', start, end: Math.min(duration, start + 1.2) },
      { duration }
    );
    cfg.subtitles.segments = sortCues([...(cfg.subtitles.segments || []), cue]);
    this.config.set({ ...cfg });
    this.activeCueIndex.set(cfg.subtitles.segments.findIndex((c) => c.start === cue.start && c.text === cue.text));
    this.markDirty();
  }

  deleteCue(index: number): void {
    const cfg = this.config();
    if (!cfg?.subtitles.segments) return;
    cfg.subtitles.segments = cfg.subtitles.segments.filter((_, i) => i !== index);
    if (!cfg.subtitles.segments.length) cfg.subtitles.segments = null;
    this.config.set({ ...cfg });
    this.activeCueIndex.set(-1);
    this.markDirty();
  }

  splitSelectedCue(): void {
    const index = this.activeCueIndex();
    const cfg = this.config();
    if (index < 0 || !cfg?.subtitles.segments?.[index]) return;
    const cue = cfg.subtitles.segments[index];
    const offset = Number(cfg.subtitles.timing_offset_seconds || 0);
    const playhead = this.playheadSeconds() - offset;
    const split = splitCueAt(cue, {
      atSeconds: playhead > cue.start && playhead < cue.end ? playhead : undefined,
    });
    if (!split) {
      this.error.set('Cue is too short to split — place the playhead inside it or lengthen it.');
      return;
    }
    const next = [...cfg.subtitles.segments];
    next.splice(index, 1, ...split);
    cfg.subtitles.segments = sortCues(next);
    this.config.set({ ...cfg });
    this.activeCueIndex.set(index);
    this.markDirty();
  }

  mergeWithNext(index: number): void {
    const cfg = this.config();
    if (!cfg?.subtitles.segments || index < 0 || index >= cfg.subtitles.segments.length - 1) return;
    const merged = mergeCues(cfg.subtitles.segments[index], cfg.subtitles.segments[index + 1]);
    const next = [...cfg.subtitles.segments];
    next.splice(index, 2, merged);
    cfg.subtitles.segments = sortCues(next);
    this.config.set({ ...cfg });
    this.activeCueIndex.set(index);
    this.markDirty();
  }

  clearCues(): void {
    const cfg = this.config();
    if (!cfg) return;
    cfg.subtitles.segments = null;
    this.config.set({ ...cfg });
    this.activeCueIndex.set(-1);
    this.markDirty();
  }

  reseedFromTranscript(): void {
    const clip = this.activeClip();
    const cfg = this.config();
    if (!clip || !cfg) return;
    this.seedCuesFromTranscription(clip, cfg, true);
  }

  autoSplitPlainText(): void {
    const cfg = this.config();
    if (!cfg) return;
    const text =
      this.cues()
        .map((c) => c.text)
        .join(' ')
        .trim() ||
      this.activeClip()?.transcript ||
      '';
    if (!text.trim()) {
      this.error.set('No text available to split into cues');
      return;
    }
    cfg.subtitles.segments = cuesFromPlainText(text, this.clipDuration());
    this.config.set({ ...cfg });
    this.activeCueIndex.set(0);
    this.markDirty();
    this.message.set(`Split into ${cfg.subtitles.segments.length} cues — nudge timing as needed.`);
  }

  cueLaneStyle(cue: SubtitleCue): Record<string, string> {
    const duration = this.clipDuration();
    const left = Math.max(0, (cue.start / duration) * 100);
    const width = Math.max(1.5, ((cue.end - cue.start) / duration) * 100);
    return {
      left: `${left}%`,
      width: `${width}%`,
    };
  }

  playheadLaneStyle(): Record<string, string> {
    const duration = this.clipDuration();
    const left = Math.max(0, Math.min(100, (this.playheadSeconds() / duration) * 100));
    return { left: `${left}%` };
  }

  private seedCuesFromTranscription(
    clip: Clip,
    cfg: ClipConfiguration,
    force = false
  ): void {
    if (!force && cfg.subtitles.segments?.length) return;
    this.api.getVideoTranscription(clip.video_id, true).subscribe({
      next: (transcription) => {
        const duration = this.clipDuration();
        let cues = cuesFromTranscriptionSegments(transcription.segments || [], {
          clipStart: Number(clip.start_seconds || 0),
          clipEnd: Number(clip.end_seconds || clip.start_seconds + duration),
        });
        if (!cues.length) {
          const text = clip.transcript || transcription.full_text || '';
          cues = cuesFromPlainText(text, duration);
        }
        if (!cues.length) return;
        const latest = this.config();
        if (!latest) return;
        if (!force && latest.subtitles.segments?.length) return;
        latest.subtitles.segments = cues;
        this.config.set({ ...latest });
        if (force) this.markDirty();
        this.message.set(
          force
            ? `Reloaded ${cues.length} cues from transcription.`
            : `Loaded ${cues.length} editable cues — adjust timing like CapCut, then Save / Preview.`
        );
      },
      error: () => {
        if (!force) return;
        const text = clip.transcript || '';
        if (!text.trim()) {
          this.error.set('No transcription available to seed cues');
          return;
        }
        const latest = this.config();
        if (!latest) return;
        latest.subtitles.segments = cuesFromPlainText(text, this.clipDuration());
        this.config.set({ ...latest });
        this.markDirty();
      },
    });
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
    if (clip.output_path) return 'Playing exported clip (includes Audio Studio mix)';
    if (clip.preview_path) return 'Playing preview render (includes Audio Studio mix)';
    return 'Playing source video audio — click Preview render to hear replacement/VO mix';
  }

  previewVideoOpacity(clip: Clip): number {
    // Live preview dims the <video> only; subtitle overlay stays opaque.
    // After Preview/Export, opacity is already burned into the file — keep player at 1.
    if (this.hasRenderedMedia(clip)) return 1;
    const value = this.config()?.video?.opacity;
    if (value == null || Number.isNaN(Number(value))) return 1;
    return Math.max(0, Math.min(1, Number(value)));
  }

  setVideoOpacity(raw: number | string): void {
    const cfg = this.config();
    if (!cfg) return;
    const value = Math.max(0, Math.min(1, Number(raw)));
    cfg.video.opacity = Number.isFinite(value) ? value : 1;
    this.config.set({ ...cfg });
    this.markDirty();
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
    cfg.subtitles.style.outline_width = Number(style['outline_width'] ?? cfg.subtitles.style.outline_width);
    cfg.subtitles.style.shadow = Number(style['shadow'] ?? cfg.subtitles.style.shadow);
    cfg.subtitles.style.position = (style['position'] as typeof cfg.subtitles.style.position) || 'bottom';
    cfg.subtitles.style.max_lines = Number(style['max_lines'] || cfg.subtitles.style.max_lines);
    cfg.subtitles.style.alignment =
      (style['alignment'] as typeof cfg.subtitles.style.alignment) || cfg.subtitles.style.alignment;
    cfg.subtitles.style.uppercase = Boolean(style['uppercase']);
    cfg.subtitles.style.italic = Boolean(style['italic']);
    cfg.subtitles.style.font_weight = style['bold'] ? 'bold' : 'normal';
    cfg.subtitles.style.animation = String(style['animation_preset'] || cfg.subtitles.style.animation);
    cfg.subtitles.style.box_enabled = Boolean(style['box_enabled']);
    if (style['box_color']) cfg.subtitles.style.box_color = String(style['box_color']);
    if (style['box_opacity'] != null) cfg.subtitles.style.box_opacity = Number(style['box_opacity']);
    if (style['letter_spacing'] != null) {
      cfg.subtitles.style.letter_spacing = Number(style['letter_spacing']);
    }
    this.config.set({ ...cfg });
    this.markDirty();
  }

  private buildPatch(): Record<string, unknown> {
    const cfg = this.config();
    if (!cfg) return {};
    if (cfg.subtitles.timing_offset_seconds == null || Number.isNaN(Number(cfg.subtitles.timing_offset_seconds))) {
      cfg.subtitles.timing_offset_seconds = 0;
    }
    // Preserve per-cue timing (CapCut-style). Never collapse to a single full-clip segment.
    if (cfg.subtitles.segments?.length) {
      const duration = this.clipDuration();
      cfg.subtitles.segments = sortCues(
        cfg.subtitles.segments.map((seg) => normalizeCue(seg, { duration }))
      );
    } else {
      cfg.subtitles.segments = null;
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
