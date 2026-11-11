import { DecimalPipe, NgFor, NgIf } from '@angular/common';
import { Component, OnDestroy, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { Subscription, switchMap, timer } from 'rxjs';

import {
  Clip,
  GenerationConfiguration,
  ProcessingJob,
  Project,
  Transcription,
  VideoImportResponse,
} from '../../core/models';
import { ApiService } from '../../core/services/api.service';
import { ClipGenerationWizardComponent } from './components/clip-generation-wizard/clip-generation-wizard.component';
import { VideoMetadataPanelComponent } from './components/video-metadata-panel/video-metadata-panel.component';

@Component({
  selector: 'app-video-import',
  standalone: true,
  imports: [
    NgIf,
    NgFor,
    FormsModule,
    DecimalPipe,
    VideoMetadataPanelComponent,
    ClipGenerationWizardComponent,
  ],
  templateUrl: './video-import.component.html',
  styleUrl: './video-import.component.scss',
})
export class VideoImportComponent implements OnDestroy {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);
  private pollSub: Subscription | null = null;

  readonly projects = signal<Project[]>([]);
  readonly result = signal<VideoImportResponse | null>(null);
  readonly busy = signal(false);
  readonly busyMessage = signal('Working…');
  readonly dragging = signal(false);
  readonly error = signal<string | null>(null);
  readonly activeJob = signal<ProcessingJob | null>(null);
  readonly transcription = signal<Transcription | null>(null);
  readonly clips = signal<Clip[]>([]);

  projectName = '';
  selectedProjectId = '';

  constructor() {
    this.api.listProjects().subscribe({
      next: (projects) => this.projects.set(projects),
      error: () => undefined,
    });
  }

  ngOnDestroy(): void {
    this.pollSub?.unsubscribe();
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.dragging.set(true);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragging.set(false);
    const file = event.dataTransfer?.files?.[0];
    if (file) {
      this.importFile(file);
    }
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (file) {
      this.importFile(file);
    }
  }

  importFile(file: File): void {
    this.busy.set(true);
    this.busyMessage.set('Importing and extracting metadata…');
    this.error.set(null);
    this.transcription.set(null);
    this.clips.set([]);
    this.activeJob.set(null);
    this.api
      .importVideo(
        file,
        this.selectedProjectId || undefined,
        this.projectName || file.name.replace(/\.[^.]+$/, '')
      )
      .subscribe({
        next: (response) => {
          this.result.set(response);
          this.busy.set(false);
          this.api.listProjects().subscribe((projects) => this.projects.set(projects));
        },
        error: (err) => {
          this.busy.set(false);
          this.error.set(this.formatDetail(err) || 'Import failed');
        },
      });
  }

  onGenerate(config: GenerationConfiguration): void {
    const imported = this.result();
    if (!imported) {
      return;
    }
    this.busy.set(true);
    this.busyMessage.set('Queueing clip generation…');
    this.error.set(null);
    this.transcription.set(null);
    this.clips.set([]);
    this.api
      .analyzeVideo(imported.video.id, {
        generation_config: config,
        save_configuration: true,
      })
      .subscribe({
        next: (job) => {
          this.activeJob.set(job);
          this.busyMessage.set('Running local transcription + highlight detection…');
          this.startPolling(job.id, imported.video.id);
        },
        error: (err) => {
          this.busy.set(false);
          this.error.set(this.formatDetail(err) || 'Failed to queue generation');
        },
      });
  }

  cancelActive(): void {
    const job = this.activeJob();
    if (!job) {
      return;
    }
    this.api.cancelJob(job.id).subscribe({
      next: () => this.busyMessage.set('Cancellation requested…'),
      error: (err) => this.error.set(this.formatDetail(err) || 'Cancel failed'),
    });
  }

  openClipsStudio(): void {
    void this.router.navigate(['/clips']);
  }

  private startPolling(jobId: string, videoId: string): void {
    this.pollSub?.unsubscribe();
    this.pollSub = timer(0, 1500)
      .pipe(switchMap(() => this.api.getJob(jobId)))
      .subscribe({
        next: (job) => {
          this.activeJob.set(job);
          if (['completed', 'failed', 'cancelled'].includes(job.status)) {
            this.busy.set(false);
            this.pollSub?.unsubscribe();
            this.pollSub = null;
            if (job.status === 'completed') {
              this.api.getVideoTranscription(videoId).subscribe({
                next: (tx) => this.transcription.set(tx),
                error: () => undefined,
              });
              this.api.getVideoClips(videoId).subscribe({
                next: (clips) => this.clips.set(clips),
                error: () => undefined,
              });
            }
            if (job.status === 'failed') {
              this.error.set(job.error || job.message || 'Job failed');
            }
          }
        },
        error: (err) => {
          this.busy.set(false);
          this.error.set(err?.message || 'Failed to poll job');
          this.pollSub?.unsubscribe();
          this.pollSub = null;
        },
      });
  }

  private formatDetail(err: unknown): string | null {
    const detail = (err as { error?: { detail?: unknown }; message?: string })?.error?.detail;
    if (typeof detail === 'string') {
      return detail;
    }
    if (detail && typeof detail === 'object') {
      const validation = (detail as { validation?: { errors?: string[] } }).validation;
      if (validation?.errors?.length) {
        return validation.errors.join('; ');
      }
      try {
        return JSON.stringify(detail);
      } catch {
        return 'Request failed';
      }
    }
    return (err as { message?: string })?.message || null;
  }
}
