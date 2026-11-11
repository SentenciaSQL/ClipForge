import { DecimalPipe, NgIf } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { GenerationDurationConfig } from '../../../../core/models';

@Component({
  selector: 'app-clip-duration-settings',
  standalone: true,
  imports: [FormsModule, NgIf, DecimalPipe],
  templateUrl: './clip-duration-settings.component.html',
  styleUrl: './clip-duration-settings.component.scss',
})
export class ClipDurationSettingsComponent {
  @Input({ required: true }) config!: GenerationDurationConfig;
  @Input() videoDuration: number | null = null;
  @Output() configChange = new EventEmitter<GenerationDurationConfig>();

  emit(): void {
    this.configChange.emit({ ...this.config });
  }

  setMin(value: number): void {
    this.config.min_duration = Number(value) || 1;
    this.emit();
  }

  setMax(value: number): void {
    this.config.max_duration = Number(value) || 1;
    this.emit();
  }

  setCount(value: number): void {
    this.config.clip_count = Math.max(1, Math.min(50, Number(value) || 1));
    this.emit();
  }

  setAuto(value: boolean): void {
    this.config.auto_clip_count = value;
    this.emit();
  }
}
