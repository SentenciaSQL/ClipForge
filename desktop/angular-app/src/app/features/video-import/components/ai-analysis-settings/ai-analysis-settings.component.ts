import { NgFor } from '@angular/common';
import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { GenerationAnalysisConfig } from '../../../../core/models';

@Component({
  selector: 'app-ai-analysis-settings',
  standalone: true,
  imports: [FormsModule, NgFor],
  templateUrl: './ai-analysis-settings.component.html',
  styleUrl: './ai-analysis-settings.component.scss',
})
export class AiAnalysisSettingsComponent {
  @Input({ required: true }) config!: GenerationAnalysisConfig;
  @Output() configChange = new EventEmitter<GenerationAnalysisConfig>();

  readonly languages = [
    { value: 'auto', label: 'Automatic language detection' },
    { value: 'en', label: 'English' },
    { value: 'es', label: 'Spanish' },
    { value: 'fr', label: 'French' },
    { value: 'de', label: 'German' },
    { value: 'pt', label: 'Portuguese' },
    { value: 'it', label: 'Italian' },
    { value: 'ja', label: 'Japanese' },
    { value: 'ko', label: 'Korean' },
    { value: 'zh', label: 'Chinese' },
  ];

  readonly whisperModels = ['large-v3', 'distil-large-v3', 'medium', 'small', 'base', 'tiny'];
  readonly sensitivities = [
    { value: 'low', label: 'Low — fewer, stronger clips' },
    { value: 'medium', label: 'Medium — balanced' },
    { value: 'high', label: 'High — more candidates' },
  ];
  readonly categories = [
    'auto',
    'educational',
    'storytelling',
    'podcast',
    'interview',
    'gaming',
    'tutorial',
    'humor',
    'opinions',
    'general',
  ];

  emit(): void {
    this.configChange.emit({ ...this.config });
  }

  languageValue(): string {
    return this.config.language || 'auto';
  }

  setLanguage(value: string): void {
    this.config.language = value === 'auto' ? null : value;
    this.emit();
  }

  setCategory(value: string): void {
    this.config.content_category = value;
    this.config.auto_detect_content_type = value === 'auto';
    this.emit();
  }

  setAutoDetect(value: boolean): void {
    this.config.auto_detect_content_type = value;
    if (value) {
      this.config.content_category = 'auto';
    }
    this.emit();
  }
}
