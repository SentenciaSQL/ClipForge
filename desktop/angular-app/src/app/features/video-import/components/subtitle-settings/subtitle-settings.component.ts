import { NgFor, NgIf } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ClipConfiguration, SubtitlePreset } from '../../../../core/models';

type SubtitleCfg = ClipConfiguration['subtitles'];

@Component({
  selector: 'app-subtitle-settings',
  standalone: true,
  imports: [FormsModule, NgIf, NgFor],
  templateUrl: './subtitle-settings.component.html',
  styleUrl: './subtitle-settings.component.scss',
})
export class SubtitleSettingsComponent {
  @Input({ required: true }) config!: SubtitleCfg;
  @Input() presets: SubtitlePreset[] = [];
  @Output() configChange = new EventEmitter<SubtitleCfg>();

  readonly fonts = ['Montserrat', 'Inter', 'Poppins', 'Oswald', 'Roboto Condensed', 'Space Grotesk'];
  readonly positions = ['top', 'center', 'bottom', 'custom'];
  readonly animations = ['word', 'karaoke', 'pop', 'fade', 'scale', 'static', 'punch'];

  emit(): void {
    this.configChange.emit({
      ...this.config,
      style: { ...this.config.style },
    });
  }

  setEnabled(value: boolean): void {
    this.config.enabled = value;
    this.emit();
  }

  setPreset(slug: string): void {
    this.config.preset_slug = slug;
    const preset = this.presets.find((p) => p.slug === slug);
    const style = (preset?.config || {}) as Partial<SubtitleCfg['style']>;
    if (style && Object.keys(style).length) {
      this.config.style = { ...this.config.style, ...style };
    }
    this.emit();
  }

  patchStyle(key: keyof SubtitleCfg['style'], value: string | number | boolean): void {
    this.config.style = {
      ...this.config.style,
      [key]: value,
    } as SubtitleCfg['style'];
    this.emit();
  }
}
