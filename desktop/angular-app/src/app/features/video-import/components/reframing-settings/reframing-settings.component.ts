import { NgFor, NgIf } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ClipConfiguration } from '../../../../core/models';

type ReframeCfg = ClipConfiguration['reframe'];

@Component({
  selector: 'app-reframing-settings',
  standalone: true,
  imports: [FormsModule, NgFor, NgIf],
  templateUrl: './reframing-settings.component.html',
  styleUrl: './reframing-settings.component.scss',
})
export class ReframingSettingsComponent {
  @Input({ required: true }) config!: ReframeCfg;
  @Output() configChange = new EventEmitter<ReframeCfg>();

  readonly modes = [
    {
      key: 'smart_crop',
      label: 'Smart Crop',
      help: 'Adapts to content type. Tracks faces when present; otherwise keeps the strongest visual region without assuming a speaker.',
    },
    {
      key: 'center_crop',
      label: 'Center Crop',
      help: 'Crops from the center of the frame to the target aspect ratio.',
    },
    {
      key: 'blurred_bg',
      label: 'Blurred Background',
      help: 'Fits the full frame and fills letterboxing with a blurred copy of the video.',
    },
    {
      key: 'solid_bg',
      label: 'Solid Background',
      help: 'Fits the full frame onto a solid color background.',
    },
    {
      key: 'original',
      label: 'Original Frame',
      help: 'Keeps the original framing as closely as possible for the selected aspect.',
    },
    {
      key: 'manual',
      label: 'Manual Crop',
      help: 'Uses a normalized crop rectangle you define (editable later per clip).',
    },
  ];

  emit(): void {
    this.configChange.emit({ ...this.config });
  }

  select(mode: string): void {
    this.config.mode = mode;
    this.config.enable_face_detection = mode === 'smart_crop' || mode === 'podcast';
    if (mode === 'manual' && !this.config.manual_crop) {
      this.config.manual_crop = { x: 0.15, y: 0.1, width: 0.7, height: 0.8 };
    }
    this.emit();
  }
}
