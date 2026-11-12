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
      key: 'auto',
      label: 'Auto (quality-aware)',
      help: 'Chooses smart crop or blurred background based on source resolution and aspect — avoids destructive vertical crops on low-res landscape footage.',
    },
    {
      key: 'smart_crop',
      label: 'Smart Crop',
      help: 'Detects faces/people when relevant and keeps the subject in frame with smoothed focal tracking. Does not assume every video has a speaker.',
    },
    {
      key: 'center_crop',
      label: 'Center Crop',
      help: 'Crops around the center. Warns when the crop throws away most of a landscape frame.',
    },
    {
      key: 'blurred_bg',
      label: 'Blurred Background',
      help: 'Preserves the full original frame as foreground, fills the canvas with a blurred/darkened cover — no stretch.',
    },
    {
      key: 'fit_original',
      label: 'Fit Original',
      help: 'Keeps the entire source frame, maintains aspect ratio, pads with a configurable background.',
    },
    {
      key: 'solid_bg',
      label: 'Solid Background',
      help: 'Fits the full frame onto a solid color background without cropping.',
    },
    {
      key: 'original',
      label: 'Original Frame',
      help: 'Same as Fit Original — pad into the target canvas without cropping.',
    },
    {
      key: 'manual',
      label: 'Manual Crop',
      help: 'Select and reposition the visible region (normalized crop rectangle).',
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
