import { NgFor } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { GenerationAudioConfig } from '../../../../core/models';

@Component({
  selector: 'app-audio-generation-settings',
  standalone: true,
  imports: [FormsModule, NgFor],
  templateUrl: './audio-generation-settings.component.html',
  styleUrl: './audio-generation-settings.component.scss',
})
export class AudioGenerationSettingsComponent {
  @Input({ required: true }) config!: GenerationAudioConfig;
  @Output() configChange = new EventEmitter<GenerationAudioConfig>();

  readonly modes = [
    {
      key: 'preserve',
      label: 'Preserve original audio',
      help: 'Keep the source soundtrack on every clip.',
    },
    {
      key: 'remove',
      label: 'Remove original audio',
      help: 'Mute the original track (editable later in Audio Studio).',
    },
    {
      key: 'replace',
      label: 'Replace original audio',
      help: 'Mute original so you can replace it in Audio Studio.',
    },
    {
      key: 'music',
      label: 'Add background music',
      help: 'Duck original audio; add music beds in Audio Studio after generation.',
    },
    {
      key: 'voiceover',
      label: 'Add voice-over',
      help: 'Prepare for a voice-over track in Audio Studio after clips are created.',
    },
  ];

  emit(): void {
    this.configChange.emit({ ...this.config });
  }

  select(mode: GenerationAudioConfig['mode']): void {
    this.config.mode = mode;
    this.emit();
  }
}
