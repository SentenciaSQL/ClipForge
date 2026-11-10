import { DecimalPipe, NgFor, NgIf } from '@angular/common';
import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subscription, switchMap, timer } from 'rxjs';

import { Clip, ProcessingJob, Project } from '../../core/models';
import { ApiService } from '../../core/services/api.service';

@Component({
  selector: 'app-export-library',
  standalone: true,
  imports: [NgIf, NgFor, FormsModule, DecimalPipe],
  template: `
    <div class="space-y-6">
      <header class="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div class="avc-label">Deliverables</div>
          <h1 class="avc-title mt-1">Export Library</h1>
          <p class="mt-2 max-w-2xl text-sm text-muted">
            Preview rendered shorts, batch-export, and manage local output files under workspace/exports.
          </p>
        </div>
        <button class="avc-btn-primary" type="button" (click)="batchExport()" [disabled]="!selectedIds().length || busy()">
          Export selected ({{ selectedIds().length }})
        </button>
      </header>

      <section class="avc-panel p-5">
        <label class="text-sm block max-w-md">
          <span class="avc-label">Project</span>
          <select class="avc-input mt-2" [(ngModel)]="selectedProjectId" (ngModelChange)="loadClips()">
            <option value="">Select project</option>
            <option *ngFor="let project of projects()" [value]="project.id">{{ project.name }}</option>
          </select>
        </label>
      </section>

      <div *ngIf="error()" class="rounded-xl border border-danger/40 bg-danger/10 px-4 py-3 text-sm text-danger">
        {{ error() }}
      </div>
      <div *ngIf="job()" class="avc-panel p-4 text-sm">
        {{ job()?.status }} · {{ job()?.message }} · {{ job()?.progress | number: '1.0-0' }}%
      </div>

      <section class="space-y-3" *ngIf="clips().length; else empty">
        <article class="avc-panel p-4 flex flex-wrap items-start gap-4" *ngFor="let clip of clips()">
          <label class="mt-1">
            <input type="checkbox" [checked]="selectedIds().includes(clip.id)" (change)="toggle(clip.id)" />
          </label>
          <div class="min-w-0 flex-1">
            <div class="font-medium">{{ clip.hook || clip.title }}</div>
            <div class="text-xs text-muted mt-1">
              {{ clip.status }} · {{ clip.duration_seconds | number: '1.1-1' }}s · score
              {{ clip.score | number: '1.0-0' }}
            </div>
            <div class="text-xs text-muted mt-2 break-all" *ngIf="clip.output_path">{{ clip.output_path }}</div>
          </div>
          <div class="flex gap-2">
            <button class="avc-btn-ghost text-xs" type="button" (click)="renderOne(clip)" [disabled]="busy()">
              Render
            </button>
            <button class="avc-btn-ghost text-xs" type="button" (click)="remove(clip)">Delete</button>
          </div>
        </article>
      </section>
      <ng-template #empty>
        <div class="avc-panel p-8 text-sm text-muted">No clips for this project yet.</div>
      </ng-template>
    </div>
  `,
})
export class ExportLibraryComponent implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);
  private pollSub: Subscription | null = null;

  readonly projects = signal<Project[]>([]);
  readonly clips = signal<Clip[]>([]);
  readonly selectedIds = signal<string[]>([]);
  readonly job = signal<ProcessingJob | null>(null);
  readonly busy = signal(false);
  readonly error = signal<string | null>(null);
  selectedProjectId = '';

  ngOnInit(): void {
    this.api.listProjects().subscribe({
      next: (projects) => this.projects.set(projects),
      error: (err) => this.error.set(err?.message || 'Failed to load projects'),
    });
  }

  ngOnDestroy(): void {
    this.pollSub?.unsubscribe();
  }

  loadClips(): void {
    this.selectedIds.set([]);
    if (!this.selectedProjectId) {
      this.clips.set([]);
      return;
    }
    this.api.getProjectClips(this.selectedProjectId).subscribe({
      next: (clips) => this.clips.set(clips),
      error: (err) => this.error.set(err?.error?.detail || 'Failed to load clips'),
    });
  }

  toggle(id: string): void {
    this.selectedIds.update((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id]
    );
  }

  renderOne(clip: Clip): void {
    this.busy.set(true);
    this.api.renderClip(clip.id, { burn_subtitles: true }).subscribe({
      next: (job) => this.watch(job, () => this.loadClips()),
      error: (err) => {
        this.busy.set(false);
        this.error.set(err?.error?.detail || 'Render failed');
      },
    });
  }

  batchExport(): void {
    const ids = this.selectedIds();
    if (!ids.length) {
      return;
    }
    this.busy.set(true);
    this.api.exportClips(ids).subscribe({
      next: (job) => this.watch(job, () => this.loadClips()),
      error: (err) => {
        this.busy.set(false);
        this.error.set(err?.error?.detail || 'Export failed');
      },
    });
  }

  remove(clip: Clip): void {
    this.api.deleteClip(clip.id).subscribe({
      next: () => this.loadClips(),
      error: (err) => this.error.set(err?.error?.detail || 'Delete failed'),
    });
  }

  private watch(job: ProcessingJob, onDone: () => void): void {
    this.job.set(job);
    this.pollSub?.unsubscribe();
    this.pollSub = timer(0, 1500)
      .pipe(switchMap(() => this.api.getJob(job.id)))
      .subscribe({
        next: (updated) => {
          this.job.set(updated);
          if (['completed', 'failed', 'cancelled'].includes(updated.status)) {
            this.busy.set(false);
            this.pollSub?.unsubscribe();
            this.pollSub = null;
            onDone();
            if (updated.status === 'failed') {
              this.error.set(updated.error || 'Job failed');
            }
          }
        },
      });
  }
}
