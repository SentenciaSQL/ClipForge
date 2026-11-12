import { NgFor, NgIf } from '@angular/common';
import { Component, EventEmitter, Input, OnChanges, Output, SimpleChanges, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import {
  GenerationConfiguration,
  GenerationProfile,
  SourceQualityAssessment,
  SourceVideo,
  SubtitlePreset,
  defaultGenerationConfiguration,
} from '../../../../core/models';
import { ApiService } from '../../../../core/services/api.service';
import { AiAnalysisSettingsComponent } from '../ai-analysis-settings/ai-analysis-settings.component';
import { AudioGenerationSettingsComponent } from '../audio-generation-settings/audio-generation-settings.component';
import { ClipDurationSettingsComponent } from '../clip-duration-settings/clip-duration-settings.component';
import { GenerationConfigurationSummaryComponent } from '../generation-configuration-summary/generation-configuration-summary.component';
import { QualitySettingsComponent } from '../quality-settings/quality-settings.component';
import { ReframingSettingsComponent } from '../reframing-settings/reframing-settings.component';
import { SubtitleSettingsComponent } from '../subtitle-settings/subtitle-settings.component';
import { VideoFormatSettingsComponent } from '../video-format-settings/video-format-settings.component';

type WizardStep = 'configure' | 'summary';
type SectionKey =
  | 'duration'
  | 'subtitles'
  | 'format'
  | 'quality'
  | 'reframe'
  | 'ai'
  | 'audio'
  | 'profiles';

@Component({
  selector: 'app-clip-generation-wizard',
  standalone: true,
  imports: [
    NgIf,
    NgFor,
    FormsModule,
    ClipDurationSettingsComponent,
    SubtitleSettingsComponent,
    VideoFormatSettingsComponent,
    QualitySettingsComponent,
    ReframingSettingsComponent,
    AiAnalysisSettingsComponent,
    AudioGenerationSettingsComponent,
    GenerationConfigurationSummaryComponent,
  ],
  templateUrl: './clip-generation-wizard.component.html',
  styleUrl: './clip-generation-wizard.component.scss',
})
export class ClipGenerationWizardComponent implements OnChanges {
  private readonly api = inject(ApiService);

  @Input({ required: true }) video!: SourceVideo;
  @Input() busy = false;
  @Output() generate = new EventEmitter<GenerationConfiguration>();
  @Output() saved = new EventEmitter<GenerationConfiguration>();

  readonly config = signal<GenerationConfiguration>(defaultGenerationConfiguration());
  readonly profiles = signal<GenerationProfile[]>([]);
  readonly subtitlePresets = signal<SubtitlePreset[]>([]);
  readonly summary = signal<string[]>([]);
  readonly errors = signal<string[]>([]);
  readonly warnings = signal<string[]>([]);
  readonly sourceQuality = signal<SourceQualityAssessment | null>(null);
  readonly message = signal<string | null>(null);
  readonly error = signal<string | null>(null);

  step: WizardStep = 'configure';
  /** Multiple sections can stay open; avoids flaky native <details> + [open] binding. */
  openSections = new Set<SectionKey>(['quality', 'duration']);
  selectedProfileId = '';
  newProfileName = '';
  dirty = false;

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['video'] && this.video) {
      this.load();
    }
  }

  load(): void {
    this.step = 'configure';
    this.error.set(null);
    this.message.set(null);
    this.api.getGenerationConfiguration(this.video.id).subscribe({
      next: (out) => {
        this.config.set(structuredClone(out.configuration));
        this.summary.set(out.summary || []);
        this.errors.set((out.validation?.errors as string[]) || []);
        this.warnings.set((out.validation?.warnings as string[]) || []);
        this.sourceQuality.set(out.source_quality || null);
        this.selectedProfileId = out.configuration.profile_id || '';
        this.dirty = false;
        if (!out.source_quality) {
          this.refreshSourceQuality();
        }
      },
      error: () => {
        this.config.set(defaultGenerationConfiguration());
        this.refreshSourceQuality();
      },
    });
    this.api.listGenerationProfiles().subscribe({
      next: (profiles) => this.profiles.set(profiles),
      error: () => undefined,
    });
    this.api.listSubtitlePresets().subscribe({
      next: (presets) => this.subtitlePresets.set(presets),
      error: () => undefined,
    });
  }

  refreshSourceQuality(): void {
    const cfg = this.config();
    this.api
      .getSourceQuality(this.video.id, {
        aspect_ratio: cfg.video.aspect_ratio,
        allow_upscale: Boolean(cfg.video.allow_upscale),
        content_hint: cfg.analysis.content_category,
        requested_width: cfg.video.width,
        requested_height: cfg.video.height,
      })
      .subscribe({
        next: (quality) => {
          this.sourceQuality.set(quality);
          // If auto quality is on and canvas is still oversized, apply recommendation.
          const rec = quality.recommendations || {};
          const recW = Number(rec['width'] || 0);
          const recH = Number(rec['height'] || 0);
          if (
            cfg.video.auto_quality &&
            !cfg.video.allow_upscale &&
            recW > 0 &&
            recH > 0 &&
            (cfg.video.width > recW + 2 || cfg.video.height > recH + 2)
          ) {
            this.applyAdaptiveRecommendation();
          }
        },
        error: () => undefined,
      });
  }

  applyAdaptiveRecommendation(): void {
    this.error.set(null);
    this.api.applyAdaptiveGenerationConfiguration(this.video.id).subscribe({
      next: (out) => {
        this.config.set(structuredClone(out.configuration));
        this.summary.set(out.summary || []);
        this.warnings.set((out.validation?.warnings as string[]) || []);
        this.sourceQuality.set(out.source_quality || null);
        this.message.set('Applied adaptive quality recommendation');
        this.dirty = false;
        this.saved.emit(out.configuration);
      },
      error: (err) => this.error.set(this.formatError(err) || 'Adaptive quality failed'),
    });
  }

  toggle(section: SectionKey, event?: Event): void {
    event?.preventDefault();
    event?.stopPropagation();
    if (this.openSections.has(section)) {
      this.openSections.delete(section);
    } else {
      this.openSections.add(section);
    }
    // New Set reference so Angular re-checks isOpen() after the click.
    this.openSections = new Set(this.openSections);
  }

  isOpen(section: SectionKey): boolean {
    return this.openSections.has(section);
  }

  patchConfig(partial: Partial<GenerationConfiguration>): void {
    this.config.set({ ...this.config(), ...partial });
    this.dirty = true;
  }

  saveConfiguration(confirmOverwrite = false): void {
    this.error.set(null);
    this.api
      .saveGenerationConfiguration(this.video.id, {
        configuration: this.config(),
        apply_profile: Boolean(this.selectedProfileId && confirmOverwrite),
        profile_id: this.selectedProfileId || null,
        confirm_overwrite: confirmOverwrite,
      })
      .subscribe({
        next: (out) => {
          this.config.set(structuredClone(out.configuration));
          this.summary.set(out.summary || []);
          this.errors.set((out.validation?.errors as string[]) || []);
          this.warnings.set((out.validation?.warnings as string[]) || []);
          this.message.set('Configuration saved');
          this.dirty = false;
          this.saved.emit(out.configuration);
        },
        error: (err) => {
          const detail = err?.error?.detail;
          if (typeof detail === 'string' && detail.includes('confirm_overwrite')) {
            if (window.confirm('Replace your current settings with the selected profile?')) {
              this.saveConfiguration(true);
              return;
            }
          }
          this.error.set(this.formatError(err) || 'Failed to save configuration');
        },
      });
  }

  applyProfile(profileId: string): void {
    this.selectedProfileId = profileId;
    if (!profileId) {
      return;
    }
    const profile = this.profiles().find((p) => p.id === profileId);
    if (!profile) {
      return;
    }
    if (this.dirty) {
      const ok = window.confirm(
        'Applying a profile will overwrite your current editable settings. Continue?'
      );
      if (!ok) {
        return;
      }
    }
    const next = structuredClone(profile.config_json) as GenerationConfiguration;
    next.profile_id = profile.id;
    next.profile_slug = profile.slug;
    this.config.set(next);
    this.dirty = true;
    this.message.set(`Loaded profile: ${profile.name}`);
  }

  saveAsProfile(): void {
    const name = this.newProfileName.trim();
    if (!name) {
      this.error.set('Enter a name for the custom profile');
      return;
    }
    this.api
      .createGenerationProfile({
        name,
        description: 'Custom generation profile',
        config_json: this.config(),
      })
      .subscribe({
        next: (profile) => {
          this.profiles.set([...this.profiles(), profile]);
          this.selectedProfileId = profile.id;
          this.newProfileName = '';
          this.message.set(`Saved profile “${profile.name}”`);
        },
        error: (err) => this.error.set(this.formatError(err) || 'Failed to save profile'),
      });
  }

  duplicateProfile(profile: GenerationProfile): void {
    this.api.duplicateGenerationProfile(profile.id).subscribe({
      next: (copy) => {
        this.profiles.set([...this.profiles(), copy]);
        this.message.set(`Duplicated as “${copy.name}”`);
      },
      error: (err) => this.error.set(this.formatError(err) || 'Duplicate failed'),
    });
  }

  deleteProfile(profile: GenerationProfile): void {
    if (profile.is_builtin) {
      return;
    }
    if (!window.confirm(`Delete custom profile “${profile.name}”?`)) {
      return;
    }
    this.api.deleteGenerationProfile(profile.id).subscribe({
      next: () => {
        this.profiles.set(this.profiles().filter((p) => p.id !== profile.id));
        if (this.selectedProfileId === profile.id) {
          this.selectedProfileId = '';
        }
        this.message.set('Profile deleted');
      },
      error: (err) => this.error.set(this.formatError(err) || 'Delete failed'),
    });
  }

  goToSummary(): void {
    this.error.set(null);
    this.api.validateGenerationConfiguration(this.video.id, this.config()).subscribe({
      next: (out) => {
        this.summary.set(out.summary || []);
        this.errors.set((out.validation?.errors as string[]) || []);
        this.warnings.set((out.validation?.warnings as string[]) || []);
        if (out.validation?.ok === false) {
          this.error.set('Fix validation errors before generating clips');
          return;
        }
        this.api
          .saveGenerationConfiguration(this.video.id, {
            configuration: this.config(),
            confirm_overwrite: true,
          })
          .subscribe({
            next: (saved) => {
              this.config.set(structuredClone(saved.configuration));
              this.summary.set(saved.summary || this.summary());
              this.dirty = false;
              this.saved.emit(saved.configuration);
              this.step = 'summary';
            },
            error: (err) => this.error.set(this.formatError(err) || 'Failed to save configuration'),
          });
      },
      error: (err) => this.error.set(this.formatError(err) || 'Validation failed'),
    });
  }

  backToConfigure(): void {
    this.step = 'configure';
  }

  confirmGenerate(): void {
    if (this.errors().length) {
      return;
    }
    this.generate.emit(this.config());
  }

  private formatError(err: unknown): string | null {
    const detail = (err as { error?: { detail?: unknown }; message?: string })?.error?.detail;
    if (typeof detail === 'string') {
      return detail;
    }
    if (detail && typeof detail === 'object') {
      const validation = (detail as { validation?: { errors?: string[] } }).validation;
      if (validation?.errors?.length) {
        return validation.errors.join('; ');
      }
      return JSON.stringify(detail);
    }
    return (err as { message?: string })?.message || null;
  }
}
