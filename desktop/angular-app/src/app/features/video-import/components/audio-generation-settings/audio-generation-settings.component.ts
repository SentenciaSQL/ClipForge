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
      help: 'Mute original. In Audio Studio upload your audio, then “Use for subtitles” so captions match.',
    },
    {
      key: 'music',
      label: 'Add background music',
      help: 'Duck original audio; add music beds in Audio Studio after generation.',
    },
    {
      key: 'voiceover',
      label: 'Add voice-over',
      help: 'Prepare for VO in Audio Studio. Upload VO and use “Use for subtitles” to realign captions.',
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
