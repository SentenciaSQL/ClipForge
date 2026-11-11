import { NgFor, NgIf, NgStyle } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ClipConfiguration } from '../../../../core/models';

type VideoCfg = ClipConfiguration['video'];

@Component({
  selector: 'app-video-format-settings',
  standalone: true,
  imports: [FormsModule, NgFor, NgIf, NgStyle],
  templateUrl: './video-format-settings.component.html',
  styleUrl: './video-format-settings.component.scss',
})
export class VideoFormatSettingsComponent {
  @Input({ required: true }) config!: VideoCfg;
  @Input() sourceWidth: number | null = null;
  @Input() sourceHeight: number | null = null;
  @Output() configChange = new EventEmitter<VideoCfg>();

  readonly aspects = [
    { key: '9:16', label: '9:16 – Vertical (TikTok, Reels, Shorts)' },
    { key: '16:9', label: '16:9 – Landscape (YouTube)' },
    { key: '1:1', label: '1:1 – Square' },
    { key: '4:5', label: '4:5 – Portrait' },
    { key: '4:3', label: '4:3 – Classic' },
    { key: '21:9', label: '21:9 – Cinematic' },
    { key: 'custom', label: 'Custom aspect ratio' },
  ];

  readonly resolutions = [
    { key: '480p', label: '480p' },
    { key: '720p', label: '720p' },
    { key: '1080p', label: '1080p' },
    { key: '1440p', label: '1440p' },
    { key: '2160p', label: '4K' },
  ];

  readonly fpsOptions = [
    { key: 'source', label: 'Preserve source FPS' },
    { key: '24', label: '24 FPS' },
    { key: '25', label: '25 FPS' },
    { key: '30', label: '30 FPS' },
    { key: '50', label: '50 FPS' },
    { key: '60', label: '60 FPS' },
  ];

  private readonly shortSide: Record<string, number> = {
    '480p': 480,
    '720p': 720,
    '1080p': 1080,
    '1440p': 1440,
    '2160p': 2160,
  };

  emit(): void {
    this.syncDimensions();
    this.configChange.emit({ ...this.config });
  }

  setAspect(key: string): void {
    this.config.aspect_ratio = key;
    this.emit();
  }

  setResolution(key: string): void {
    this.config.resolution_label = key;
    this.emit();
  }

  setFps(key: string): void {
    if (key === 'source') {
      this.config.preserve_source_fps = true;
      this.config.fps = null;
    } else {
      this.config.preserve_source_fps = false;
      this.config.fps = Number(key);
    }
    this.emit();
  }

  fpsKey(): string {
    return this.config.preserve_source_fps ? 'source' : String(this.config.fps || 30);
  }

  previewStyle(): Record<string, string> {
    const [w, h] = this.config.aspect_ratio.split(':').map(Number);
    if (!w || !h || this.config.aspect_ratio === 'custom') {
      return { aspectRatio: `${this.config.width} / ${this.config.height}` };
    }
    return { aspectRatio: `${w} / ${h}` };
  }

  upscaleWarning(): string | null {
    if (!this.sourceWidth || !this.sourceHeight) {
      return null;
    }
    const sourceShort = Math.min(this.sourceWidth, this.sourceHeight);
    const targetShort = this.shortSide[this.config.resolution_label] || 0;
    if (targetShort > sourceShort) {
      return `Selected resolution (${this.config.resolution_label}) is higher than the source short side (${sourceShort}px). Upscaling may reduce sharpness.`;
    }
    return null;
  }

  private syncDimensions(): void {
    if (this.config.aspect_ratio === 'custom' || this.config.resolution_label === 'custom') {
      return;
    }
    const parts = this.config.aspect_ratio.split(':').map(Number);
    const short = this.shortSide[this.config.resolution_label] || 1080;
    if (parts.length !== 2 || !parts[0] || !parts[1]) {
      return;
    }
    const [aw, ah] = parts;
    if (aw <= ah) {
      this.config.width = short;
      this.config.height = Math.round((short * ah) / aw);
    } else {
      this.config.height = short;
      this.config.width = Math.round((short * aw) / ah);
    }
  }
}
