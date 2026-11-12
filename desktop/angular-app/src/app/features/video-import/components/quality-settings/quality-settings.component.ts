import { NgFor, NgIf } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ClipConfiguration, SourceQualityAssessment } from '../../../../core/models';

type VideoCfg = ClipConfiguration['video'];

@Component({
  selector: 'app-quality-settings',
  standalone: true,
  imports: [FormsModule, NgIf, NgFor],
  templateUrl: './quality-settings.component.html',
  styleUrl: './quality-settings.component.scss',
})
export class QualitySettingsComponent {
  @Input({ required: true }) config!: VideoCfg;
  @Input() sourceQuality: SourceQualityAssessment | null = null;
  @Input() warnings: string[] = [];
  @Output() configChange = new EventEmitter<VideoCfg>();
  @Output() applyAdaptive = new EventEmitter<void>();

  readonly qualityPresets = [
    { key: 'draft', label: 'Draft — fast previews' },
    { key: 'fast', label: 'Fast' },
    { key: 'balanced', label: 'Balanced' },
    { key: 'high', label: 'High quality' },
    { key: 'maximum', label: 'Maximum quality (slower)' },
  ];

  readonly encoders = [
    { key: 'auto', label: 'Auto (NVENC if available, else CPU)' },
    { key: 'cpu', label: 'CPU (libx264 / libx265)' },
    { key: 'nvenc', label: 'NVIDIA NVENC' },
  ];

  readonly codecs = [
    { key: 'h264', label: 'H.264' },
    { key: 'h265', label: 'H.265 / HEVC' },
  ];

  emit(): void {
    this.configChange.emit({ ...this.config });
  }

  setAuto(value: boolean): void {
    this.config.auto_quality = value;
    this.emit();
    if (value) {
      this.applyAdaptive.emit();
    }
  }

  setAllowUpscale(value: boolean): void {
    this.config.allow_upscale = value;
    this.emit();
  }

  setAiUpscale(value: boolean): void {
    this.config.ai_upscale = value;
    this.emit();
  }

  recommendationNotes(): string[] {
    const notes = this.sourceQuality?.recommendations?.['notes'];
    return Array.isArray(notes) ? (notes as string[]) : [];
  }

  uniqueWarnings(): string[] {
    const merged = [...(this.warnings || []), ...(this.sourceQuality?.warnings || [])];
    return [...new Set(merged.map((item) => String(item || '').trim()).filter(Boolean))];
  }
}
